"""Deferred records: the pessimistic stand-ins for a metric
whose tool could not run and was deferred.

A deferred record has no value, so it never reads as passing,
and it carries the `pessimistic` marker that keeps it from
holding a commit.
"""

from pathlib import Path

from quality_metrics.coverage import coverage_record
from quality_metrics.crap import DEFERRED_CRAP_SCORE, crap_record
from quality_metrics.functions import measurement
from quality_metrics.touched import Target

DEFERRED_LABEL = "pessimistic, tooling deferred"
NO_LANGUAGE_ENTRY_STATUS = "not measured: no language entry"


def _as_deferred(record):
    """`record` marked pessimistic and labelled as deferred."""
    return {**record, "pessimistic": True, "label": DEFERRED_LABEL}


def deferred_measurement(target, metric, limit, function=None):
    """A record for a metric whose tool could not run and was
    deferred.

    It has no value, so it never reads as passing, and it
    carries the `pessimistic` marker that keeps it from holding
    a commit.
    """
    return _as_deferred(measurement(target, metric, None, limit, function))


def deferred_flagged_measurement(target, metric, flagged_value, limit):
    """A record read as flagged when its tool could not run,
    labelled.

    The worst case lists as a violation yet, being pessimistic,
    never holds a commit, so a missing tool scores no better
    than a failing check.
    """
    return _as_deferred(measurement(target, metric, flagged_value, limit))


def deferred_crap_measurements(target, functions):
    """One CRAP violation per touched function when complexity
    is deferred.

    Without a complexity there is no score, so each record
    reads the lowest score that flags (DEFERRED_CRAP_SCORE,
    just above CRAP_LIMIT): a worst case that lists as a
    violation yet, being pessimistic, never holds a commit.
    """
    return [
        _as_deferred(crap_record(target, function, DEFERRED_CRAP_SCORE))
        for function in functions
    ]


def deferred_coverage_measurement(target):
    """Coverage read as 0% for a deferred coverage tool,
    labelled.

    0% is the worst case, so CRAP stays pessimistic; the marker
    keeps it from holding a commit.
    """
    return _as_deferred(coverage_record(target, 0))


def unmeasured_file_measurement(file_path):
    """A file-scoped record: no language entry, so nothing was
    measured.

    Deferred and valueless, it never reads as passing, and it
    never holds a commit.
    """
    target = Target(Path(file_path), None, None)
    return {
        **deferred_measurement(target, "language_entry", None),
        "status": NO_LANGUAGE_ENTRY_STATUS,
    }
