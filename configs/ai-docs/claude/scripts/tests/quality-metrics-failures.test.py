import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.failures import (
    HEADROOM_MAX_WAIT_SECONDS,
    HEADROOM_POLL_SECONDS,
    TOOL_TIMEOUT_SECONDS,
    TimeoutPolicy,
    ToolTimedOutTwice,
    deferred_measurement,
    holds_commit,
    machine_has_headroom,
)
from quality_metrics.functions import FunctionMeasure, is_over_limit, measurement
from quality_metrics.size import FUNCTION_LINES_LIMIT
from quality_metrics.touched import Target

MEASURED_COMPLEXITY = {"metric": "complexity", "value": 7}


def timing_out_then(outcomes, timeouts_seen):
    """A tool attempt: raises a timeout for each None, else returns the outcome."""
    remaining = list(outcomes)

    def attempt(timeout_seconds):
        timeouts_seen.append(timeout_seconds)
        outcome = remaining.pop(0)
        if outcome is None:
            raise subprocess.TimeoutExpired(["lizard"], timeout_seconds)
        return outcome

    return attempt


def test_should_report_the_measured_value_with_no_ask_when_the_retry_after_a_120_second_timeout_succeeds():
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: True, sleep=lambda seconds: None)

    result = policy.run(timing_out_then([None, MEASURED_COMPLEXITY], timeouts_seen))

    assert result == MEASURED_COMPLEXITY
    assert timeouts_seen == [TOOL_TIMEOUT_SECONDS, TOOL_TIMEOUT_SECONDS]
    assert TOOL_TIMEOUT_SECONDS == 120


def test_should_wait_for_headroom_and_retry_instead_of_asking_when_headroom_is_no_go():
    verdicts = iter([False, False, True])
    sleeps = []
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: next(verdicts), sleep=sleeps.append)

    result = policy.run(timing_out_then([None, MEASURED_COMPLEXITY], timeouts_seen))

    assert result == MEASURED_COMPLEXITY
    assert sleeps == [HEADROOM_POLL_SECONDS, HEADROOM_POLL_SECONDS]
    assert len(timeouts_seen) == 2


@pytest.mark.parametrize(
    ("thresholds", "expected_go"),
    [
        ({"HEADROOM_MIN_FREE_DISK_MB": "0", "HEADROOM_MIN_AVAILABLE_MB": "0", "HEADROOM_LOAD_RATIO_MAX": "100000"}, True),
        ({"HEADROOM_MIN_FREE_DISK_MB": "999999999999"}, False),
    ],
    ids=["go", "no-go"],
)
def test_should_read_the_headroom_verdict_from_check_machine_headroom(monkeypatch, thresholds, expected_go):
    for name, value in thresholds.items():
        monkeypatch.setenv(name, value)

    assert machine_has_headroom() is expected_go


def test_should_mark_a_deferred_result_non_blocking_so_no_commit_is_held():
    target = Target(Path("src/cart.py"), "python", {4})
    deferred_function = FunctionMeasure("apply_discount", 3, 9, 12, 5, 2, 2)
    oversized_function = FunctionMeasure("price_order", 12, 90, 80, 5, 2, 2)
    deferred = deferred_measurement(target, "crap", 8, deferred_function)
    oversized = measurement(target, "size", oversized_function.nloc, FUNCTION_LINES_LIMIT, oversized_function)

    assert deferred["label"] == "pessimistic, tooling deferred"
    assert deferred["pessimistic"] is True
    assert is_over_limit(oversized)
    assert holds_commit([deferred]) is False
    assert holds_commit([deferred, oversized]) is True


def test_should_stop_waiting_and_ask_when_headroom_stays_no_go_past_the_wait_cap():
    sleeps = []
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: False, sleep=sleeps.append)

    with pytest.raises(ToolTimedOutTwice):
        policy.run(timing_out_then([None, MEASURED_COMPLEXITY], timeouts_seen))

    assert sum(sleeps) == HEADROOM_MAX_WAIT_SECONDS
    assert len(timeouts_seen) == 1


def test_should_not_count_a_timeout_under_no_go_headroom_as_the_tool_failing():
    verdicts = iter([False, True, True])
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: next(verdicts), sleep=lambda seconds: None)

    result = policy.run(timing_out_then([None, None, MEASURED_COMPLEXITY], timeouts_seen))

    assert result == MEASURED_COMPLEXITY
    assert len(timeouts_seen) == 3
