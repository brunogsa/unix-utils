import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
MEASURE_SCRIPT = SCRIPTS_DIR / "measure-quality-metrics.py"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture.author@example.com",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture.author@example.com",
}

# The shipped declaration has an empty per_unit list, so a
# per-unit run against it binds nothing. Each test writes the
# declaration it needs.
GO_DECLARATION = """\
excluded_paths: [dist/]
ignored_extensions: [.md, .txt, .json, .yaml, .yml, .toml]
per_unit: [{per_unit}]
languages:
  go:
    extensions: [.go]
    metrics: [{metrics}]
  html:
    extensions: [.html]
    metrics: [size]
  css:
    extensions: [.css]
    metrics: [size]
"""


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True, capture_output=True)


def make_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    for name, text in files.items():
        (repo / name).write_text(text)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "base")
    return repo


def write_declaration(tmp_path, metrics, per_unit=None):
    path = tmp_path / "quality-metrics.yaml"
    names = ", ".join(metrics)
    path.write_text(GO_DECLARATION.format(per_unit=per_unit or names, metrics=names))
    return path


def measure(repo, declaration_path, *arguments):
    result = subprocess.run(
        [sys.executable, str(MEASURE_SCRIPT), *arguments, "--declaration", str(declaration_path)],
        cwd=repo, env=GIT_ENV, capture_output=True, text=True,
    )
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)


def violation_summary(report):
    return sorted(
        (
            (item["function"], item["metric"], item["value"], item["limit"])
            for item in report["violations"]
        ),
        key=str,
    )


def measured_functions(report, metric):
    return sorted(
        item["function"] for item in report["measurements"]
        if item["metric"] == metric and item["scope"] == "function"
    )


def go_function_nested(name, depth):
    """A Go function whose `if` statements nest `depth` levels deep."""
    lines = [f"func {name}(a int) int {{"]
    for level in range(1, depth + 1):
        lines.append("\t" * level + f"if a > {level} {{")
    lines.append("\t" * (depth + 1) + "return 1")
    for level in range(depth, 0, -1):
        lines.append("\t" * level + "}")
    lines += ["\treturn 0", "}", ""]
    return "\n".join(lines)


PACKAGE_LINE = "package main\n\n"


class TestNestingOfTouchedFunctions:
    def test_should_name_the_function_nesting_4_and_limit_3_when_a_unit_adds_a_go_function_nested_4_deep(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"report.go": PACKAGE_LINE + go_function_nested("legacy_parse", 5)})
        (repo / "report.go").write_text(
            PACKAGE_LINE + go_function_nested("legacy_parse", 5) + go_function_nested("build_report", 4)
        )
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure(repo, declaration_path, "--per-unit")

        assert violation_summary(report) == [("build_report", "nesting", 4, 3)]

    def test_should_pass_a_go_function_nested_3_deep(self, tmp_path):
        repo = make_repo(tmp_path, {"report.go": PACKAGE_LINE})
        (repo / "report.go").write_text(PACKAGE_LINE + go_function_nested("build_report", 3))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure(repo, declaration_path, "--per-unit")

        assert violation_summary(report) == []
        assert measured_functions(report, "nesting") == ["build_report"]

    def test_should_not_bind_an_untouched_function_nested_5_deep_a_reindent_only_edit_or_a_detected_rename(
        self, tmp_path
    ):
        deep = go_function_nested("legacy_parse", 5)
        small = "func trim_cell(a int) int {\n\treturn a\n}\n"
        repo = make_repo(
            tmp_path,
            {
                "untouched.go": PACKAGE_LINE + deep + small,
                "reindent.go": PACKAGE_LINE + deep,
                "old_name.go": PACKAGE_LINE + deep,
            },
        )
        (repo / "untouched.go").write_text(
            PACKAGE_LINE + deep + small.replace("return a", "return a + 1")
        )
        (repo / "reindent.go").write_text(
            PACKAGE_LINE + deep.replace("\t", "    ")
        )
        git(repo, "mv", "old_name.go", "new_name.go")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure(repo, declaration_path, "--per-unit")

        assert violation_summary(report) == []
        assert measured_functions(report, "nesting") == ["trim_cell"]
