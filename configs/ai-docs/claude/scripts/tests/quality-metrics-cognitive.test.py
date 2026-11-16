import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics import declaration
from quality_metrics_support import (
    SHIPPED_DECLARATION, make_repo, measure_report, run_measure,
)

COGNITIVE_LIMIT = 15

DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: [cognitive_complexity]
languages:
  python:
    extensions: [.py]
    metrics: [cognitive_complexity]
  ts:
    extensions: [.ts]
    metrics: [cognitive_complexity]
  bash:
    extensions: [.sh]
    metrics: [{bash_metrics}]
"""


def write_declaration(tmp_path, bash_metrics="size"):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION.format(bash_metrics=bash_metrics))
    return path


def python_function_with_ifs(name, branch_count):
    """Each flat `if` adds 1 to cognitive complexity."""
    lines = [f"def {name}(a):"]
    for number in range(branch_count):
        lines += [f"    if a == {number}:", f"        return {number}"]
    return "\n".join(lines + ["    return 0", ""])


def typescript_function_with_ifs(name, branch_count):
    lines = [f"function {name}(a: number): number {{"]
    for number in range(branch_count):
        lines += [f"  if (a === {number}) {{", f"    return {number};", "  }"]
    return "\n".join(lines + ["  return 0;", "}", ""])


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


@pytest.mark.parametrize(
    "file_name, build",
    [
        ("report.py", python_function_with_ifs),
        ("report.ts", typescript_function_with_ifs),
    ],
    ids=["python", "typescript"],
)
class TestCognitiveComplexityOfTouchedFunctions:
    def test_should_flag_a_function_at_cognitive_complexity_16_against_limit_15(
        self, tmp_path, file_name, build
    ):
        report = measure_added(tmp_path, file_name, build("route_order", 16))

        assert cognitive_summary(report) == [("route_order", 16, COGNITIVE_LIMIT)]
        assert violation_names(report) == ["route_order"]

    def test_should_pass_a_function_at_cognitive_complexity_15(
        self, tmp_path, file_name, build
    ):
        report = measure_added(tmp_path, file_name, build("route_order", 15))

        assert cognitive_summary(report) == [("route_order", 15, COGNITIVE_LIMIT)]
        assert violation_names(report) == []


class TestShippedDeclaration:
    @pytest.mark.parametrize("language", ["js", "ts", "python", "go"])
    def test_should_declare_cognitive_complexity_for_every_language_lizard_measures(
        self, language
    ):
        loaded = declaration.load_declaration(SHIPPED_DECLARATION)

        assert "cognitive_complexity" in loaded.languages[language].metrics

    def test_should_not_declare_cognitive_complexity_for_bash(self):
        loaded = declaration.load_declaration(SHIPPED_DECLARATION)

        assert "cognitive_complexity" not in loaded.languages["bash"].metrics

    def test_should_fail_the_run_naming_the_metric_when_a_bash_entry_declares_cognitive_complexity(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"run.sh": "#!/bin/bash\n"})
        (repo / "run.sh").write_text("#!/bin/bash\nrun() {\n  echo 1\n}\n")
        declaration_path = write_declaration(tmp_path, "cognitive_complexity")

        result = run_measure(repo, declaration_path, "--per-unit")

        assert result.returncode == 2
        assert "cannot measure cognitive_complexity" in result.stderr
