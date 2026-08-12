#!/usr/bin/env python3
# render-session-audit - Fill assets/audit-template.html from cost.json +
# timeline.json + narrative.json to produce one self-contained session audit.
#
# Usage:
#   render-session-audit.py <cost.json> <timeline.json> <narrative.json> [-o DIR]
#
# stdin: none. stdout: the path written. exit: 0 on success, 1 when an
# input file cannot be read/parsed or the narrative digest is missing a
# required section.
#
# WHY DATA_TOKEN-REPLACE, NOT CLIENT-SIDE JS: build-usage-viewer.py's
# pattern is read-template / compute-blob / string-replace / write. Here the
# "blob" is pre-rendered, already-escaped HTML built in Python, not a JSON
# blob for a <script> to parse client-side -- every value that reaches the
# page (commit messages, narrative findings) is transcript-derived text
# flowing into a static file a browser will open, so escaping has to be a
# property of the bytes on disk, checkable without running any JS at all.

import argparse
import html
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "..", "assets", "audit-template.html")
DATA_TOKEN = "__AUDIT_CONTENT__"

# The 4 fixed shards the orchestrator always fans out to (plan D3): a
# narrative.json missing any one of these is malformed input, never a
# silently-blank section.
REQUIRED_SECTIONS = ("time", "money", "work", "status")
SECTION_TITLES = {
    "time": "Time",
    "money": "Money",
    "work": "Work done",
    "status": "Status and next steps",
}

# D9: top-5 per section, plus a "plus N more, not shown" line for the rest.
TOP_N_RANKED = 5

# A rough four-print-page proxy for the largest realistic session (long
# commit list, all 4 sections near their top-N cap): ~75KB/page at this
# template's font size and margins, so 4 pages gives headroom without
# letting the page silently balloon past its budget.
FOUR_PAGE_BYTE_BUDGET = 300_000


def _escape(value):
    return html.escape(str(value), quote=True)


def _render_ranked(ranked):
    """Sorted by value descending, top TOP_N_RANKED rows, plus a "plus N
    more, not shown" line when items were dropped -- the renderer's own
    sort decides what counts as "top", never trusting the digest's
    on-disk order (a shard's ranked[] is not guaranteed pre-sorted)."""
    ordered = sorted(ranked, key=lambda item: item.get("value", 0), reverse=True)
    shown = ordered[:TOP_N_RANKED]
    dropped = len(ordered) - len(shown)
    rows = "".join(
        f"<li>{_escape(item.get('label', ''))}: {_escape(item.get('value', ''))}</li>\n"
        for item in shown
    )
    more = (f'<p class="dropped">plus {dropped} more, not shown</p>\n'
            if dropped > 0 else "")
    return f"<ul>\n{rows}</ul>\n{more}"


def _render_section(digest):
    section = digest["section"]
    title = SECTION_TITLES.get(section, section)
    incomplete = digest.get("incomplete")
    if incomplete:
        return (
            f'<section class="incomplete">\n'
            f"<h2>{_escape(title)} — INCOMPLETE</h2>\n"
            f"<p>{_escape(incomplete)}</p>\n"
            f"</section>\n"
        )
    findings = "".join(f"<li>{_escape(finding)}</li>\n" for finding in digest.get("findings", []))
    return (
        f"<section>\n"
        f"<h2>{_escape(title)}</h2>\n"
        f'<p class="headline">{_escape(digest.get("headline", ""))}</p>\n'
        f"{_render_ranked(digest.get('ranked', []))}\n"
        f"<ul>\n{findings}</ul>\n"
        f"</section>\n"
    )


def _render_narrative(narrative):
    sections_by_id = {digest["section"]: digest for digest in narrative.get("sections", [])}
    missing = [name for name in REQUIRED_SECTIONS if name not in sections_by_id]
    if missing:
        raise ValueError(
            f"narrative digest missing required section(s): {', '.join(missing)}")
    return "".join(_render_section(sections_by_id[name]) for name in REQUIRED_SECTIONS)


def _render_cost_summary(cost):
    return (
        "<section>\n<h2>Cost</h2>\n"
        f"<p>total: {_escape(cost.get('total', 0))}</p>\n"
        f"<p>main_cost: {_escape(cost.get('main_cost', 0))}</p>\n"
        f"<p>subagent_cost: {_escape(cost.get('subagent_cost', 0))}</p>\n"
        "</section>\n"
    )


