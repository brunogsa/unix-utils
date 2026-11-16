import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import make_repo, measure_report

COGNITIVE_LIMIT = 15

DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: [cognitive_complexity]
languages:
  python:
    extensions: [.py]
    metrics: [cognitive_complexity]
"""


def write_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION)
    return path


def python_function_with_ifs(name, branch_count):
    """Each flat `if` adds 1 to cognitive complexity."""
    lines = [f"def {name}(a):"]
    for number in range(branch_count):
        lines += [f"    if a == {number}:", f"        return {number}"]
    return "\n".join(lines + ["    return 0", ""])


def cognitive_summary(report):
    return sorted(
        (item["function"], item["value"], item["limit"])
        for item in report["measurements"]
        if item["metric"] == "cognitive_complexity"
    )


def violation_names(report):
    return sorted(item["function"] for item in report["violations"])


def measure_added(tmp_path, file_name, text):
    repo = make_repo(tmp_path, {file_name: ""})
    (repo / file_name).write_text(text)
    return measure_report(repo, write_declaration(tmp_path), "--per-unit")


class TestCognitiveComplexityOfTouchedFunctions:
    def test_should_flag_a_function_at_cognitive_complexity_16_against_limit_15(
        self, tmp_path
    ):
        report = measure_added(tmp_path, "report.py", python_function_with_ifs("route_order", 16))

        assert cognitive_summary(report) == [("route_order", 16, COGNITIVE_LIMIT)]
        assert violation_names(report) == ["route_order"]

    def test_should_pass_a_function_at_cognitive_complexity_15(self, tmp_path):
        report = measure_added(tmp_path, "report.py", python_function_with_ifs("route_order", 15))

        assert cognitive_summary(report) == [("route_order", 15, COGNITIVE_LIMIT)]
        assert violation_names(report) == []
