import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics import sourcing
from quality_metrics.coverage import coverage_measurement
from quality_metrics.functions import is_over_limit
from quality_metrics.sourcing import (
    lazy_tool_map_for,
    measure_coverage_with_repo_tool,
    measure_function_size_with_repo_tool,
    source_for,
)
from quality_metrics.tool_map import load_detector_rules
from quality_metrics.touched import Target

DETECTOR_RULES = SCRIPTS_DIR / "quality-metrics-detectors.yaml"
SESSION_ID = "session-7b1d3e"

JEST_CONFIG = "module.exports = { collectCoverage: true, coverageThreshold: {} };\n"
PYTHON_MODULE = "def add(first, second):\n    return first + second\n"


def source_of_coverage(working_directory, map_dir):
    rules = load_detector_rules(DETECTOR_RULES)
    tool_map = lazy_tool_map_for(working_directory, rules, SESSION_ID, map_dir, base_ref="HEAD")
    return source_for("coverage", tool_map)


def test_should_name_the_repos_own_tool_as_the_source_when_the_tool_map_lists_one(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG, "src/index.js": "module.exports = 1;\n"})

    sourcing = source_of_coverage(repo, tmp_path)

    assert sourcing == {
        "metric": "coverage",
        "source": {"kind": "repo", "tool": "jest"},
        "side_pr_candidate": None,
    }


def test_should_measure_with_the_global_tool_and_list_a_side_pr_candidate_when_the_repo_lacks_the_tool(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": PYTHON_MODULE})

    sourcing = source_of_coverage(repo, tmp_path)

    assert sourcing == {
        "metric": "coverage",
        "source": {"kind": "global", "tool": "coverage.py"},
        "side_pr_candidate": "no repo coverage tool",
    }


def test_should_measure_with_the_global_fallback_named_as_the_source_outside_any_git_repo(tmp_path):
    working_directory = tmp_path / "scratch"
    working_directory.mkdir()
    (working_directory / "tool.sh").write_text("#!/bin/bash\necho tool\n")

    sourcing = source_of_coverage(working_directory, tmp_path)

    assert sourcing == {
        "metric": "coverage",
        "source": {"kind": "global", "tool": "coverage.py"},
        "side_pr_candidate": None,
    }
    assert list(tmp_path.glob("quality-metrics_*.json")) == []


def install_stub_tool(tmp_path, monkeypatch, name, script):
    """Put an executable `name` first on PATH, standing in for a repo tool."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / name
    stub.write_text(script)
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


# Reports its findings only when asked for every function
# (a zero line allowance), as the repo's limit of 60 would
# not.
ESLINT_STUB = """#!/bin/bash
case "$*" in
  *"max-lines-per-function: [error, {max: 0}]"*)
    echo '[{"filePath":"src/cart.js","messages":[{"ruleId":"max-lines-per-function","message":"Function '"'"'applyDiscount'"'"' has too many lines (45). Maximum allowed is 0.","line":1,"endLine":45}]}]'
    exit 1;;
  *) echo '[{"filePath":"src/cart.js","messages":[]}]'; exit 0;;
esac
"""


# Writes an lcov report where it is told to, then fails the
# repo's own 95% threshold the way jest words it.
JEST_STUB = """#!/bin/bash
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
done
cp "$LCOV_FIXTURE" "$report_dir/lcov.info"
echo 'Jest: "global" coverage threshold for lines (95%) not met: 92%' >&2
exit 1
"""

# 25 coverable lines, 23 run: 92% changed-line coverage.
CART_LCOV = "SF:src/cart.js\n" + "".join(
    f"DA:{line},{1 if line <= 23 else 0}\n" for line in range(1, 26)
) + "end_of_record\n"


def test_should_flag_a_45_line_function_against_the_30_line_limit_when_the_repo_linter_allows_60(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, {"src/cart.js": "// 45-line function\n"})
    install_stub_tool(tmp_path, monkeypatch, "eslint", ESLINT_STUB)
    target = Target(repo / "src/cart.js", "javascript", {10})

    records = measure_function_size_with_repo_tool(target, repo)

    assert [(record["function"], record["value"], record["limit"]) for record in records] == [
        ("applyDiscount", 45, 30)
    ]
    assert is_over_limit(records[0])


def test_should_read_measurements_as_valid_when_a_repo_tool_exits_non_zero_on_its_own_threshold(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, {"src/cart.js": "// covered 92%\n"})
    lcov_fixture = tmp_path / "cart.lcov"
    lcov_fixture.write_text(CART_LCOV)
    monkeypatch.setenv("LCOV_FIXTURE", str(lcov_fixture))
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_STUB)
    target = Target(repo / "src/cart.js", "javascript", None)

    outcome = measure_coverage_with_repo_tool(target, repo)

    assert outcome["exit_class"] == "repo_threshold"
    assert [record["value"] for record in outcome["measurements"]] == [92]
    assert not is_over_limit(outcome["measurements"][0])


# A jest dying on an internal error: a stack trace, no report.
JEST_CRASH_STUB = """#!/bin/bash
echo "TypeError: Cannot read properties of undefined (reading 'config')" >&2
echo "    at Object.run (/repo/node_modules/jest-cli/build/run.js:31:18)" >&2
exit 1
"""

# Logs each attempt in $ATTEMPT_LOG, then hangs past a timeout.
# `exec` so a kill lands on sleep itself, not a parent shell.
JEST_HANG_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
exec sleep 5
"""