def _render_time_partition(timeline):
    partition = timeline.get("time_partition", {})
    buckets = partition.get("buckets", {})
    # `pct` is printed exactly as supplied --
    # extract-session-timeline.py already reconciled every
    # bucket's share to sum to 100 after rounding;
    #
    # a renderer that recomputed from seconds could disagree
    # with that reconciled number and print two different
    # answers for one figure.
    rows = "".join(
        f"<li>{_escape(name)}: {_escape(bucket.get('seconds', 0))}s "
        f"({_escape(bucket.get('pct', 0))}%)</li>\n"
        for name, bucket in buckets.items()
    )
    agent_vs_wall = partition.get("agent_hours_vs_wall_clock_occupied", {})
    return (
        "<section>\n<h2>Time</h2>\n"
        f"<p>wall clock: {_escape(partition.get('wall_clock_seconds', 0))}s</p>\n"
        f"<ul>\n{rows}</ul>\n"
        f"<p>agent hours: {_escape(agent_vs_wall.get('agent_hours_seconds', 0))}s vs "
        f"wall-clock occupied: {_escape(agent_vs_wall.get('wall_clock_occupied_seconds', 0))}s</p>\n"
        "</section>\n"
    )


def _render_commits(timeline):
    """The commit list is the one place a raw transcript-authored string
    (the git commit command, which may embed a user- or assistant-written
    commit message) flows straight into this page -- every field here
    must be escaped, not just the obviously "text" ones."""
    commits = timeline.get("commits", {})
    items = commits.get("items", [])
    rows = "".join(
        f"<li>{_escape(item.get('timestamp', ''))} "
        f"[{_escape(item.get('source', ''))}] "
        f"{_escape(item.get('command', ''))}</li>\n"
        for item in items
    )
    note = commits.get("note")
    note_html = f'<p class="note">{_escape(note)}</p>\n' if note else ""
    return f"<section>\n<h2>Commits</h2>\n<ul>\n{rows}</ul>\n{note_html}</section>\n"


def _read_template():
    with open(TEMPLATE_PATH) as fh:
        return fh.read()


def render_audit_html(cost, timeline, narrative, template=None):
    """The full self-contained HTML string for one session's audit.

    Every dynamic value is HTML-escaped before insertion: cost.json,
    timeline.json, and narrative.json all ultimately carry transcript-
    derived text (commit messages, shard findings quoting the session),
    and this string is written straight to a file a browser will open.
    """
    if template is None:
        template = _read_template()
    sid = timeline.get("sid") or cost.get("sid") or "unknown"
    body = (
        f"<h1>Session audit — {_escape(sid)}</h1>\n"
        f"{_render_cost_summary(cost)}"
        f"{_render_time_partition(timeline)}"
        f"{_render_commits(timeline)}"
        f"{_render_narrative(narrative)}"
    )
    return template.replace(DATA_TOKEN, body)


def _sanitize_sid_for_filename(sid):
    """A session id must never carry a path separator into the output
    filename -- extract-session-timeline.py/claude-usage-report.py both
    treat sid as an opaque token, never a path, but a malformed or
    adversarial one (e.g. containing "../") must not be able to steer
    write_audit_html's output outside the requested out_dir, such as
    into usage-history/snapshots/ (AC5)."""
    return re.sub(r"[/\\]", "_", sid)


def write_audit_html(cost, timeline, narrative, out_dir="."):
    sid = timeline.get("sid") or cost.get("sid") or "unknown"
    html_text = render_audit_html(cost, timeline, narrative)
    safe_sid = _sanitize_sid_for_filename(str(sid))
    out_path = os.path.join(out_dir, f"audit_session-{safe_sid}.html")
    with open(out_path, "w") as fh:
        fh.write(html_text)
    return out_path


def _load_json(path):
    with open(path) as fh:
        return json.load(fh)


def main():
    parser = argparse.ArgumentParser(
        description="Render one session's audit as self-contained HTML "
                    "from cost.json + timeline.json + narrative.json.")
    parser.add_argument("cost_json", help="path to cost.json")
    parser.add_argument("timeline_json", help="path to timeline.json")
    parser.add_argument("narrative_json", help="path to narrative.json")
    parser.add_argument("-o", "--out-dir", default=".",
                        help="directory to write the HTML into (default: cwd)")
    args = parser.parse_args()
    try:
        cost = _load_json(args.cost_json)
        timeline = _load_json(args.timeline_json)
        narrative = _load_json(args.narrative_json)
        out_path = write_audit_html(cost, timeline, narrative, args.out_dir)
    except (OSError, ValueError) as err:
        print(f"cannot render audit: {err}", file=sys.stderr)
        sys.exit(1)
    print(out_path)


if __name__ == "__main__":
    main()
