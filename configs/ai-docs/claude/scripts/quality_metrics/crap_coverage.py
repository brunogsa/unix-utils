"""Measures CRAP and changed-line coverage for one touched file.

Both metrics read the same test run, so one module serves them.
"""

from quality_metrics.collection import NO_COVERAGE_DATA, repo_relative
from quality_metrics.coverage import coverage_measurement
from quality_metrics.crap import crap_measurements
from quality_metrics.declaration import metric_status, NOT_APPLICABLE
from quality_metrics.functions import touched_functions


def measure(target, metrics, declaration, source_path, coverage_run):
    """CRAP and coverage records of the declared `metrics`.

    `source_path` names the real file, in any form `repo_relative`
    accepts: lcov names files repo-relative, while `target.path`
    can be a temporary copy.
    """
    result = _coverage_result(declaration, target, coverage_run)
    key = repo_relative(coverage_run.repo_dir, source_path)
    records = []
    if "crap" in metrics:
        records += crap_measurements(
            declaration, target, touched_functions(target),
            line_hits=result.hits_by_file.get(key, {}),
        )
    if "coverage" in metrics:
        records.append(coverage_measurement(
            target, line_hits=result.hits_by_file.get(key)
        ))
    if result.tests_failed:
        return [{**record, "pessimistic": True} for record in records]
    return records


def _coverage_result(declaration, target, coverage_run):
    """A language that opts coverage out needs no test run."""
    if metric_status(declaration, target.language, "coverage") == NOT_APPLICABLE:
        return NO_COVERAGE_DATA
    return coverage_run.result_for(target.language)
