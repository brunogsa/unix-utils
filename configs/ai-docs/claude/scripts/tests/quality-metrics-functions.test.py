import importlib
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


def go_function_with_lines(name, code_lines):
    """A Go function of exactly `code_lines` non-blank, non-comment lines.

    A blank line and a comment sit inside the body to pin that neither counts.
    """
    body_statements = code_lines - 4
    lines = [f"func {name}() int {{", "\ttotal := 0", "", "\t// comment lines do not count"]
    lines += [f"\ttotal += {number}" for number in range(1, body_statements + 1)]
    lines += ["\treturn total", "}", ""]
    return "\n".join(lines)


def go_function_with_parameters(name, parameter_count):
    parameters = ", ".join(f"p{number} int" for number in range(1, parameter_count + 1))
    return f"func {name}({parameters}) int {{\n\treturn p1\n}}\n"


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

# --- end of nesting tests ---


class TestSizeLimits:
    def test_should_pass_30_lines_5_parameters_and_a_300_line_file_and_flag_31_6_and_301(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"report.go": PACKAGE_LINE})
        functions_text = "".join(
            [
                go_function_with_lines("lines_30", 30),
                go_function_with_lines("lines_31", 31),
                go_function_with_parameters("parameters_5", 5),
                go_function_with_parameters("parameters_6", 6),
            ]
        )
        (repo / "report.go").write_text(PACKAGE_LINE + functions_text)
        file_at_limit = PACKAGE_LINE + "// header comment\n\n" + "".join(
            f"var at_limit_{number} = {number}\n" for number in range(1, 300)
        )
        file_over_limit = PACKAGE_LINE + "".join(
            f"var over_limit_{number} = {number}\n" for number in range(1, 301)
        )
        (repo / "at_limit.go").write_text(file_at_limit)
        (repo / "over_limit.go").write_text(file_over_limit)
        declaration_path = write_declaration(tmp_path, ["size", "parameters"])

        function_report = measure(repo, declaration_path, "--per-unit")
        file_report = measure(repo, declaration_path, "--files", "at_limit.go", "over_limit.go")

        function_violations = [
            entry for entry in violation_summary(function_report) if entry[0] is not None
        ]
        assert function_violations == [
            ("lines_31", "size", 31, 30),
            ("parameters_6", "parameters", 6, 5),
        ]
        assert [
            (item["file"], item["value"], item["limit"])
            for item in file_report["violations"]
        ] == [("over_limit.go", 301, 300)]
        assert [
            item["value"] for item in file_report["measurements"] if item["file"] == "at_limit.go"
        ] == [300]

    def test_should_count_html_and_css_size_as_non_blank_non_comment_lines(self, tmp_path):
        repo = make_repo(tmp_path, {"README.txt": "base\n"})
        css_filler = "\n/* one-line comment */\n/* multi-line\n   comment */\n\n"
        html_filler = "\n<!-- one-line comment -->\n<!-- multi-line\n     comment -->\n\n"
        (repo / "at_limit.css").write_text(
            css_filler + "".join(f".rule-{n} {{ color: red; }}\n" for n in range(300))
        )
        (repo / "over_limit.css").write_text(
            css_filler + "".join(f".rule-{n} {{ color: red; }}\n" for n in range(301))
        )
        (repo / "at_limit.html").write_text(
            html_filler + "".join(f"<p>paragraph {n}</p>\n" for n in range(300))
        )
        (repo / "over_limit.html").write_text(
            html_filler + "".join(f"<p>paragraph {n}</p>\n" for n in range(301))
        )
        declaration_path = write_declaration(tmp_path, ["size"])
        names = ["at_limit.css", "over_limit.css", "at_limit.html", "over_limit.html"]

        report = measure(repo, declaration_path, "--files", *names)

        assert {item["file"]: item["value"] for item in report["measurements"]} == {
            "at_limit.css": 300,
            "over_limit.css": 301,
            "at_limit.html": 300,
            "over_limit.html": 301,
        }
        assert sorted(item["file"] for item in report["violations"]) == [
            "over_limit.css",
            "over_limit.html",
        ]

# --- end of size tests ---


class TestBashComplexity:
    def test_should_pin_the_complexity_shellmetrics_reads_for_a_bash_function_holding_a_case_statement(
        self, tmp_path
    ):
        # shellmetrics counts a four-branch case as 3 added
        # paths, so it reads complexity 4 where a hand count
        # of 1 + 4 branches gives 5.
        script = tmp_path / "pick.sh"
        script.write_text(
            'pick() {\n  case "$1" in\n    a) echo a ;;\n    b) echo b ;;\n'
            "    c) echo c ;;\n    *) echo other ;;\n  esac\n}\n"
        )
        functions = importlib.import_module("quality_metrics.functions")

        measures = functions.measure_functions(script, "bash")

        assert {measure_.name: measure_.complexity for measure_ in measures} == {"pick": 4}