# Exits cleanly but never writes the lcov report.
JEST_NO_REPORT_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
exit 0
"""

# Jest's own words for a run with failing tests.
JEST_FAILED_TESTS_STUB = """#!/bin/bash
echo "FAIL src/cart.test.js" >&2
echo "Tests:       2 failed, 10 passed, 12 total" >&2
exit 1
"""

GLOBAL_COVERAGE_PERCENT = 100


def measure_globally_for(target, calls):
    """Stands in for the global coverage tool; records each call."""
    def measure_globally():
        calls.append(target.path)
        return [coverage_measurement(target, {1: 1, 2: 1})]
    return measure_globally


def test_should_classify_a_crash_from_the_tool_output_and_fall_through_to_the_global_tool_with_a_side_pr_candidate(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, {"src/cart.js": "// covered\n"})
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_CRASH_STUB)
    target = Target(repo / "src/cart.js", "javascript", None)
    global_calls = []

    outcome = sourcing.measure_coverage(target, repo, measure_globally_for(target, global_calls))

    assert outcome["exit_class"] == "crash"
    assert outcome["source"] == {"kind": "global", "tool": "coverage.py"}
    assert [record["value"] for record in outcome["measurements"]] == [GLOBAL_COVERAGE_PERCENT]
    assert outcome["side_pr_candidate"] == "repo jest crashed"
    assert len(global_calls) == 1


@pytest.mark.parametrize(
    ("stub", "expected_exit_class", "expected_candidate", "expected_attempts"),
    [
        (JEST_HANG_STUB, "timeout", "repo jest timed out twice", 2),
        (JEST_NO_REPORT_STUB, "no_coverage_data", "repo jest wrote no coverage data", 1),
    ],
    ids=["timeout-on-both-attempts", "no-coverage-report-written"],
)
def test_should_fall_through_to_the_global_tool_when_the_repo_tool_times_out_twice_or_writes_no_coverage_data(
    tmp_path, monkeypatch, stub, expected_exit_class, expected_candidate, expected_attempts
):
    repo = make_repo(tmp_path, {"src/cart.js": "// covered\n"})
    attempt_log = tmp_path / "attempts.log"
    monkeypatch.setenv("ATTEMPT_LOG", str(attempt_log))
    install_stub_tool(tmp_path, monkeypatch, "jest", stub)
    target = Target(repo / "src/cart.js", "javascript", None)
    global_calls = []

    outcome = sourcing.measure_coverage(
        target, repo, measure_globally_for(target, global_calls), timeout_seconds=0.5
    )

    assert outcome["exit_class"] == expected_exit_class
    assert outcome["source"] == {"kind": "global", "tool": "coverage.py"}
    assert [record["value"] for record in outcome["measurements"]] == [GLOBAL_COVERAGE_PERCENT]
    assert outcome["side_pr_candidate"] == expected_candidate
    assert len(attempt_log.read_text().splitlines()) == expected_attempts
    assert len(global_calls) == 1


def test_should_classify_a_non_zero_test_run_reporting_failed_tests_as_a_red_build_not_a_tooling_gap(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, {"src/cart.js": "// covered\n"})
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_FAILED_TESTS_STUB)
    target = Target(repo / "src/cart.js", "javascript", None)
    global_calls = []

    outcome = sourcing.measure_coverage(target, repo, measure_globally_for(target, global_calls))

    assert outcome["exit_class"] == "failed_tests"
    assert outcome["red_build"] is True
    assert outcome["source"] == {"kind": "repo", "tool": "jest"}
    assert outcome["side_pr_candidate"] is None
    assert outcome["measurements"] == []
    assert global_calls == []



