import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    commit_all, git, head_of, make_repo, measure_report, run_measure,
)

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
  bash:
    extensions: [.sh]
    metrics: [size]
"""


def write_declaration(tmp_path, metrics, per_unit=None):
    path = tmp_path / "quality-metrics.yaml"
    names = ", ".join(metrics)
    path.write_text(GO_DECLARATION.format(per_unit=per_unit or names, metrics=names))
    return path


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
    """A Go function whose `if` statements nest `depth` levels
    deep."""
    lines = [f"func {name}(a int) int {{"]
    for level in range(1, depth + 1):
        lines.append("\t" * level + f"if a > {level} {{")
    lines.append("\t" * (depth + 1) + "return 1")
    for level in range(depth, 0, -1):
        lines.append("\t" * level + "}")
    lines += ["\treturn 0", "}", ""]
    return "\n".join(lines)


def go_function_with_lines(name, code_lines):
    """A Go function of exactly `code_lines` non-blank,
    non-comment lines.

    A blank line and a comment sit inside the body to pin that
    neither counts.
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

        report = measure_report(repo, declaration_path, "--per-unit")

        assert violation_summary(report) == [("build_report", "nesting", 4, 3)]

    def test_should_pass_a_go_function_nested_3_deep(self, tmp_path):
        repo = make_repo(tmp_path, {"report.go": PACKAGE_LINE})
        (repo / "report.go").write_text(PACKAGE_LINE + go_function_nested("build_report", 3))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--per-unit")

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

        report = measure_report(repo, declaration_path, "--per-unit")

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

        function_report = measure_report(repo, declaration_path, "--per-unit")
        file_report = measure_report(repo, declaration_path, "--files", "at_limit.go", "over_limit.go")

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

        report = measure_report(repo, declaration_path, "--files", *names)

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

    def test_should_not_count_scss_double_slash_comment_lines_but_keep_slashes_in_urls_and_strings(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"README.txt": "base\n"})
        scss_text = (
            "// first comment\n"
            ".a { color: red; }\n"
            "// second comment\n"
            "// third comment\n"
            ".b { color: blue; } // trailing comment\n"
            '.c { content: "// not a comment"; }\n'
            ".d { background: url(http://x/y.png); }\n"
        )
        (repo / "styles.scss").write_text(scss_text)
        (repo / "plain.css").write_text(
            "// not a comment in css\n.a { color: red; }\n"
        )
        declaration_path = write_declaration(tmp_path, ["size"])
        declaration_path.write_text(
            declaration_path.read_text().replace("[.css]", "[.css, .scss]")
        )

        report = measure_report(
            repo, declaration_path, "--files", "styles.scss", "plain.css"
        )

        assert {item["file"]: item["value"] for item in report["measurements"]} == {
            "styles.scss": 4,
            "plain.css": 2,
        }

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


def bash_function_with_statements(name, statements, with_heredoc=False):
    """A Bash function of exactly `statements` logical lines.

    The heredoc form opens with one statement whose body holds
    a bare `}` line and a quoted brace, which a brace-counting
    reader takes for the end of the function.
    """
    lines = [f"{name}() {{"]
    remaining = statements
    if with_heredoc:
        lines += ["  cat <<TEXT", "}", "TEXT", '  echo "}"']
        remaining -= 2
    lines += [f"  total=$((total + {number}))" for number in range(1, remaining + 1)]
    lines.append("}")
    return "\n".join(lines) + "\n"


