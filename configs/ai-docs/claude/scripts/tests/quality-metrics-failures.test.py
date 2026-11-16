import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    JEST_CRASH_STUB,
    SCRIPTS_DIR,
    coverage_records_of,
    head_of,
    install_global_collector,
    install_stub_tool,
    make_repo,
)

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.failures import (
    HEADROOM_MAX_WAIT_SECONDS,
    HEADROOM_POLL_SECONDS,
    TOOL_TIMEOUT_SECONDS,
    TimeoutPolicy,
    ToolTimedOutTwice,
    ask_unless_deferred,
    deferred_crap_measurements,
    deferred_measurement,
    holds_commit,
    machine_has_headroom,
    measure_language_entry_or_ask,
)
from quality_metrics.declaration import load_declaration
from quality_metrics.functions import FunctionMeasure, is_over_limit, measurement
from quality_metrics.size import FUNCTION_LINES_LIMIT
from quality_metrics.collection import CoverageRun
from quality_metrics.tool_map import DETECTOR_RULES_PATH, LazyToolMap, load_detector_rules, record_deferred_tool
from quality_metrics.tools import ToolError
from quality_metrics.touched import Target

MEASURED_COMPLEXITY = {"metric": "complexity", "value": 7}

SESSION_ID = "session-4c9e21"
INTERACTIVE_SESSION = {"CLAUDE_CODE_ENTRYPOINT": "cli"}


def timing_out_then(outcomes, timeouts_seen):
    """A tool attempt: raises a timeout for each None, else
    returns the outcome."""
    remaining = list(outcomes)

    def attempt(timeout_seconds):
        timeouts_seen.append(timeout_seconds)
        outcome = remaining.pop(0)
        if outcome is None:
            raise subprocess.TimeoutExpired(["lizard"], timeout_seconds)
        return outcome

    return attempt


def repo_with_crashing_jest(tmp_path, monkeypatch):
    """A repo whose jest dies on an internal error, and its one
    JS target."""
    repo = make_repo(tmp_path, {"jest.config.js": "module.exports = {};\n", "src/cart.js": "// covered\n"})
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_CRASH_STUB)
    return repo, Target(repo / "src/cart.js", "js", None, repo_path="src/cart.js")


def lazy_tool_map_with_detectors(repo, map_dir):
    """The repo's tool map under the real detector rules, so a
    jest config lists jest."""
    return LazyToolMap(repo, head_of(repo), load_detector_rules(DETECTOR_RULES_PATH), SESSION_ID, map_dir)


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


def test_should_list_every_touched_function_as_a_pessimistic_crap_violation_when_complexity_is_deferred():
    target = Target(Path("src/rows.js"), "javascript", {3, 14})
    parse_row = FunctionMeasure("parseRow", 1, 10, 9, 4, 2, 2)
    format_row = FunctionMeasure("formatRow", 12, 20, 8, 3, 1, 1)

    records = deferred_crap_measurements(target, [parse_row, format_row])

    assert [(record["function"], record["metric"]) for record in records] == [
        ("parseRow", "crap"),
        ("formatRow", "crap"),
    ]
    assert all(is_over_limit(record) for record in records)
    assert {record["label"] for record in records} == {"pessimistic, tooling deferred"}
    assert all(record["pessimistic"] is True for record in records)
    assert holds_commit(records) is False


def python_only_declaration(tmp_path):
    """A declaration whose only language entry is Python."""
    declaration_path = tmp_path / "quality-metrics.yaml"
    declaration_path.write_text(
        "excluded_paths: []\n"
        "ignored_extensions: [.md]\n"
        "per_unit: []\n"
        "languages:\n"
        "  python:\n"
        "    extensions: [.py]\n"
        "    metrics: [crap, size]\n"
    )
    return load_declaration(declaration_path)


def test_should_list_a_file_with_no_language_entry_as_not_measured_and_scored_pessimistically_after_an_ask(
    tmp_path,
):
    repo = make_repo(tmp_path, {"lib/convert.rb": "def convert(value)\n  value.to_s\nend\n"})
    base_sha = head_of(repo)
    tool_map = LazyToolMap(repo, base_sha, [], SESSION_ID, tmp_path)
    declaration = python_only_declaration(tmp_path)

    before_defer = measure_language_entry_or_ask(
        declaration, "lib/convert.rb", tool_map, environ=INTERACTIVE_SESSION
    )
    record_deferred_tool(repo, base_sha, "language entry (.rb)", SESSION_ID, tmp_path)
    after_defer = measure_language_entry_or_ask(
        declaration, "lib/convert.rb", tool_map, environ=INTERACTIVE_SESSION
    )

    assert before_defer["ask"]["tool"] == "language entry (.rb)"
    assert before_defer["ask"]["choices"] == ["fix now", "defer"]
    assert "no language entry claims 'lib/convert.rb'" in before_defer["ask"]["reason"]
    assert before_defer["measurements"] == []
    assert after_defer["ask"] is None
    assert len(after_defer["measurements"]) == 1
    unmeasured = after_defer["measurements"][0]
    assert unmeasured["file"] == "lib/convert.rb"
    assert unmeasured["status"] == "not measured: no language entry"
    assert unmeasured["label"] == "pessimistic, tooling deferred"
    assert unmeasured["pessimistic"] is True
    assert unmeasured["value"] is None
    assert holds_commit(after_defer["measurements"]) is False


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
    assert other_tool_ask is not None
    assert other_tool_ask["tool"] == "jscpd"


