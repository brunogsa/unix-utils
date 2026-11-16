import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import SCRIPTS_DIR, make_repo

sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from quality_metrics.sourcing import lazy_tool_map_for, source_for
from quality_metrics.tool_map import DETECTOR_RULES_PATH, load_detector_rules

SESSION_ID = "session-9d2f40"

JEST_CONFIG = "module.exports = { collectCoverage: true, coverageThreshold: {} };\n"
PYTHON_MODULE = "def add(first, second):\n    return first + second\n"


@pytest.mark.parametrize(
    ("repo_files", "language", "global_tool"),
    [
        ({"jest.config.js": JEST_CONFIG, "calc.py": PYTHON_MODULE}, "python", "coverage.py"),
        ({".coveragerc": "[run]\n", "src/cart.js": "// covered\n"}, "js", "c8"),
    ],
    ids=["python-target-in-a-repo-with-only-jest", "js-target-in-a-repo-with-only-pytest-cov"],
)
def test_should_measure_with_the_global_tool_and_name_the_language_when_the_repo_tool_measures_another_language(
    tmp_path, repo_files, language, global_tool
):
    repo = make_repo(tmp_path, repo_files)
    rules = load_detector_rules(DETECTOR_RULES_PATH)
    tool_map = lazy_tool_map_for(repo, rules, SESSION_ID, tmp_path, base_ref="HEAD")

    coverage_source = source_for("coverage", tool_map, language)

    assert coverage_source == {
        "metric": "coverage",
        "source": {"kind": "global", "tool": global_tool},
        "side_pr_candidate": f"no repo coverage tool for {language}",
    }


def test_should_match_no_language_for_a_tool_map_entry_written_before_entries_carried_languages():
    entry_without_languages = {
        "tools": [{"tool": "jest", "metric": "coverage", "config": "jest.config.js"}],
        "deferred": [],
    }
    tool_map = SimpleNamespace(entry=lambda: entry_without_languages)

    coverage_source = source_for("coverage", tool_map, "js")

    assert coverage_source["source"] == {"kind": "global", "tool": "c8"}
    assert coverage_source["side_pr_candidate"] == "no repo coverage tool for js"
