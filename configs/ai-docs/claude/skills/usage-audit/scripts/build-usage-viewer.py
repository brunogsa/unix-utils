#!/usr/bin/env python3
# build-usage-viewer - Render the snapshot series as one self-contained HTML page.
#
# Usage:
#   build-usage-viewer.py            # write usage-history/viewer.html
#   build-usage-viewer.py --open     # ...and open it in the default browser
#   build-usage-viewer.py -o PATH    # write somewhere else
#
# Reads every usage-history/snapshots/*.json plus the config-change ledger for the
# same range, and injects both into assets/viewer-template.html.
#
# WHY INLINE THE DATA: a page opened over file:// cannot fetch a sibling .json —
# the browser blocks it as a cross-origin request. Inlining is what keeps the
# viewer a double-click away instead of requiring a local web server.
#
# WHY A CHART AT ALL: the per-day series is a time series, and the markdown log
# cannot show one. A spend swing from $156 to $616 inside a week reads as noise
# in a table and as an obvious shape in a chart — and the ledger markers put the
# config change that caused it directly under the day it landed.

import argparse
import glob
import importlib.util
import json
import os
import sys
import webbrowser
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
SNAPSHOTS_DIR = os.path.join(SKILL_DIR, "usage-history", "snapshots")
TEMPLATE = os.path.join(SKILL_DIR, "assets", "viewer-template.html")
DEFAULT_OUT = os.path.join(SKILL_DIR, "usage-history", "viewer.html")

DATA_TOKEN = "__USAGE_DATA__"

# Per-day fields the page actually reads. Anything else is dead weight in a file
# that already inlines 40+ days of aggregates.
DAY_FIELDS = (
    "coverage", "kpis", "total", "main_cost", "subagent_cost", "compactions",
    "session_count", "cache_hit_rate", "thinking_block_share", "tokens",
    "by_family", "by_subagent_type", "by_skill_marginal", "top_sessions",
    "reconciliation",
)

# Only the verdict is rendered. The four per-bucket token counts behind it are
# ~400 bytes a day the page never shows, and the day file keeps them anyway.
RECONCILIATION_FIELDS = ("status", "worst_delta_pct")

# Sessions shown per day, and the columns the page renders for each. Untrimmed,
# `top_sessions` alone was 139 KB of the payload — full transcript paths and a
# per-session token dict nothing on the page reads.
TOP_SESSIONS = 8
SESSION_FIELDS = ("title", "cost", "duration_hours", "compactions",
                  "user_messages", "interruptions", "skills")


def trim_sessions(sessions):
    """The top few sessions, reduced to the fields the page renders."""
    out = []
    for session in sessions[:TOP_SESSIONS]:
        row = {k: session[k] for k in SESSION_FIELDS if k in session}
        # The transcript path is 90+ chars of constant prefix; only the session
        # id distinguishes one row from the next, and only when title is blank.
        path = session.get("path", "")
        row["id"] = os.path.basename(path).split(".")[0][:8]
        out.append(row)
    return out


def load_ledger(since_day, until_day):
    """Config commits per day, or an empty map when the ledger can't run.

    Imported rather than shelled out to: the filename has a dash, so it is not a
    valid module name for a plain import, and a subprocess would re-pay Python
    startup for data this process is about to serialize anyway.
    """
    path = os.path.join(SCRIPTS_DIR, "config-change-ledger.py")
    spec = importlib.util.spec_from_file_location("config_change_ledger", path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        root = module.repo_root()
        if not root:
            return {}
        commits = module.read_commits(root, since_day, until_day)
    except Exception as err:
        print(f"ledger unavailable, rendering without commit markers: {err}", file=sys.stderr)
        return {}
    by_day = {}
    for commit in commits:
        by_day.setdefault(commit["day"], []).append(
            {k: commit[k] for k in ("sha", "subject", "surfaces")})
    return by_day


def load_days():
    days = {}
    for path in sorted(glob.glob(os.path.join(SNAPSHOTS_DIR, "*.json"))):
        try:
            with open(path) as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as err:
            print(f"skipping unreadable snapshot {path}: {err}", file=sys.stderr)
            continue
        day = payload.get("day")
        if not day:
            # A pre-rewrite window snapshot has no `day`; it measures a range and
            # cannot be placed on a per-day axis without misrepresenting it.
            print(f"skipping {os.path.basename(path)}: no `day` field (legacy window snapshot)",
                  file=sys.stderr)
            continue
        entry = {k: payload[k] for k in DAY_FIELDS if k in payload}
        entry["top_sessions"] = trim_sessions(entry.get("top_sessions", []))
        block = entry.get("reconciliation")
        # A snapshot predating the gate has no block at all. Left absent, the page
        # treats it as unverified rather than silently as verified — the day was
        # measured by an aggregator no independent reader ever checked.
        if isinstance(block, dict):
            entry["reconciliation"] = {
                k: block[k] for k in RECONCILIATION_FIELDS if k in block}
        days[day] = entry
    return days


def main():
    parser = argparse.ArgumentParser(
        description="Render usage snapshots as a self-contained interactive HTML page.")
    parser.add_argument("-o", "--out", default=DEFAULT_OUT, help="output path")
    parser.add_argument("--open", action="store_true", help="open the page when done")
    args = parser.parse_args()

    days = load_days()
    if not days:
        print(f"no per-day snapshots in {SNAPSHOTS_DIR} — run claude-usage-report.py --backfill first",
              file=sys.stderr)
        sys.exit(1)

    ordered = sorted(days)
    payload = {
        "days": days,
        "ledger": load_ledger(ordered[0], ordered[-1]),
        "meta": {
            "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            "first_day": ordered[0],
            "last_day": ordered[-1],
        },
    }

    try:
        with open(TEMPLATE) as fh:
            html = fh.read()
    except OSError as err:
        print(f"cannot read template {TEMPLATE}: {err}", file=sys.stderr)
        sys.exit(1)

    # `</script>` inside a string literal would close the tag early and truncate
    # the page; escaping the slash is the standard fix and stays valid JSON.
    blob = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(DATA_TOKEN, blob)

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        fh.write(html)

    size_kb = os.path.getsize(out) / 1024
    marked = sum(1 for d in ordered if payload["ledger"].get(d))
    print(f"wrote {out} ({size_kb:.0f} KB)")
    print(f"  {len(ordered)} days: {ordered[0]} .. {ordered[-1]}")
    print(f"  {marked} day(s) carry config-commit markers")

    if args.open:
        webbrowser.open(f"file://{out}")


if __name__ == "__main__":
    main()