class TestReviewMode:
    def test_should_measure_only_functions_the_diff_changes_adds_or_removes_in_review_mode(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path,
            {
                "report.go": PACKAGE_LINE
                + go_function_nested("untouched_deep", 5)
                + go_function_nested("edited_deep", 5)
                + go_function_nested("removed_deep", 5)
            },
        )
        base = head_of(repo)
        (repo / "report.go").write_text(
            PACKAGE_LINE
            + go_function_nested("untouched_deep", 5)
            + go_function_nested("edited_deep", 5).replace("return 0", "return 2")
            + go_function_nested("added_deep", 4)
        )
        commit_all(repo, "change the report")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert measured_functions(report, "nesting") == ["added_deep", "edited_deep"]
        assert violation_summary(report) == [
            ("added_deep", "nesting", 4, 3),
            ("edited_deep", "nesting", 5, 3),
        ]

    def test_should_list_a_removed_over_limit_function_as_resolved_with_its_last_score_and_no_violation(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path,
            {"report.go": PACKAGE_LINE + go_function_nested("legacy_parse", 5)
             + go_function_nested("keep_small", 1)},
        )
        base = head_of(repo)
        (repo / "report.go").write_text(PACKAGE_LINE + go_function_nested("keep_small", 1))
        commit_all(repo, "drop the legacy parser")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert [
            (item["file"], item["function"], item["metric"], item["value"], item["limit"])
            for item in report["resolved"]
        ] == [("report.go", "legacy_parse", "nesting", 5, 3)]
        assert report["violations"] == []

    def test_should_leave_a_removed_function_under_every_limit_out_of_the_resolved_list(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path,
            {"report.go": PACKAGE_LINE + go_function_nested("trim_cell", 1)
             + go_function_nested("keep_small", 1)},
        )
        base = head_of(repo)
        (repo / "report.go").write_text(PACKAGE_LINE + go_function_nested("keep_small", 1))
        commit_all(repo, "drop the small helper")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert report["resolved"] == []

    def test_should_not_list_as_resolved_an_over_limit_function_the_base_branch_added_after_the_fork(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path, {"report.go": PACKAGE_LINE + go_function_nested("shared_small", 1)}
        )
        git(repo, "checkout", "--quiet", "-b", "feature")
        git(repo, "checkout", "--quiet", "main")
        (repo / "report.go").write_text(
            PACKAGE_LINE + go_function_nested("shared_small", 1)
            + go_function_nested("main_only_deep", 5)
        )
        commit_all(repo, "main adds a deep function after the fork")
        git(repo, "checkout", "--quiet", "feature")
        (repo / "report.go").write_text(
            PACKAGE_LINE + go_function_nested("shared_small", 1).replace("return 0", "return 2")
        )
        commit_all(repo, "feature edits the report")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", "main...HEAD")

        assert report["resolved"] == []

    def test_should_still_measure_a_file_the_base_branch_deleted_after_the_fork_and_the_branch_modified(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path, {"gone.go": PACKAGE_LINE + go_function_nested("edited_deep", 1)}
        )
        git(repo, "checkout", "--quiet", "-b", "feature")
        git(repo, "checkout", "--quiet", "main")
        git(repo, "rm", "--quiet", "gone.go")
        commit_all(repo, "main deletes the file after the fork")
        git(repo, "checkout", "--quiet", "feature")
        (repo / "gone.go").write_text(PACKAGE_LINE + go_function_nested("edited_deep", 5))
        commit_all(repo, "feature deepens the function")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", "main...HEAD")

        assert violation_summary(report) == [("edited_deep", "nesting", 5, 3)]
        assert report["resolved"] == []

    def test_should_ignore_an_uncommitted_edit_when_measuring_the_committed_range(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path, {"report.go": PACKAGE_LINE + go_function_nested("edited_small", 1)}
        )
        base = head_of(repo)
        (repo / "report.go").write_text(
            PACKAGE_LINE + go_function_nested("edited_small", 1).replace("return 0", "return 2")
        )
        commit_all(repo, "change the committed function body")
        (repo / "report.go").write_text(PACKAGE_LINE + go_function_nested("edited_small", 6))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert violation_summary(report) == []
        assert [item["value"] for item in report["measurements"]
                if item["metric"] == "nesting"] == [1]

# --- end of review mode tests ---


class TestDiffOutputVariants:
    @pytest.mark.parametrize("config_key", ["diff.mnemonicPrefix", "diff.noprefix"])
    def test_should_still_find_an_over_limit_edit_when_git_prints_mnemonic_or_no_path_prefixes(
        self, tmp_path, config_key
    ):
        repo = make_repo(tmp_path, {"r.go": PACKAGE_LINE + go_function_nested("edited_deep", 1)})
        git(repo, "config", config_key, "true")
        (repo / "r.go").write_text(PACKAGE_LINE + go_function_nested("edited_deep", 5))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path)

        assert violation_summary(report) == [("edited_deep", "nesting", 5, 3)]

    def test_should_measure_an_over_limit_edit_to_a_file_whose_name_holds_a_space(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path, {"my report.go": PACKAGE_LINE + go_function_nested("edited_deep", 1)}
        )
        (repo / "my report.go").write_text(PACKAGE_LINE + go_function_nested("edited_deep", 5))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path)

        assert violation_summary(report) == [("edited_deep", "nesting", 5, 3)]
        assert report["unclaimed_files"] == []




