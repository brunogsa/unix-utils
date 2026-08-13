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

# The 5 fixed shards the orchestrator always fans out to (plan D3, spec
# S5): a narrative.json missing any one of these is malformed input,
# never a silently-blank section. S5 Recommendations runs sequentially
# after the other 4 are merged (it needs their findings to be specific
# rather than generic), but its digest is validated the same way.
REQUIRED_SECTIONS = ("time", "money", "work", "status", "recommendations")
SECTION_TITLES = {
    "time": "Time",
    "money": "Money",
    "work": "Work done",
    "status": "Status and next steps",
    "recommendations": "Recommendations",
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


def _format_duration_hours(seconds):
    """Render a duration for a human reader, never a bare seconds count
    once it crosses a minute -- gap 4: the old renderer printed every
    duration in raw seconds, which is unreadable for a multi-hour session.

    >= 3600s -> "12h 47m" (hours + minutes, no seconds)
    >= 60s   -> "42m"     (minutes only, no seconds)
    else     -> "38s"     (bare seconds; sub-minute durations have nothing
                            coarser worth showing)
    """
    total_seconds = int(seconds)
    if total_seconds >= 3600:
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"
    if total_seconds >= 60:
        minutes = total_seconds // 60
        return f"{minutes}m"
    return f"{total_seconds}s"


def _render_stacked_bar_svg(segments, width=600, height=28):
    """One horizontal stacked bar as inline SVG, plus a matching legend
    list -- reused by the time-bucket partition and the money
    main-vs-subagent split, both spec'd as "one horizontal stacked bar,
    each segment labelled".

    `segments` is a list of {"label", "fraction", "color", "detail"}: a
    segment's on-screen width is its `fraction` normalized against the
    total of all fractions (never against the sum of a caller's raw
    seconds/dollars), so a caller can pass an already-reconciled pct
    verbatim without this helper re-deriving anything from it. `detail`
    is the caller's own fully-formatted text (e.g. "20m (33.0%)") for
    the legend row -- this helper only escapes and lays it out.

    No xmlns attribute: optional for inline SVG under HTML5, and
    "http://www.w3.org/2000/svg" would trip the no-http(s):// guard that
    keeps this page free of any external-resource reference.
    """
    total_fraction = sum(seg["fraction"] for seg in segments) or 1
    x = 0.0
    rects = []
    legend_rows = []
    for seg in segments:
        seg_width = (seg["fraction"] / total_fraction) * width
        rects.append(
            f'<rect x="{x:.1f}" y="0" width="{seg_width:.1f}" height="{height}" '
            f'fill="{seg["color"]}"><title>{_escape(seg["label"])}: {_escape(seg["detail"])}</title></rect>\n'
        )
        legend_rows.append(
            f'<li><span class="swatch" style="background:{seg["color"]}"></span>'
            f'{_escape(seg["label"])}: {_escape(seg["detail"])}</li>\n'
        )
        x += seg_width
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="stacked bar chart">\n'
        f'{"".join(rects)}'
        f'</svg>\n'
        f'<ul class="bar-legend">\n{"".join(legend_rows)}</ul>\n'
    )


def _render_bar_row(label, fraction_pct, detail):
    """One labelled horizontal bar whose fill width is `fraction_pct`
    (already normalized 0-100 by the caller) -- the building block for
    the agent-hours-vs-wall-clock-occupied pair and any other
    side-by-side bar comparison."""
    return (
        f'<div class="bar-row">'
        f'<span class="bar-row-label">{_escape(label)}</span>'
        f'<span class="bar-track"><span class="bar-fill" style="width:{fraction_pct:.1f}%"></span></span>'
        f'<span class="bar-row-value">{_escape(detail)}</span>'
        f'</div>\n'
    )


def _render_agent_hours_vs_wall_clock(agent_hours_seconds, wall_clock_occupied_seconds):
    """The classic parallelism ratio: how much agent work ran (summed
    across concurrent subagents) vs. how long the wall clock was actually
    occupied by that work. Two short bars side by side, scaled to
    whichever of the two is larger, so the ratio is visually legible."""
    max_seconds = max(agent_hours_seconds, wall_clock_occupied_seconds) or 1
    return (
        '<div class="bar-pair">\n'
        + _render_bar_row(
            "Agent hours (parallel work)",
            agent_hours_seconds / max_seconds * 100,
            _format_duration_hours(agent_hours_seconds))
        + _render_bar_row(
            "Wall-clock occupied",
            wall_clock_occupied_seconds / max_seconds * 100,
            _format_duration_hours(wall_clock_occupied_seconds))
        + '</div>\n'
    )


