"""Builds the metrics verdict text from a measure-quality-metrics report.

Order: deferred metrics and exceptions first, then the open
violations, then the rest. An exception counts only with a split
diff saved on disk, so a claim made in prose alone stays an
open violation.
"""

import itertools
from pathlib import Path

from quality_metrics import hotspots

METRICS_TAG = "[metrics]"

METRIC_TITLES = {
    ("crap", "function"): "CRAP",
    ("size", "function"): "Function size",
    ("size", "file"): "File size",
}


NO_CODE_MEASURED = "No code file was measured."

NO_GIT_SKIPPED = (
    "No git repo encloses the working directory, so the removed-code check "
    "and the base-ref reads were skipped."
)


def verdict_filename(timestamp, in_git=True):
    """The verdict's file name; a run outside git is named so a reader sees it."""
    if in_git:
        return f"verdict_metrics_{timestamp}.md"
    return f"verdict_quality-gate_no-git_{timestamp}.md"


def build_verdict(report, exceptions=(), import_edges=(), in_git=True):
    """Verdict markdown.

    `exceptions` are claims with a saved split diff path;
    `import_edges` are (importer, imported) file pairs;
    `in_git` is False when no git repo encloses the working directory.
    """
    numbers = itertools.count(1)
    claims_by_key = {_key(claim): claim for claim in exceptions}
    accepted = []
    open_violations = []
    for violation in report["violations"]:
        claim = claims_by_key.get(_key(violation))
        if claim and Path(claim["diff_path"]).is_file():
            accepted.append((violation, claim))
        else:
            open_violations.append((violation, False))
    sections = [
        _deferred_section(report["measurements"], numbers),
        _exceptions_section(accepted, numbers),
        _violations_section(open_violations, numbers),
        *_ranked_sections(report["measurements"], numbers),
        _design_section(report["measurements"], import_edges),
    ]
    if not in_git:
        sections.append(_section("Skipped checks", [NO_GIT_SKIPPED]))
    return "\n\n".join(sections) + "\n"


def _key(item):
    return (item["file"], item["function"], item["metric"])


def _exceptions_section(accepted, numbers):
    entries = [
        _entry(
            next(numbers),
            f"{_describe(violation)}, split {_metric_name(violation)} "
            f"{claim['split_value']:g}, [split diff]({claim['diff_path']})",
        )
        for violation, claim in accepted
    ]
    return _section(f"Exceptions ({len(entries)})", entries)


def _deferred_section(measurements, numbers):
    """One entry per deferred metric, counting the records its tool could not measure."""
    labels_by_title = {}
    counts_by_title = {}
    for record in measurements:
        if record.get("pessimistic"):
            title = _metric_name(record)
            labels_by_title[title] = record["label"]
            counts_by_title[title] = counts_by_title.get(title, 0) + 1
    entries = [
        _entry(
            next(numbers),
            f"{title} - {counts_by_title[title]} measurements ({labels_by_title[title]})",
        )
        for title in sorted(counts_by_title)
    ]
    return _section(f"Deferred metrics ({len(entries)})", entries)


def _violations_section(violations, numbers):
    entries = [
        _entry(next(numbers), _describe(item))
        for item, _ in violations
    ]
    return _section(f"Open violations ({len(entries)})", entries)


def _ranked_sections(measurements, numbers):
    """One list per metric and scope, worst value first; a limit of 0 has no ranking."""
    records_by_title = {}
    for record in measurements:
        if record["limit"] > 0:
            records_by_title.setdefault(_metric_name(record), []).append(record)
    return [
        _section(
            f"Ranked: {title}",
            [
                _entry(next(numbers), _describe(record))
                for record in sorted(records, key=lambda item: -item["value"])
            ],
        )
        for title, records in sorted(records_by_title.items())
    ]


def _design_section(measurements, import_edges):
    if not measurements:
        return f"## Code design\n\n{NO_CODE_MEASURED}"
    view = hotspots.hotspot_view({"measurements": measurements}, import_edges)
    return f"## Code design\n\n{view}"


def _section(title, entries):
    return "\n\n".join([f"## {title}", *entries])


def _entry(number, text):
    return f"### {number}. {METRICS_TAG} {text}"


def _describe(record):
    subject = record["function"] or record["file"]
    where = f" in {record['file']}" if record["function"] else ""
    return (
        f"{subject}{where} - {_metric_name(record)} {record['value']:g} "
        f"(limit {record['limit']:g})"
    )


def _metric_name(record):
    return METRIC_TITLES.get((record["metric"], record["scope"]), record["metric"])