class TestBashSize:
    def test_should_count_a_touched_bash_function_in_logical_lines_whatever_braces_its_heredoc_and_strings_hold(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path,
            {
                "report.sh": bash_function_with_statements("untouched_big", 35)
                + bash_function_with_statements("with_heredoc", 31, with_heredoc=True)
            },
        )
        base = head_of(repo)
        edited_tail = (
            bash_function_with_statements("with_heredoc", 31, with_heredoc=True)
            .replace("total + 29", "total + 290")
        )
        (repo / "report.sh").write_text(
            bash_function_with_statements("untouched_big", 35)
            + edited_tail
            + bash_function_with_statements("statements_30", 30)
        )
        declaration_path = write_declaration(tmp_path, ["size"])

        report = measure_report(repo, declaration_path, "--per-unit", "--base", base)

        assert measured_functions(report, "size") == ["statements_30", "with_heredoc"]
        assert violation_summary(report) == [("with_heredoc", "size", 31, 30)]

    def test_should_count_a_bash_file_in_logical_lines_and_flag_301_but_not_300(self, tmp_path):
        repo = make_repo(tmp_path, {"README.txt": "base\n"})
        header = "#!/bin/bash\n# header comment\n\n"
        (repo / "at_limit.sh").write_text(
            header + "".join(f"value_{number}={number}\n" for number in range(300))
        )
        (repo / "over_limit.sh").write_text(
            header + "".join(f"value_{number}={number}\n" for number in range(301))
        )
        declaration_path = write_declaration(tmp_path, ["size"])

        report = measure_report(repo, declaration_path, "--files", "at_limit.sh", "over_limit.sh")

        assert {item["file"]: item["value"] for item in report["measurements"]} == {
            "at_limit.sh": 300,
            "over_limit.sh": 301,
        }
        assert [item["file"] for item in report["violations"]] == ["over_limit.sh"]

# --- end of Bash size tests ---


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "quality-metrics"


class TestCrossPlatformMeasurement:
    def test_should_measure_the_fixture_repo_to_the_same_values_on_macos_and_linux(self, tmp_path):
        # Hand-written expected values live in the fixture dir,
        # so this test passing on macOS and in a Linux container
        # shows both read the fixture to the same values.
        repo = tmp_path / "repo"
        shutil.copytree(FIXTURE_DIR / "repo", repo)
        names = sorted(path.name for path in repo.iterdir())

        # The shipped declaration also binds CRAP and coverage,
        # which run the repo's tests; this fixture has none.
        declaration_path = write_declaration(tmp_path, ["size", "nesting", "parameters"])

        result = run_measure(repo, declaration_path, "--files", *names)
        report = json.loads(result.stdout)

        expected = json.loads((FIXTURE_DIR / "expected-measurements.json").read_text())
        order = lambda item: (item["file"], item["scope"], item["function"] or "", item["metric"])
        assert sorted(report["measurements"], key=order) == sorted(expected, key=order)
        assert [item["function"] for item in report["violations"]] == ["build_report"]


class TestUntrackedNonAsciiFile:
    def test_should_measure_an_over_limit_function_in_an_untracked_file_whose_name_holds_non_ascii_characters(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"seed.go": PACKAGE_LINE + go_function_nested("seed", 1)})
        (repo / "café.go").write_text(PACKAGE_LINE + go_function_nested("untracked_deep", 5))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        result = run_measure(repo, declaration_path, "--per-unit")

        report = json.loads(result.stdout)
        assert violation_summary(report) == [("untracked_deep", "nesting", 5, 3)]
        assert report["unclaimed_files"] == []
        assert result.returncode == 1