# Bucket display names + a distinct colour per bucket, reused by both the
# stacked-bar segments and their legend -- fixed, not derived from data,
# since the buckets are a closed set defined by extract-session-timeline.py's
# time-partition contract (5 as of Scout #33's `unattributed` bucket).
_TIME_BUCKET_LABELS = {
    "main_api": "Main API",
    "tool_exec": "Tool exec",
    "agent_occupied": "Agent occupied",
    "unattributed": "Unattributed",
    "human_idle": "Human idle",
}
_TIME_BUCKET_COLORS = {
    "main_api": "#4c78a8",
    "tool_exec": "#f58518",
    "agent_occupied": "#54a24b",
    "unattributed": "#8c8c8c",
    "human_idle": "#b279a2",
}


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


def _render_section(digest, extra_html=""):
    """One narrative section. `extra_html` (a deterministic data panel --
    e.g. the Money or Time data viz) is injected right after the `<h2>` and
    before the headline/ranked/findings, in both the complete and
    incomplete branches: the spec merges "one section per topic, data panel
    first, shard narrative underneath" rather than the old renderer's
    double-render (a bare data section AND a separate narrative section for
    the same topic), and a failed/incomplete shard is no reason to also
    hide the deterministic data that render independently of it."""
    section = digest["section"]
    title = SECTION_TITLES.get(section, section)
    incomplete = digest.get("incomplete")
    if incomplete:
        return (
            f'<section class="incomplete">\n'
            f"<h2>{_escape(title)} — INCOMPLETE</h2>\n"
            f"{extra_html}"
            f"<p>{_escape(incomplete)}</p>\n"
            f"</section>\n"
        )
    findings = "".join(f"<li>{_escape(finding)}</li>\n" for finding in digest.get("findings", []))
    return (
        f"<section>\n"
        f"<h2>{_escape(title)}</h2>\n"
        f"{extra_html}"
        f'<p class="headline">{_escape(digest.get("headline", ""))}</p>\n'
        f"{_render_ranked(digest.get('ranked', []))}\n"
        f"<ul>\n{findings}</ul>\n"
        f"</section>\n"
    )


def _validate_required_sections(sections_by_id):
    missing = [name for name in REQUIRED_SECTIONS if name not in sections_by_id]
    if missing:
        raise ValueError(
            f"narrative digest missing required section(s): {', '.join(missing)}")


def _render_narrative(cost, timeline, narrative):
    """Compose the narrative sections in the spec's fixed page order --
    Money and Time each get their deterministic data panel merged in via
    `extra_html`; Work done, Status and next steps, and Recommendations are
    narrative-only. Validation (every REQUIRED_SECTIONS name present) is
    split from composition (explicit per-topic calls in page order) so a
    missing section still raises regardless of where it would have landed
    on the page."""
    sections_by_id = {digest["section"]: digest for digest in narrative.get("sections", [])}
    _validate_required_sections(sections_by_id)
    return "".join([
        _render_section(sections_by_id["money"], _render_money_panel(cost)),
        _render_section(sections_by_id["time"], _render_time_partition(timeline)),
        _render_section(sections_by_id["work"]),
        _render_section(sections_by_id["status"]),
        _render_section(sections_by_id["recommendations"]),
    ])


def _kpi_tile(label, value):
    return (
        f'<div class="kpi-tile">'
        f'<span class="kpi-value">{_escape(value)}</span>'
        f'<span class="kpi-label">{_escape(label)}</span>'
        f'</div>\n'
    )


def _render_highlights(cost, timeline):
    """Gap 7's Highlights strip: a deterministic KPI card grid computed
    straight from cost.json/timeline.json, never LLM prose. Every tile is
    independently gated on its own source key(s) -- `_cost_fixture()` in
    the test file carries only total/main_cost/subagent_cost, and this
    function must render sanely (skip the tile, never print a literal
    "None") for every key it omits."""
    tiles = []

    total = cost.get("total")
    if total is not None:
        tiles.append(_kpi_tile("Total cost", f"${total:.2f}"))

    wall_clock_seconds = timeline.get("time_partition", {}).get("wall_clock_seconds")
    if wall_clock_seconds is not None:
        tiles.append(_kpi_tile("Wall clock", _format_duration_hours(wall_clock_seconds)))

    kpis = cost.get("kpis", {})
    session_hours = kpis.get("session_hours")
    if total is not None and session_hours:
        tiles.append(_kpi_tile("Cost / hour", f"${total / session_hours:.2f}"))

    main_cost = cost.get("main_cost")
    subagent_cost = cost.get("subagent_cost")
    if main_cost is not None and subagent_cost is not None:
        combined = main_cost + subagent_cost
        main_pct = (main_cost / combined * 100) if combined else 0
        tiles.append(_kpi_tile("Main vs subagent", f"{main_pct:.0f}% / {100 - main_pct:.0f}%"))

    cache_hit_rate = cost.get("cache_hit_rate")
    if cache_hit_rate is not None:
        # claude-usage-report.py always emits this as a 0-1 fraction
        # (round(derived["cache_hit_rate"], 3)), never pre-scaled to 0-100.
        tiles.append(_kpi_tile("Cache hit rate", f"{cache_hit_rate * 100:.0f}%"))

    api_calls = cost.get("api_calls")
    if api_calls is not None:
        tiles.append(_kpi_tile("API calls", api_calls.get("main", 0) + api_calls.get("sub", 0)))

    if "user_messages" in kpis:
        tiles.append(_kpi_tile("User messages", kpis["user_messages"]))

    if "compactions" in cost:
        tiles.append(_kpi_tile("Compactions", cost["compactions"]))

    if "interruptions" in kpis:
        tiles.append(_kpi_tile("Interruptions", kpis["interruptions"]))

    if not tiles:
        return ""
    return f'<section>\n<h2>Highlights</h2>\n<div class="kpi-grid">\n{"".join(tiles)}</div>\n</section>\n'


