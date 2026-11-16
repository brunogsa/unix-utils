"""Joins the lines a change touched with an lcov report into
changed-line coverage, as a percentage.

Coverage under 90% is flagged. A changed line with no lcov
entry holds no executable code, so it counts toward neither
side. A file the report omits entirely reads 0%: nothing ran
it. A listed file with no coverable changed line reads not
applicable.
"""

from quality_metrics.functions import measurement

COVERAGE_LIMIT = 90

NO_COVERABLE_LINES = "not applicable: no coverable lines"

PERCENT = 100


def coverage_measurement(target, line_hits):
    """One file-scoped record: share of changed coverable lines
    run.

    `line_hits` is None when the report omits the file.
    """
    if line_hits is None:
        return coverage_record(target, 0)
    changed_hits = [
        hits for line, hits in line_hits.items()
        if target.touches(line, line)
    ]
    covered_count = sum(1 for hits in changed_hits if hits > 0)
    if not changed_hits:
        return not_applicable_record(target)
    return coverage_record(
        target, covered_count * PERCENT / len(changed_hits)
    )


def not_applicable_record(target):
    """A listed file whose changed lines hold no code: no
    verdict."""
    record = measurement(target, "coverage", None, COVERAGE_LIMIT)
    return {**record, "status": NO_COVERABLE_LINES}


def coverage_record(target, percent):
    record = measurement(target, "coverage", percent, COVERAGE_LIMIT)
    return {**record, "flagged_below_limit": True}
