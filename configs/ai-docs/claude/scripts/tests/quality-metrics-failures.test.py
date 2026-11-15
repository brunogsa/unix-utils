import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, head_of, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.failures import (
    HEADROOM_MAX_WAIT_SECONDS,
    HEADROOM_POLL_SECONDS,
    TOOL_TIMEOUT_SECONDS,
    TimeoutPolicy,
    ToolTimedOutTwice,
    ask_unless_deferred,
    run_or_ask,
    deferred_measurement,
    holds_commit,
    machine_has_headroom,
)
from quality_metrics.functions import FunctionMeasure, is_over_limit, measurement
from quality_metrics.size import FUNCTION_LINES_LIMIT
from quality_metrics.sourcing import measure_coverage_or_ask
from quality_metrics.tool_map import LazyToolMap, record_deferred_tool
from quality_metrics.tools import ToolError
from quality_metrics.touched import Target

MEASURED_COMPLEXITY = {"metric": "complexity", "value": 7}

# A jest dying on an internal error: a stack trace, no report.
JEST_CRASH_STUB = """#!/bin/bash
echo "TypeError: Cannot read properties of undefined (reading 'config')" >&2
echo "    at Object.run (/repo/node_modules/jest-cli/build/run.js:31:18)" >&2
exit 1
"""
SESSION_ID = "session-4c9e21"


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


def repo_with_crashing_jest(tmp_path, monkeypatch):
    """A repo whose jest dies on an internal error, and its one JS target."""
    repo = make_repo(tmp_path, {"src/cart.js": "// covered\n"})
    stub_directory = tmp_path / "stubs"
    stub_directory.mkdir()
    jest_stub = stub_directory / "jest"
    jest_stub.write_text(JEST_CRASH_STUB)
    jest_stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_directory}{os.pathsep}{os.environ['PATH']}")
    return repo, Target(repo / "src/cart.js", "javascript", None)


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


def test_should_emit_no_second_ask_for_a_tool_already_deferred_in_this_batch(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": "def add(first, second):\n    return first + second\n"})
    base_sha = head_of(repo)
    tool_map = LazyToolMap(repo, base_sha, [], SESSION_ID, tmp_path)

    first_ask = ask_unless_deferred(tool_map, "coverage.py", "coverage", "crashed")
    record_deferred_tool(repo, base_sha, "coverage.py", SESSION_ID, tmp_path)
    second_ask = ask_unless_deferred(tool_map, "coverage.py", "coverage", "crashed")
    other_tool_ask = ask_unless_deferred(tool_map, "jscpd", "code_duplication", "is not installed")

    assert first_ask == {
        "kind": "ask",
        "tool": "coverage.py",
        "metric": "coverage",
        "reason": "crashed",
        "choices": ["fix now", "defer"],
    }
    assert second_ask is None
    assert other_tool_ask["tool"] == "jscpd"


def test_should_emit_one_ask_and_run_no_third_attempt_when_both_attempts_time_out(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": "def add(first, second):\n    return first + second\n"})
    tool_map = LazyToolMap(repo, head_of(repo), [], SESSION_ID, tmp_path)
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: True, sleep=lambda seconds: None)

    outcome = run_or_ask(
        policy,
        timing_out_then([None, None, MEASURED_COMPLEXITY], timeouts_seen),
        tool_map,
        "lizard",
        "complexity",
    )

    assert outcome["value"] is None
    assert outcome["ask"]["tool"] == "lizard"
    assert outcome["ask"]["metric"] == "complexity"
    assert outcome["ask"]["choices"] == ["fix now", "defer"]
    assert len(timeouts_seen) == 2


def test_should_emit_an_ask_for_a_missing_or_crashing_global_tool_and_score_coverage_0_percent_labelled_pessimistic_on_defer(
    tmp_path, monkeypatch
):
    repo, target = repo_with_crashing_jest(tmp_path, monkeypatch)
    base_sha = head_of(repo)
    tool_map = LazyToolMap(repo, base_sha, [], SESSION_ID, tmp_path)
    global_calls = []

    def crashing_global_tool():
        global_calls.append(target.path)
        raise ToolError("coverage.py crashed with a traceback")

    first_unit = measure_coverage_or_ask(target, repo, crashing_global_tool, tool_map)
    record_deferred_tool(repo, base_sha, "coverage.py", SESSION_ID, tmp_path)
    later_unit = measure_coverage_or_ask(target, repo, crashing_global_tool, tool_map)

    assert first_unit["ask"]["tool"] == "coverage.py"
    assert first_unit["ask"]["metric"] == "coverage"
    assert "coverage.py crashed" in first_unit["ask"]["reason"]
    assert first_unit["measurements"] == []
    assert later_unit["ask"] is None
    assert [(record["value"], record["pessimistic"], record["label"]) for record in later_unit["measurements"]] == [
        (0, True, "pessimistic, tooling deferred")
    ]
    assert len(global_calls) == 1


def test_should_emit_an_ask_when_a_passing_coverage_run_writes_no_data(tmp_path, monkeypatch):
    repo, target = repo_with_crashing_jest(tmp_path, monkeypatch)
    tool_map = LazyToolMap(repo, head_of(repo), [], SESSION_ID, tmp_path)

    def global_run_that_passes_and_writes_nothing():
        return []

    outcome = measure_coverage_or_ask(target, repo, global_run_that_passes_and_writes_nothing, tool_map)

    assert outcome["ask"]["tool"] == "coverage.py"
    assert outcome["ask"]["metric"] == "coverage"
    assert outcome["ask"]["choices"] == ["fix now", "defer"]
    assert "wrote no coverage data" in outcome["ask"]["reason"]
    assert outcome["measurements"] == []


def test_should_defer_without_asking_when_the_session_entry_point_is_set_and_is_not_the_interactive_cli(
    tmp_path, monkeypatch
):
    repo, target = repo_with_crashing_jest(tmp_path, monkeypatch)
    tool_map = LazyToolMap(repo, head_of(repo), [], SESSION_ID, tmp_path)
    headless_session = {"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}

    def crashing_global_tool():
        raise ToolError("coverage.py is not installed")

    outcome = measure_coverage_or_ask(
        target, repo, crashing_global_tool, tool_map, environ=headless_session
    )

    assert outcome["ask"] is None
    assert [(record["value"], record["pessimistic"], record["label"]) for record in outcome["measurements"]] == [
        (0, True, "pessimistic, tooling deferred")
    ]


def test_should_not_count_a_timeout_under_no_go_headroom_as_the_tool_failing():
    verdicts = iter([False, True, True])
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: next(verdicts), sleep=lambda seconds: None)

    result = policy.run(timing_out_then([None, None, MEASURED_COMPLEXITY], timeouts_seen))

    assert result == MEASURED_COMPLEXITY
    assert len(timeouts_seen) == 3
