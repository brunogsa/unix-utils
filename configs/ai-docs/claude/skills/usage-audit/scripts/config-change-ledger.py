#!/usr/bin/env python3
# config-change-ledger - What changed in the Claude Code config, grouped by day.
#
# Usage:
#   config-change-ledger.py                      # oldest snapshot day .. yesterday
#   config-change-ledger.py --since 2026-07-20   # from a day
#   config-change-ledger.py --since 2026-07-20 --until 2026-07-24
#   config-change-ledger.py --json               # machine-readable
#
# Pairs with claude-usage-report.py: that one says WHAT usage did on a day, this
# one says WHAT CHANGED that day to explain it. A config edit lands on day D and
# shows up in the KPIs on D+1 onward, so the ledger is the candidate-cause list
# an audit reads next to the snapshot deltas.
#
# It also settles a question the experiments log cannot answer about itself:
# whether a row's "change" actually shipped. Three rows sat `running` for over a
# week describing tweaks that were never enacted ("no actual toggle has been
# tried yet"). A commit either exists or it does not.
#
# Scope is configs/ai-docs/claude/ — CLAUDE.md, skills, agents, settings.json and
# hooks are the only tracked paths that can change token spend. Widening it to
# the whole repo adds shell/editor commits that cannot move a usage KPI.
#
# WHY A SCRIPT AND NOT AN INLINE `git log`: day grouping, surface classification
# and the --json shape are reasons enough, but rtk adds one more.
#
# `rtk git log` injects a default -n cap — 10 commits, 50 with --pretty — and
# announces it on neither stdout nor stderr. The truncated head then reads as the
# complete answer for whatever range was asked for, and since git orders newest
# first, a multi-day range comes back looking like a single day.
#
# The range flags themselves survive: --since and --until pass through untouched,
# and an explicit -n is honored exactly. The cap is the entire defect.
#
# The hook rewrites Bash tool calls, not subprocesses, so the git call below never
# meets the cap regardless.

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta

# realpath resolves the ~/.claude symlink so the repo is found from either path.
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SNAPSHOTS_DIR = os.path.join(SKILL_DIR, "usage-history", "snapshots")
SNAPSHOT_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")

# The config tree that can move a usage KPI, relative to the repo root.
CONFIG_PATH = "configs/ai-docs/claude"

# Record separator: a byte sequence that cannot occur in a commit subject.
RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"


def repo_root():
    """The unix-utils checkout holding this skill, or None when it is not a repo."""
    try:
        out = subprocess.run(
            ["git", "-C", SKILL_DIR, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def classify(path):
    """A changed file -> the config surface it belongs to.

    Surfaces are what an audit reasons about ("did a skill change or did the
    model pin change?"), so collapsing file paths into them keeps a day with 40
    commits readable without dropping which levers actually moved.
    """
    rest = path[len(CONFIG_PATH) + 1:] if path.startswith(CONFIG_PATH + "/") else path
    parts = rest.split("/")
    if parts[0] in ("skills", "agents", "hooks", "scripts") and len(parts) > 1:
        # A skill is a directory; an agent/hook/script is a single file.
        name = parts[1][:-3] if parts[1].endswith(".md") else parts[1]
        return f"{parts[0][:-1]}:{name}"
    return parts[0]


def read_commits(root, since_day, until_day):
    """Commits touching the config tree in [since_day, until_day], newest first.

    Both bounds are committer-date, matching git's own --since/--until filter —
    %ad (author date) can differ, and mixing the two makes the printed dates
    disagree with the range that selected them.
    """
    fmt = RECORD_SEP + FIELD_SEP.join(["%cd", "%h", "%s"])
    try:
        out = subprocess.run(
            ["git", "-C", root, "log",
             f"--since={since_day} 00:00:00", f"--until={until_day} 23:59:59",
             "--date=short", f"--pretty=format:{fmt}", "--name-only",
             "--", CONFIG_PATH],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"git log failed: {err}", file=sys.stderr)
        return []
    commits = []
    for chunk in out.stdout.split(RECORD_SEP):
        if not chunk.strip():
            continue
        header, _, files_blob = chunk.partition("\n")
        fields = header.split(FIELD_SEP)
        if len(fields) != 3:
            continue
        day, sha, subject = fields
        files = [line for line in files_blob.splitlines() if line.strip()]
        commits.append({
            "day": day,
            "sha": sha,
            "subject": subject,
            "surfaces": sorted({classify(f) for f in files}),
        })
    return commits


def snapshot_days():
    """Local days that already have a usage snapshot."""
    try:
        names = os.listdir(SNAPSHOTS_DIR)
    except OSError:
        return []
    return sorted(m.group(1) for m in (SNAPSHOT_DAY_RE.match(n) for n in names) if m)


def render_text(by_day, since_day, until_day):
    if not by_day:
        print(f"no config commits in {since_day}..{until_day}")
        return
    print(f"config-change ledger · {CONFIG_PATH} · {since_day}..{until_day}\n")
    for day in sorted(by_day, reverse=True):
        commits = by_day[day]
        surfaces = sorted({s for c in commits for s in c["surfaces"]})
        print(f"== {day} · {len(commits)} commit(s) · {len(surfaces)} surface(s) ==")
        for commit in commits:
            print(f"  {commit['sha']}  {commit['subject']}")
            print(f"            {', '.join(commit['surfaces'])}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Day-grouped log of Claude Code config changes, to read "
                    "alongside usage snapshots as the candidate-cause list.")
    parser.add_argument("--since", help="earliest day (default: oldest usage snapshot)")
    parser.add_argument("--until", help="latest day (default: yesterday)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()

    root = repo_root()
    if not root:
        print(f"not a git checkout: {SKILL_DIR}", file=sys.stderr)
        sys.exit(1)

    days = snapshot_days()
    since_day = args.since or (days[0] if days else None)
    until_day = args.until or (date.today() - timedelta(days=1)).isoformat()
    if not since_day:
        print("no --since given and no snapshots exist to infer one from", file=sys.stderr)
        sys.exit(1)

    commits = read_commits(root, since_day, until_day)
    by_day = defaultdict(list)
    for commit in commits:
        by_day[commit["day"]].append(commit)

    if args.json:
        print(json.dumps({
            "since": since_day, "until": until_day, "path": CONFIG_PATH,
            "days": {day: by_day[day] for day in sorted(by_day, reverse=True)},
        }, indent=2))
    else:
        render_text(by_day, since_day, until_day)


if __name__ == "__main__":
    main()
