"""Builds the metrics verdict text from a
measure-quality-metrics report.

Order: deferred metrics, tooling asks and exceptions first, then
the open violations, then the rest, with the coverage sources
before the code design.
An exception counts only with a split diff saved on disk and no
rejection by the judge, so a claim made in prose alone, or one
the judge rejected, stays an open violation.
"""

import collections
import itertools
from pathlib import Path

from quality_metrics import debt, hotspots
from quality_metrics.atomic_write import write_text_atomically
from quality_metrics.deferred import DEFERRED_LABEL
from quality_metrics.functions import display_value

METRICS_TAG = "[metrics]"

METRIC_TITLES = {
    ("crap", "function"): "CRAP",
    ("size", "function"): "Function size",
    ("size", "file"): "File size",
    ("nesting", "function"): "Nesting",
    ("parameters", "function"): "Parameters",
    ("cognitive_complexity", "function"): "Cognitive complexity",
    ("coverage", "file"): "Coverage",
    ("code_duplication", "file"): "Code duplication",
    ("test_duplication", "file"): "Test duplication",
    ("dependency_direction", "file"): "Dependency direction",
}

PESSIMISTIC_NOTE = "pessimistic"
REJECTED_NOTE = ", exception rejected by the judge"

NO_CODE_MEASURED = "No code file was measured."

NO_GIT_SKIPPED = (
    "No git repo encloses the working directory, so the removed-code check "
    "and the base-ref reads were skipped."
)


def verdict_filename(timestamp, in_git=True):
    """The verdict's file name; a run outside git is named so a
    reader sees it."""
    if in_git:
        return f"verdict_metrics_{timestamp}.md"
    return f"verdict_quality-gate_no-git_{timestamp}.md"


def write_verdict(directory, timestamp, text, in_git=True):
    """Write the verdict into `directory` and return its path.

    The text goes to a hidden temp file in the same directory,
    then a rename, so a reader sees no verdict or the whole one.
    A killed run leaves only the temp file, whose name never
    matches `verdict_*`.
    """
    target = Path(directory) / verdict_filename(timestamp, in_git)
    write_text_atomically(target, text, temp_prefix=".verdict-tmp-")
    return target


def build_verdict(report, exceptions=(), in_git=True):
    """Verdict markdown.

    `exceptions` are claims with a saved split diff path, marked
    `rejected` once the judge ruled the split does not read
    worse; `in_git` is False when no git repo encloses the
    working directory.
    """
    numbers = itertools.count(1)
    accepted, open_violations = _partition_claims(report["violations"], exceptions)
    sections = [
        _deferred_section(report["measurements"], numbers),
        _asks_section(report.get("asks", []), numbers),
        _exceptions_section(accepted, numbers),
        _violations_section(open_violations, numbers),
        _gate_inputs_section(report.get("gate_input_violations", []), numbers),
        _duplication_section(report.get("duplication_candidates", []), numbers),
        _not_applicable_section(report.get("not_applicable", []), numbers),
        *_ranked_sections(report["measurements"], numbers),
        _sources_section(report.get("sources", []), numbers),
        _debt_section(report),
        _design_section(report["measurements"]),
    ]
    if not in_git:
        sections.append(_section("Skipped checks", [NO_GIT_SKIPPED]))
    return "\n\n".join(sections) + "\n"


def _partition_claims(violations, exceptions):
    """Split violations into accepted ones (a claim whose
    diff file exists, not rejected) and open ones, each
    paired with whether its claim was rejected.
    """
    claims_by_key = {_key(claim): claim for claim in exceptions}
    accepted = []
    open_violations = []
    for violation in violations:
        claim = claims_by_key.get(_key(violation))
        is_rejected = bool(claim and claim.get("rejected"))
        if claim and not is_rejected and Path(claim["diff_path"]).is_file():
            accepted.append((violation, claim))
        else:
            open_violations.append((violation, is_rejected))
    return accepted, open_violations


def _key(item):
    return (item["file"], item["function"], item["metric"])


def _exceptions_section(accepted, numbers):
    entries = [
        _entry(
            next(numbers),
            f"{_describe(violation)}, split {_metric_name(violation)} "
            f"{display_value({'value': claim['split_value']})}, [split diff]({claim['diff_path']})",
        )
        for violation, claim in accepted
    ]
    return _section(f"Exceptions ({len(entries)})", entries)


