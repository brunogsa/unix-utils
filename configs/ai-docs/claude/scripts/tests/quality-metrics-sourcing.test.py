import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.sourcing import lazy_tool_map_for, source_for
from quality_metrics.tool_map import load_detector_rules

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

