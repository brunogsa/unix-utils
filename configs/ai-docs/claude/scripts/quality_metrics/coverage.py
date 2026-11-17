"""Joins the lines a change touched with an lcov report into
changed-line coverage, as a percentage plus the changed lines
that never ran.

Coverage under 90% is flagged. A changed line with no lcov
entry holds no executable code, so it counts toward neither
side. A file the report omits entirely reads 0%: nothing ran
it. A listed file with no coverable changed line reads not
applicable.

A JS/TS file with no executable code, such as a type-only file
or a barrel of re-exports, reads not applicable whether or not
the report lists it.
"""

from quality_metrics.executable_code import has_no_executable_code
from quality_metrics.functions import measurement

COVERAGE_LIMIT = 90

NO_COVERABLE_LINES = "not applicable: no coverable lines"
NO_EXECUTABLE_CODE = "not applicable: no executable code"

PERCENT = 100


def coverage_measurement(target, line_hits):
    """One file-scoped record: share of changed coverable lines
    run.

    `line_hits` is None when the report omits the file.
    """
    if has_no_executable_code(target.path):
        return not_applicable_record(target, NO_EXECUTABLE_CODE)
    if line_hits is None:
        return coverage_record(target, 0)
    changed_hits = {
        line: hits for line, hits in line_hits.items()
        if target.touches(line, line)
    }
    covered_count = sum(1 for hits in changed_hits.values() if hits > 0)
    if not changed_hits:
        return not_applicable_record(target)
    return coverage_record(
        target,
        covered_count * PERCENT / len(changed_hits),
        uncovered_lines=uncovered_ranges(changed_hits),
    )


def uncovered_ranges(line_hits):
    """Lines with 0 hits as sorted range strings, e.g.
    ["12-15", "40"]; [] when every line ran."""
    ranges = []
    first = last = None
    for line in sorted(line for line, hits in line_hits.items() if hits == 0):
        if last is not None and line == last + 1:
            last = line
            continue
        if first is not None:
            ranges.append(_range_text(first, last))
        first = last = line
    if first is not None:
        ranges.append(_range_text(first, last))
    return ranges


def _range_text(first, last):
    return str(first) if first == last else f"{first}-{last}"


def not_applicable_record(target, status=NO_COVERABLE_LINES):
    """A file whose changed lines hold no code: no verdict.

    `status` names why no line could run.
    """
    record = measurement(target, "coverage", None, COVERAGE_LIMIT)
    return {**record, "status": status, "uncovered_lines": None}


def coverage_record(target, percent, uncovered_lines=None):
    """`uncovered_lines` is None when no line data was read:
    null means not measured, [] means every line ran."""
    record = measurement(target, "coverage", percent, COVERAGE_LIMIT)
    return {
        **record,
        "flagged_below_limit": percent < COVERAGE_LIMIT,
        "uncovered_lines": uncovered_lines,
    }