def _render_money_main_vs_subagent(cost):
    """Gap 3: main-vs-subagent spend as one horizontal stacked bar, each
    segment labelled with its dollar amount and its percent of the
    combined main+subagent spend (not of cost.json's `total`, which may
    include cost not attributed to either -- combined is the only
    denominator these two numbers are guaranteed to sum to)."""
    main_cost = cost.get("main_cost")
    subagent_cost = cost.get("subagent_cost")
    if main_cost is None or subagent_cost is None:
        return ""
    combined = main_cost + subagent_cost
    main_pct = (main_cost / combined * 100) if combined else 0
    subagent_pct = 100 - main_pct
    segments = [
        {"label": "Main session", "fraction": main_pct, "color": "#4c78a8",
         "detail": f"${main_cost:.2f} ({main_pct:.0f}%)"},
        {"label": "Subagents", "fraction": subagent_pct, "color": "#f58518",
         "detail": f"${subagent_cost:.2f} ({subagent_pct:.0f}%)"},
    ]
    return f'<div class="stacked-bar">\n{_render_stacked_bar_svg(segments)}</div>\n'


def _render_model_distribution(cost):
    """Gap 2: model distribution was invisible. Horizontal bar rows, one per
    model, each labelled with the model's exact name, its dollar amount, and
    its percent of the distribution's own total (not cost.json's `total`,
    for the same reason _render_money_main_vs_subagent uses `combined`: the
    distribution's own entries are the only values these percentages are
    guaranteed to sum to).

    Prefers `by_model` (exact model names, e.g. "claude-opus-5") since that
    is the more specific figure the spec asks for; falls back to `by_family`
    (e.g. "opus") only when `by_model` is absent, rather than rendering
    nothing."""
    distribution = cost.get("by_model") or cost.get("by_family")
    if not distribution:
        return ""
    total = sum(distribution.values()) or 1
    rows = []
    for name, value in sorted(distribution.items(), key=lambda item: item[1], reverse=True):
        pct = value / total * 100
        rows.append(_render_bar_row(name, pct, f"${value:.2f} ({pct:.0f}%)"))
    return f'<div class="bar-list">\n{"".join(rows)}</div>\n'


def _humanize_token_count(count):
    """A token count in the tens of millions is unreadable as a raw digit
    string -- render it as "58.29M" (two decimals, trailing zero kept) once
    it crosses a million; below that a human can still read the raw count
    at a glance, so only comma-group it rather than inventing a K suffix
    the spec never asked for."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.2f}M"
    return f"{count:,}"


_TOKEN_BREAKDOWN_LABELS = {
    "input": "Input",
    "output": "Output",
    "cache_read": "Cache read",
    "cache_write_5m": "Cache write (5m TTL)",
    "cache_write_1h": "Cache write (1h TTL)",
}


def _render_token_breakdown(cost):
    """Gap 1: a bar row per token type, over
    tokens.{input, output, cache_read, cache_write_5m, cache_write_1h}.
    `cache_read` routinely dwarfs every other count, so each bar is scaled
    to the MAX token value present (never the sum) -- scaling to the sum
    would shrink every other row to an invisible sliver, per the spec:
    "scale each bar to the max token value, not the sum, or every other row
    collapses to invisible"."""
    tokens = cost.get("tokens")
    if not tokens:
        return ""
    present = {name: count for name, count in tokens.items() if count is not None}
    if not present:
        return ""
    max_count = max(present.values()) or 1
    rows = [
        _render_bar_row(_TOKEN_BREAKDOWN_LABELS.get(name, name), count / max_count * 100,
                         _humanize_token_count(count))
        for name, count in present.items()
    ]
    note = (
        '<p class="note">Note: cache write is input&#215;1.25 (5m TTL) / '
        "input&#215;2 (1h TTL), priced per exact model, not per family.</p>\n"
    )
    return f'<div class="bar-list">\n{"".join(rows)}</div>\n{note}'


