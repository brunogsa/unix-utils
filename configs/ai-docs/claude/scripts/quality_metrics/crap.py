"""Joins each function's complexity with its line coverage into
CRAP.

CRAP = complexity^2 * (1 - coverage)^3 + complexity.
A function is flagged only above CRAP 30, the original Crap4j
convention, so a score of exactly 30 passes: complexity 8 at
full coverage scores 8 and passes, complexity 5 at 0% scores
30 and passes, complexity 6 at 0% scores 42 and flags.

Coverage comes from an lcov report.
A language that declares crap without coverage opts coverage
out and is scored at full coverage; a coverage tool that failed
or has not run reads 0%, never a pass.
"""

from quality_metrics.coverage import uncovered_ranges
from quality_metrics.declaration import is_coverage_opted_out
from quality_metrics.functions import measurement

CRAP_LIMIT = 30

# The lowest worst-case score that still flags, now that a
# score equal to the limit passes.
DEFERRED_CRAP_SCORE = CRAP_LIMIT + 1

FULL_COVERAGE = 1.0
NO_COVERAGE = 0.0

LCOV_FILE_PREFIX = "SF:"
LCOV_LINE_PREFIX = "DA:"
LCOV_END_OF_FILE = "end_of_record"


def crap_score(complexity, coverage):
    return complexity ** 2 * (1 - coverage) ** 3 + complexity


def parse_lcov(lcov_text):
    """Map each source file to {line number: execution
    count}."""
    hits_by_file = {}
    current_hits = None
    for line in lcov_text.splitlines():
        if line.startswith(LCOV_FILE_PREFIX):
            current_hits = hits_by_file.setdefault(line[len(LCOV_FILE_PREFIX):], {})
        elif line.startswith(LCOV_LINE_PREFIX) and current_hits is not None:
            line_number, hits = line[len(LCOV_LINE_PREFIX):].split(",")[:2]
            current_hits[int(line_number)] = int(hits)
        elif line == LCOV_END_OF_FILE:
            current_hits = None
    return hits_by_file


def crap_measurements(declaration, target, functions, line_hits):
    """One CRAP record per touched function, unrounded."""
    is_opted_out = is_coverage_opted_out(declaration, target.language)
    records = []
    for function in functions:
        uncovered_lines = None
        if is_opted_out:
            coverage = FULL_COVERAGE
        else:
            coverage = function_coverage(function, line_hits)
            if line_hits:
                uncovered_lines = uncovered_ranges(_own_hits(function, line_hits))
        score = crap_score(function.complexity, coverage)
        records.append(crap_record(target, function, score, uncovered_lines))
    return records


def crap_record(target, function, score, uncovered_lines=None):
    """`uncovered_lines` is None when no line data was read:
    null means not measured, [] means every line ran."""
    record = measurement(target, "crap", score, CRAP_LIMIT, function)
    return {**record, "uncovered_lines": uncovered_lines}


def _own_hits(function, line_hits):
    return {
        line: hits for line, hits in line_hits.items()
        if function.start <= line <= function.end
    }


def function_coverage(function, line_hits):
    """Share of the function's coverable lines that ran; 0 with
    none."""
    coverable = list(_own_hits(function, line_hits).values())
    if not coverable:
        return NO_COVERAGE
    return sum(1 for hits in coverable if hits > 0) / len(coverable)
