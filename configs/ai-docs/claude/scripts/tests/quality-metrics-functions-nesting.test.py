import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_functions_support import (
    PACKAGE_LINE, go_function_nested, measured_functions,
    violation_summary, write_declaration,
)
from quality_metrics_support import git, make_repo, measure_report


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
