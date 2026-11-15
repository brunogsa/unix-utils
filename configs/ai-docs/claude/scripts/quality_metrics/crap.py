"""Joins each function's complexity with its line coverage into CRAP.

CRAP = complexity^2 * (1 - coverage)^3 + complexity. A function is
flagged at CRAP 8 or above, so complexity 8 is flagged even at full
coverage, while complexity 7 at full coverage scores 7 and passes.

Coverage comes from an lcov report. A language that declares crap
without coverage opts coverage out and is scored at full coverage;
a coverage tool that failed or has not run reads 0%, never a pass.
"""

from quality_metrics.declaration import is_coverage_opted_out
from quality_metrics.functions import measurement

CRAP_LIMIT = 8

FULL_COVERAGE = 1.0
NO_COVERAGE = 0.0

LCOV_FILE_PREFIX = "SF:"
LCOV_LINE_PREFIX = "DA:"
LCOV_END_OF_FILE = "end_of_record"


def crap_score(complexity, coverage):
    return complexity ** 2 * (1 - coverage) ** 3 + complexity


def parse_lcov(lcov_text):
    """Map each source file to {line number: execution count}."""
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
        if is_opted_out:
            coverage = FULL_COVERAGE
        else:
            coverage = function_coverage(function, line_hits)
        score = crap_score(function.complexity, coverage)
        records.append(crap_record(target, function, score))
    return records


def crap_record(target, function, score):
    record = measurement(target, "crap", score, CRAP_LIMIT, function)
    return {**record, "flagged_at_limit": True}


def function_coverage(function, line_hits):
    """Share of the function's coverable lines that ran; 0 with none."""
    coverable = [
        hits for line, hits in line_hits.items()
        if function.start <= line <= function.end
    ]
    if not coverable:
        return NO_COVERAGE
    return sum(1 for hits in coverable if hits > 0) / len(coverable)
