import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.failures import TOOL_TIMEOUT_SECONDS, TimeoutPolicy

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