class TestUndecodableChangedFile:
    def test_should_exit_clean_when_the_diff_range_modifies_a_binary_file_and_no_limit_is_exceeded(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"seed.go": PACKAGE_LINE + go_function_nested("seed", 1)})
        (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00first")
        commit_all(repo, "add the logo")
        base = head_of(repo)
        (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00second")
        commit_all(repo, "change the logo")
        declaration_path = write_declaration(tmp_path, ["nesting"])

        result = run_measure(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert "UnicodeDecodeError" not in result.stderr
        assert result.returncode == 0
        assert json.loads(result.stdout)["violations"] == []


class TestBashDeclaredMetrics:
    @pytest.mark.parametrize("metric", ["nesting", "parameters"])
    def test_should_fail_as_a_declaration_error_naming_bash_and_the_metric_when_bash_declares_a_metric_it_cannot_measure(
        self, tmp_path, metric
    ):
        repo = make_repo(tmp_path, {"seed.go": PACKAGE_LINE + go_function_nested("seed", 1)})
        (repo / "deploy.sh").write_text("deploy() {\n  echo ok\n}\n")
        declaration_path = write_declaration(tmp_path, ["nesting"])
        declaration_path.write_text(
            declaration_path.read_text().replace(
                "  bash:\n    extensions: [.sh]\n    metrics: [size]",
                f"  bash:\n    extensions: [.sh]\n    metrics: [size, {metric}]",
            ).replace("per_unit: [nesting]", f"per_unit: [nesting, size, {metric}]")
        )

        result = run_measure(repo, declaration_path, "--per-unit")

        assert result.returncode == 2
        assert "TypeError" not in result.stderr
        assert "bash" in result.stderr and metric in result.stderr


class TestResolvedReadsTheHeadRef:
    def test_should_list_a_removed_over_limit_function_as_resolved_when_only_the_working_tree_still_holds_it(
        self, tmp_path
    ):
        keep = go_function_nested("keep_small", 1)
        repo = make_repo(
            tmp_path,
            {"report.go": PACKAGE_LINE + go_function_nested("legacy_parse", 5) + keep},
        )
        base = head_of(repo)
        (repo / "report.go").write_text(PACKAGE_LINE + keep)
        commit_all(repo, "drop the legacy parser")
        brought_back = PACKAGE_LINE + go_function_nested("legacy_parse", 5) + keep
        (repo / "report.go").write_text(brought_back)
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert [item["function"] for item in report["resolved"]] == ["legacy_parse"]


class TestListedFilesUnderPerUnit:
    def test_should_not_hold_the_commit_for_an_untouched_over_limit_function_in_a_listed_file_under_per_unit_files(
        self, tmp_path
    ):
        committed = PACKAGE_LINE + go_function_nested("legacy_parse", 5) + go_function_nested("small", 1)
        repo = make_repo(tmp_path, {"report.go": committed})
        (repo / "report.go").write_text(
            PACKAGE_LINE + go_function_nested("legacy_parse", 5)
            + go_function_nested("small", 1).replace("return 0", "return 2")
        )
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--per-unit", "--files", "report.go")

        assert report["violations"] == []
        assert report["holds_commit"] is False

    def test_should_still_hold_the_commit_when_the_touched_function_in_a_listed_file_breaks_a_limit_under_per_unit_files(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"report.go": PACKAGE_LINE + go_function_nested("edited_deep", 1)})
        (repo / "report.go").write_text(PACKAGE_LINE + go_function_nested("edited_deep", 5))
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--per-unit", "--files", "report.go")

        assert violation_summary(report) == [("edited_deep", "nesting", 5, 3)]
        assert report["holds_commit"] is True

    def test_should_measure_a_listed_file_with_no_diff_against_base_as_a_whole_file_under_per_unit_files(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"report.go": PACKAGE_LINE + go_function_nested("legacy_parse", 5)})
        declaration_path = write_declaration(tmp_path, ["nesting"])

        report = measure_report(repo, declaration_path, "--per-unit", "--files", "report.go")

        assert violation_summary(report) == [("legacy_parse", "nesting", 5, 3)]
        assert report["holds_commit"] is True
