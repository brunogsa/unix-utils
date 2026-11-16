"""Builds the metrics verdict text from a measure-quality-metrics report.

Order: deferred metrics and exceptions first, then the open
violations, then the rest. An exception counts only with a split
diff saved on disk and no rejection by the judge, so a claim made
in prose alone, or one the judge rejected, stays an open violation.
"""

import collections
import itertools
import os
import tempfile
from pathlib import Path

from quality_metrics import hotspots
from quality_metrics.failures import DEFERRED_LABEL

METRICS_TAG = "[metrics]"

METRIC_TITLES = {
    ("crap", "function"): "CRAP",
    ("size", "function"): "Function size",
    ("size", "file"): "File size",
}


REJECTED_NOTE = ", exception rejected by the judge"

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


def write_verdict(directory, timestamp, text, in_git=True):
    """Write the verdict into `directory` and return its path.

    The text goes to a hidden temp file in the same directory, then a
    rename, so a reader sees no verdict or the whole one. A killed run
    leaves only the temp file, whose name never matches `verdict_*`.
    """
    target = Path(directory) / verdict_filename(timestamp, in_git)
    descriptor, temp_name = tempfile.mkstemp(dir=target.parent, prefix=".verdict-tmp-")
    try:
        with os.fdopen(descriptor, "w") as temp_file:
            temp_file.write(text)
        os.replace(temp_name, target)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return target


def build_verdict(report, exceptions=(), import_edges=(), in_git=True):
    """Verdict markdown.

    `exceptions` are claims with a saved split diff path, marked
    `rejected` once the judge ruled the split does not read worse;
    `import_edges` are (importer, imported) file pairs;
    `in_git` is False when no git repo encloses the working directory.
    """
    numbers = itertools.count(1)
    claims_by_key = {_key(claim): claim for claim in exceptions}
    accepted = []
    open_violations = []
    for violation in report["violations"]:
        claim = claims_by_key.get(_key(violation))
        is_rejected = bool(claim and claim.get("rejected"))
        if claim and not is_rejected and Path(claim["diff_path"]).is_file():
            accepted.append((violation, claim))
        else:
            open_violations.append((violation, is_rejected))
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
    """One entry per deferred metric, counting the records its tool could not measure.

    A failed test run is pessimistic too but carries no deferral
    label: it is a red build, not deferred tooling.
    """
    counts_by_title = collections.Counter(
        _metric_name(record)
        for record in measurements
        if record.get("label") == DEFERRED_LABEL
    )
    entries = [
        _entry(
            next(numbers),
            f"{title} - {counts_by_title[title]} measurements ({DEFERRED_LABEL})",
        )
        for title in sorted(counts_by_title)
    ]
    return _section(f"Deferred metrics ({len(entries)})", entries)


def _violations_section(violations, numbers):
    entries = [
        _entry(next(numbers), _describe(item) + (REJECTED_NOTE if is_rejected else ""))
        for item, is_rejected in violations
    ]
    return _section(f"Open violations ({len(entries)})", entries)


def _ranked_sections(measurements, numbers):
    """One list per metric and scope, worst first.

    A limit of 0 or none has no ranking, nor has a neutral
    record.
    """
    records_by_title = {}
    for record in measurements:
        if record["limit"] and record["limit"] > 0 and not hotspots.is_neutral(record):
            records_by_title.setdefault(_metric_name(record), []).append(record)
    return [
        _section(
            f"Ranked: {title}",
            [
                _entry(next(numbers), _describe(record))
                for record in sorted(records, key=hotspots.badness, reverse=True)
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
        f"{subject}{where} - {_metric_name(record)} {_shown_value(record)} "
        f"(limit {record['limit']:g})"
    )


def _shown_value(record):
    if record["value"] is None:
        return f"no value ({record['label']})"
    return f"{record['value']:g}"


def _metric_name(record):
    return METRIC_TITLES.get((record["metric"], record["scope"]), record["metric"])
