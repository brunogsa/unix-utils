import importlib
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_functions_support import (
    PACKAGE_LINE, bash_function_with_statements, go_function_with_lines,
    go_function_with_parameters, measured_functions, violation_summary,
    write_declaration,
)
from quality_metrics_support import head_of, make_repo, measure_report


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
