"""Measures CRAP and changed-line coverage for one touched file.

Both metrics read the same test run, so one module serves them.
"""

from quality_metrics.collection import NO_COVERAGE_DATA
from quality_metrics.coverage import coverage_measurement
from quality_metrics.crap import crap_measurements
from quality_metrics.declaration import is_coverage_opted_out
from quality_metrics.failures import deferred_coverage_measurement, deferred_crap_measurements
from quality_metrics.functions import touched_functions
from quality_metrics.repo_paths import repo_relative


def measure(target, metrics, declaration, coverage_run):
    """CRAP and coverage records of the declared `metrics`.

    `target.repo_path` names the real file, in any form
    `repo_relative` accepts: lcov names files repo-relative,
    while `target.path` can be a temporary copy.
    """
    result = _coverage_result(declaration, target, coverage_run)
    if result.is_deferred:
        return _deferred_records(target, metrics)
    key = repo_relative(coverage_run.repo_dir, target.repo_path)
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
    if result.has_failed_tests:
        return [{**record, "pessimistic": True} for record in records]
    return records


def _deferred_records(target, metrics):
    """Pessimistic records for a coverage tool that was
    deferred.

    An ask is always paired with these, so a deferred tool
    never leaves a metric with no record.
    """
    records = []
    if "crap" in metrics:
        records += deferred_crap_measurements(target, touched_functions(target))
    if "coverage" in metrics:
        records.append(deferred_coverage_measurement(target))
    return records


def _coverage_result(declaration, target, coverage_run):
    """A language that opts coverage out needs no test run."""
    if is_coverage_opted_out(declaration, target.language):
        return NO_COVERAGE_DATA
    return coverage_run.result_for(target.language)