def _render_thinking_share(cost):
    """Honesty constraint: the usage API never splits thinking tokens out
    of output tokens -- thinking is billed inside tokens.output. This
    renders only the truthful proxy cost.json carries
    (`thinking_block_share`, a share of assistant *blocks*, not tokens),
    with an explicit note so the reader cannot mistake it for a token
    count. Never fabricates a thinking-token count."""
    share = cost.get("thinking_block_share")
    if share is None:
        return ""
    # claude-usage-report.py always emits this as a 0-1 fraction
    # (round(derived["thinking_block_share"], 3)), the same contract as
    # cache_hit_rate -- never pre-scaled to 0-100.
    return (
        f'<p>Thinking-block share: {_escape(f"{share * 100:.1f}%")} of assistant blocks '
        f"({_escape(cost.get('thinking_blocks', 0))} thinking / "
        f"{_escape(cost.get('text_blocks', 0))} text).</p>\n"
        '<p class="note">Note: this is a share of assistant blocks, not tokens -- '
        "the usage API does not split thinking tokens out of output tokens; "
        "thinking is billed inside output tokens.</p>\n"
    )


def _render_subagent_types(cost):
    """Bar rows from `by_subagent_type`, sorted descending by cost (never
    trusting on-disk order), top TOP_N_RANKED + a "plus N more, not shown"
    line for the rest -- the same top-N-ranked convention `_render_ranked`
    already uses (D9), reused here since by_subagent_type can carry more
    entries than fit on a card grid."""
    by_subagent_type = cost.get("by_subagent_type")
    if not by_subagent_type:
        return ""
    ordered = sorted(by_subagent_type.items(), key=lambda item: item[1].get("cost", 0), reverse=True)
    shown = ordered[:TOP_N_RANKED]
    dropped = len(ordered) - len(shown)
    max_cost = max((entry.get("cost", 0) for _, entry in shown), default=0) or 1
    rows = [
        _render_bar_row(name, entry.get("cost", 0) / max_cost * 100,
                         f"${entry.get('cost', 0):.2f} ({entry.get('runs', 0)} runs)")
        for name, entry in shown
    ]
    more = (f'<p class="dropped">plus {dropped} more, not shown</p>\n' if dropped > 0 else "")
    return f'<div class="bar-list">\n{"".join(rows)}</div>\n{more}'


def _render_money_panel(cost):
    """The Money section's deterministic data viz, merged into the single
    Money `<section>` via `_render_section`'s `extra_html` -- replaces the
    old renderer's separate bare "Cost" section, which double-rendered the
    same topic the narrative "Money" section already covered."""
    return (
        f"{_render_money_main_vs_subagent(cost)}"
        f"{_render_model_distribution(cost)}"
        f"{_render_token_breakdown(cost)}"
        f"{_render_thinking_share(cost)}"
        f"{_render_subagent_types(cost)}"
    )


def _render_time_partition(timeline):
    """The Time panel's data viz: a stacked bar across the time buckets,
    plus the agent-hours-vs-wall-clock-occupied parallelism pair. Every
    duration goes through _format_duration_hours (gap 4) -- `pct` is
    still printed exactly as supplied, never re-derived, since
    extract-session-timeline.py already reconciled the buckets to sum to
    100 via largest-remainder rounding."""
    partition = timeline.get("time_partition", {})
    buckets = partition.get("buckets", {})
    segments = [
        {
            "label": _TIME_BUCKET_LABELS.get(name, name),
            "fraction": bucket.get("pct", 0),
            "color": _TIME_BUCKET_COLORS.get(name, "#888"),
            "detail": f"{_format_duration_hours(bucket.get('seconds', 0))} ({bucket.get('pct', 0)}%)",
        }
        for name, bucket in buckets.items()
    ]
    bar_html = _render_stacked_bar_svg(segments) if segments else ""

    agent_vs_wall = partition.get("agent_hours_vs_wall_clock_occupied", {})
    parallelism_html = ""
    if "agent_hours_seconds" in agent_vs_wall and "wall_clock_occupied_seconds" in agent_vs_wall:
        parallelism_html = _render_agent_hours_vs_wall_clock(
            agent_vs_wall["agent_hours_seconds"],
            agent_vs_wall["wall_clock_occupied_seconds"])

    wall_clock_html = (
        f"<p>Wall clock: {_escape(_format_duration_hours(partition['wall_clock_seconds']))}</p>\n"
        if "wall_clock_seconds" in partition else ""
    )
    return (
        f"{wall_clock_html}"
        f'<div class="stacked-bar">\n{bar_html}</div>\n'
        f"{parallelism_html}"
    )


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
        f"{_render_highlights(cost, timeline)}"
        f"{_render_narrative(cost, timeline, narrative)}"
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