def _deferred_section(measurements, numbers):
    """One entry per deferred metric, counting the records its
    tool could not measure.

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


def _counted_section(title, items, numbers, describe_item):
    """A titled section with one numbered entry per item, the
    title carrying the entry count."""
    entries = [_entry(next(numbers), describe_item(item)) for item in items]
    return _section(f"{title} ({len(entries)})", entries)


def _asks_section(asks, numbers):
    return _counted_section("Tooling asks", asks, numbers, _describe_ask)


def _describe_ask(ask):
    return f"{ask['tool']} ({ask['metric']}) - {ask['reason']}"


def _sources_section(sources, numbers):
    return _counted_section("Coverage sources", sources, numbers, _describe_source)


def _describe_source(item):
    source = item["source"]
    text = f"{item['language']} - measured by {source['kind']} {source['tool']}"
    if item["exit_class"] is not None:
        text += f", exit class {item['exit_class']}"
    if item["side_pr_candidate"] is not None:
        text += f", side-PR candidate: {item['side_pr_candidate']}"
    return text


def _violations_section(violations, numbers):
    return _counted_section("Open violations", violations, numbers, _describe_open)


def _describe_open(violation_and_rejection):
    item, is_rejected = violation_and_rejection
    return _describe(item) + (REJECTED_NOTE if is_rejected else "")


def _duplication_section(candidates, numbers):
    return _counted_section("Duplication candidates", candidates, numbers, _describe)


def _not_applicable_section(items, numbers):
    """Files a metric could not judge: listed so a reader sees
    they were not measured, never counted as violations."""
    return _counted_section(
        "Not applicable", items, numbers, _describe_not_applicable
    )


def _describe_not_applicable(item):
    title = METRIC_TITLES[(item["metric"], "file")]
    return f"{item['file']} - {title} - not applicable: {item['reason']}"


def _gate_inputs_section(gate_input_violations, numbers):
    return _counted_section(
        "Gate input violations", gate_input_violations, numbers, _describe_gate_input
    )


def _describe_gate_input(item):
    return f"{item['kind']} in {item['file']} - {item['value']}"


def _ranked_sections(measurements, numbers):
    """One list per metric and scope, worst first.

    A limit of 0 or none has no ranking, nor has a neutral
    record.
    """
    records_by_title = {}
    for record in measurements:
        if _is_rankable(record):
            records_by_title.setdefault(_metric_name(record), []).append(record)
    return [
        _ranked_section(title, records, numbers)
        for title, records in sorted(records_by_title.items())
    ]


def _ranked_section(title, records, numbers):
    worst_first = sorted(records, key=hotspots.badness, reverse=True)
    entries = [_entry(next(numbers), _describe(record)) for record in worst_first]
    return _section(f"Ranked: {title}", entries)


def _is_rankable(record):
    return bool(record["limit"]) and record["limit"] > 0 and not hotspots.is_neutral(record)


def _debt_section(report):
    counted = report["violations"] + report.get("duplication_candidates", [])
    score = debt.debt_score(counted, debt.measured_nloc(report["measurements"]))
    if score["ratio"] is None:
        text = f"{score['minutes']} min of remediation; ratio not computable, no file size was measured"
    else:
        text = (
            f"{score['minutes']} min of remediation over {score['nloc']} measured lines = "
            f"{score['ratio']:.1%}, band {score['band']}"
        )
    delta = report.get("debt", {}).get("delta")
    if delta is None:
        return _section("Debt", [text])
    return _section("Debt", [text, _debt_delta_text(delta)])


def _debt_delta_text(delta):
    if not delta["computable"]:
        return f"Debt delta: delta not computable: {delta['reason']}"
    lines = [
        f"- {_delta_name(entry)}: {entry['base_minutes']} -> "
        f"{entry['head_minutes']} min ({entry['delta_minutes']:+d})"
        for entry in delta["files"]
    ]
    return "\n".join([
        "Debt delta on touched files, base ref to HEAD (static metrics only):",
        *lines,
        f"Total: {delta['total_minutes']:+d} min",
    ])


def _delta_name(entry):
    if entry["old_file"]:
        return f"{entry['old_file']} -> {entry['file']}"
    return entry["file"]


def _design_section(measurements):
    if not measurements:
        return _section("Code design", [NO_CODE_MEASURED])
    view = hotspots.hotspot_view(measurements)
    return _section("Code design", [view])


def _section(title, entries):
    return "\n\n".join([f"## {title}", *entries])


def _entry(number, text):
    return f"### {number}. {METRICS_TAG} {text}"


def _describe(record):
    subject = record["function"] or record["file"]
    where = f" in {record['file']}" if record["function"] else ""
    heading = (
        f"{subject}{where} - {_metric_name(record)} {_shown_value(record)} "
        f"(limit {record['limit']:g})"
    )
    uncovered_lines = record.get("uncovered_lines")
    if not uncovered_lines:
        return heading
    return f"{heading}\nUncovered lines: {', '.join(uncovered_lines)}"


def _shown_value(record):
    if record["value"] is None:
        return f"no value ({record['label']})"
    if record.get("label") == DEFERRED_LABEL:
        return f"{display_value(record)} ({DEFERRED_LABEL})"
    if record.get("pessimistic"):
        return f"{display_value(record)} ({PESSIMISTIC_NOTE})"
    return display_value(record)


def _metric_name(record):
    return METRIC_TITLES.get((record["metric"], record["scope"]), record["metric"])
