import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    CART_LCOV,
    SCRIPTS_DIR,
    install_jest_reporting_cart_coverage,
    make_repo,
)

sys.path.insert(0, str(SCRIPTS_DIR))

from types import SimpleNamespace

import pytest

from quality_metrics.sourcing import (
    NoGlobalToolError,
    classify_exit,
    lazy_tool_map_for,
    run_repo_jest,
    source_for,
)
from quality_metrics.tool_map import DETECTOR_RULES_PATH, load_detector_rules
from quality_metrics.tools import ToolError

SESSION_ID = "session-7b1d3e"

JEST_CONFIG = "module.exports = { collectCoverage: true, coverageThreshold: {} };\n"
JEST_REPO_FILES = {"jest.config.js": JEST_CONFIG, "src/cart.js": "module.exports = 1;\n"}
PYTHON_MODULE = "def add(first, second):\n    return first + second\n"


def source_of_coverage(working_directory, map_dir, language):
    rules = load_detector_rules(DETECTOR_RULES_PATH)
    tool_map = lazy_tool_map_for(working_directory, rules, SESSION_ID, map_dir, base_ref="HEAD")
    return source_for("coverage", tool_map, language)


@pytest.mark.parametrize(
    ("metric", "language", "expected_tool"),
    [
        ("size", "bash", "shellmetrics"),
        ("complexity", "bash", "shellmetrics"),
        ("size", "python", "lizard"),
        ("nesting", "ts", "lizard"),
        ("parameters", "go", "lizard"),
        ("complexity", "js", "lizard"),
        ("size", "css", "line count"),
        ("coverage", "js", "c8"),
        ("coverage", "ts", "c8"),
        ("coverage", "python", "coverage.py"),
        ("coverage", "go", "gcov2lcov"),
        ("code_duplication", "bash", "jscpd"),
        ("test_duplication", "python", "jscpd"),
        ("dependency_direction", "js", "dependency-cruiser"),
        ("dependency_direction", "python", "import-linter"),
        ("dependency_direction", "go", "go-arch-lint"),
    ],
)
def test_should_name_the_global_tool_the_metric_module_runs_for_the_language_when_there_is_no_tool_map(
    metric, language, expected_tool
):
    assert source_for(metric, None, language) == {
        "metric": metric,
        "source": {"kind": "global", "tool": expected_tool},
        "side_pr_candidate": None,
    }


@pytest.mark.parametrize(
    ("metric", "language"),
    [
        ("dependency_direction", "bash"),
        ("dependency_direction", "html"),
        ("dependency_direction", "css"),
        ("crap", "python"),
        ("coverage", "bash"),
        ("nesting", "bash"),
    ],
)
def test_should_say_not_measured_with_the_metric_and_language_when_no_global_tool_measures_the_pair(
    metric, language
):
    with pytest.raises(NoGlobalToolError) as raised:
        source_for(metric, None, language)

    assert str(raised.value) == f"not measured: no global {metric} tool for {language}"
    assert isinstance(raised.value, ToolError)


def test_should_name_the_repos_own_tool_as_the_source_when_the_tool_map_lists_one(tmp_path):
    repo = make_repo(tmp_path, {"jest.config.js": JEST_CONFIG, "src/index.js": "module.exports = 1;\n"})

    coverage_source = source_of_coverage(repo, tmp_path, "js")

    assert coverage_source == {
        "metric": "coverage",
        "source": {"kind": "repo", "tool": "jest"},
        "side_pr_candidate": None,
    }


def test_should_measure_function_size_with_the_global_tool_even_when_the_repo_has_an_eslint_config(tmp_path):
    repo = make_repo(tmp_path, {"eslint.config.js": "module.exports = [];\n", "src/index.js": "module.exports = 1;\n"})
    rules = load_detector_rules(DETECTOR_RULES_PATH)
    tool_map = lazy_tool_map_for(repo, rules, SESSION_ID, tmp_path, base_ref="HEAD")

    size_source = source_for("size", tool_map, "js")

    assert size_source["source"] == {"kind": "global", "tool": "lizard"}


def test_should_measure_with_the_global_tool_and_list_a_side_pr_candidate_when_the_repo_lacks_the_tool(tmp_path):
    repo = make_repo(tmp_path, {"calc.py": PYTHON_MODULE})

    coverage_source = source_of_coverage(repo, tmp_path, "python")

    assert coverage_source == {
        "metric": "coverage",
        "source": {"kind": "global", "tool": "coverage.py"},
        "side_pr_candidate": "no repo coverage tool for python",
    }


def test_should_measure_with_the_global_fallback_named_as_the_source_outside_any_git_repo(tmp_path):
    working_directory = tmp_path / "scratch"
    working_directory.mkdir()
    (working_directory / "tool.sh").write_text("#!/bin/bash\necho tool\n")

    coverage_source = source_of_coverage(working_directory, tmp_path, "python")

    assert coverage_source == {
        "metric": "coverage",
        "source": {"kind": "global", "tool": "coverage.py"},
        "side_pr_candidate": None,
    }
    assert list(tmp_path.glob("quality-metrics_*.json")) == []


def test_should_key_repo_jest_hits_by_repo_relative_path_when_the_report_names_the_file_by_absolute_path(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    install_jest_reporting_cart_coverage(
        tmp_path, monkeypatch, CART_LCOV.replace("SF:src/cart.js", f"SF:{repo.resolve()}/src/cart.js")
    )

    run = run_repo_jest(repo)

    assert list(run["hits_by_file"]) == ["src/cart.js"]


def test_should_key_repo_jest_hits_by_repo_relative_path_when_the_repo_is_given_through_a_symlink(
    tmp_path, monkeypatch
):
    real_repo = make_repo(tmp_path, JEST_REPO_FILES)
    linked_repo = tmp_path / "linked-repo"
    linked_repo.symlink_to(real_repo, target_is_directory=True)
    install_jest_reporting_cart_coverage(
        tmp_path, monkeypatch, CART_LCOV.replace("SF:src/cart.js", f"SF:{real_repo.resolve()}/src/cart.js")
    )

    run = run_repo_jest(linked_repo)

    assert list(run["hits_by_file"]) == ["src/cart.js"]


def test_should_keep_a_repo_jest_report_path_outside_the_repo_unchanged_without_raising(
    tmp_path, monkeypatch
):
    repo = make_repo(tmp_path, JEST_REPO_FILES)
    outside_path = "/opt/shared-lib/src/cart.js"
    install_jest_reporting_cart_coverage(
        tmp_path, monkeypatch, CART_LCOV.replace("SF:src/cart.js", f"SF:{outside_path}")
    )

    run = run_repo_jest(repo)

    assert list(run["hits_by_file"]) == [outside_path]


ERRORED_SUITE_WITH_THRESHOLD_MISS = [
    pytest.param(
        "=== 5 passed, 1 error in 0.40s ===\n"
        "FAIL Required test coverage of 90% not reached. Total coverage: 84.00%\n",
        id="pytest-collection-error",
    ),
    pytest.param(
        "Test Suites: 1 failed, 2 passed, 3 total\n"
        "Tests:       12 passed, 12 total\n"
        'Jest: "global" coverage threshold for lines (90%) not met: 84%\n',
        id="jest-suite-failed-to-load",
    ),
]


@pytest.mark.parametrize("output", ERRORED_SUITE_WITH_THRESHOLD_MISS)
def test_should_read_a_run_with_an_errored_suite_as_failed_tests_even_when_the_coverage_threshold_message_is_printed(
    output
):
    result = SimpleNamespace(returncode=1, stdout="", stderr=output)

    assert classify_exit(result) == "failed_tests"



