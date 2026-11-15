import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

from quality_metrics.functions import is_over_limit
from quality_metrics.sourcing import (
    lazy_tool_map_for,
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