def test_should_give_up_and_run_no_third_attempt_when_both_attempts_time_out():
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: True, sleep=lambda seconds: None)

    with pytest.raises(ToolTimedOutTwice):
        policy.run(timing_out_then([None, None, MEASURED_COMPLEXITY], timeouts_seen))

    assert timeouts_seen == [TOOL_TIMEOUT_SECONDS, TOOL_TIMEOUT_SECONDS]


def test_should_emit_an_ask_for_a_missing_or_crashing_global_tool_and_score_coverage_0_percent_labelled_pessimistic_on_defer(
    tmp_path, monkeypatch
):
    repo, target = repo_with_crashing_jest(tmp_path, monkeypatch)
    base_sha = head_of(repo)
    global_calls = []
    install_global_collector(
        monkeypatch, global_calls, error=ToolError("c8 crashed with a traceback")
    )
    first_run = CoverageRun(
        repo, lazy_tool_map_with_detectors(repo, tmp_path), environ=INTERACTIVE_SESSION
    )

    first_records = coverage_records_of(tmp_path, target, first_run)
    record_deferred_tool(repo, base_sha, "c8", SESSION_ID, tmp_path)
    later_run = CoverageRun(
        repo, lazy_tool_map_with_detectors(repo, tmp_path), environ=INTERACTIVE_SESSION
    )
    later_records = coverage_records_of(tmp_path, target, later_run)

    assert first_run.asks[0]["tool"] == "c8"
    assert first_run.asks[0]["metric"] == "coverage"
    assert "c8 crashed" in first_run.asks[0]["reason"]
    assert later_run.asks == []
    for records in (first_records, later_records):
        assert [(record["value"], record["pessimistic"], record["label"]) for record in records] == [
            (0, True, "pessimistic, tooling deferred")
        ]
    assert len(global_calls) == 1


def test_should_emit_an_ask_when_a_passing_global_coverage_run_writes_no_data(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, {
        "jest.config.js": "module.exports = {};\n",
        "package.json": '{"scripts": {"test": "node --test"}}\n',
        "src/cart.js": "// covered\n",
    })
    target = Target(repo / "src/cart.js", "js", None, repo_path="src/cart.js")
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_CRASH_STUB)
    install_stub_tool(tmp_path, monkeypatch, "c8", "#!/bin/sh\nexit 0\n")
    coverage_run = CoverageRun(
        repo, lazy_tool_map_with_detectors(repo, tmp_path), environ=INTERACTIVE_SESSION
    )

    records = coverage_records_of(tmp_path, target, coverage_run)

    assert coverage_run.asks[0]["tool"] == "c8"
    assert coverage_run.asks[0]["metric"] == "coverage"
    assert coverage_run.asks[0]["choices"] == ["fix now", "defer"]
    assert "wrote no coverage data" in coverage_run.asks[0]["reason"]
    assert [(record["value"], record["pessimistic"]) for record in records] == [(0, True)]


def test_should_ask_about_the_global_tool_when_the_repo_jest_is_not_installed_and_the_global_tool_crashes(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, {"jest.config.js": "module.exports = {};\n", "src/cart.js": "// covered\n"})
    target = Target(repo / "src/cart.js", "js", None, repo_path="src/cart.js")
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", "/bin"]))
    install_global_collector(
        monkeypatch, [], error=ToolError("c8 crashed with a traceback")
    )
    coverage_run = CoverageRun(
        repo, lazy_tool_map_with_detectors(repo, tmp_path), environ=INTERACTIVE_SESSION
    )

    coverage_records_of(tmp_path, target, coverage_run)

    assert coverage_run.asks[0]["tool"] == "c8"
    assert "c8 crashed" in coverage_run.asks[0]["reason"]
    assert coverage_run.sources[0]["side_pr_candidate"] == "repo jest crashed"


def test_should_defer_without_asking_when_the_session_entry_point_is_set_and_is_not_the_interactive_cli(
    tmp_path, monkeypatch
):
    repo, target = repo_with_crashing_jest(tmp_path, monkeypatch)
    install_global_collector(monkeypatch, [], error=ToolError("coverage.py is not installed"))
    coverage_run = CoverageRun(
        repo,
        lazy_tool_map_with_detectors(repo, tmp_path),
        environ={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"},
    )

    records = coverage_records_of(tmp_path, target, coverage_run)

    assert coverage_run.asks == []
    assert [(record["value"], record["pessimistic"], record["label"]) for record in records] == [
        (0, True, "pessimistic, tooling deferred")
    ]


def test_should_not_count_a_timeout_under_no_go_headroom_as_the_tool_failing():
    verdicts = iter([False, True, True])
    timeouts_seen = []
    policy = TimeoutPolicy(headroom_is_go=lambda: next(verdicts), sleep=lambda seconds: None)

    result = policy.run(timing_out_then([None, None, MEASURED_COMPLEXITY], timeouts_seen))

    assert result == MEASURED_COMPLEXITY
    assert len(timeouts_seen) == 3
