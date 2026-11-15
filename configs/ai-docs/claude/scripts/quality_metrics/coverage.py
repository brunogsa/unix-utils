"""Joins the lines a change touched with an lcov report into
changed-line coverage, as a percentage.

Coverage under 90% is flagged. A changed line with no lcov entry
holds no executable code, so it counts toward neither side.
"""

from quality_metrics.functions import measurement

COVERAGE_LIMIT = 90

PERCENT = 100


def coverage_measurement(target, hits_by_file):
    """One file-scoped record: share of changed coverable lines run."""
    line_hits = hits_by_file.get(str(target.path), {})
    changed_hits = [
        hits for line, hits in line_hits.items()
        if target.touches(line, line)
    ]
    covered_count = sum(1 for hits in changed_hits if hits > 0)
    if not changed_hits:
        return coverage_record(target, 0)
    return coverage_record(
        target, covered_count * PERCENT / len(changed_hits)
    )


def coverage_record(target, percent):
    record = measurement(target, "coverage", percent, COVERAGE_LIMIT)
    return {**record, "flagged_below_limit": True}
