import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_functions_support import (
    PACKAGE_LINE, go_function_nested, measured_functions,
    violation_summary, write_declaration,
)
from quality_metrics_support import commit_all, git, head_of, make_repo, measure_report


def nesting_review_report(tmp_path, repo, revision_range):
    declaration_path = write_declaration(tmp_path, ["nesting"])
    return measure_report(repo, declaration_path, "--diff", revision_range)


def repo_after_dropping(tmp_path, dropped_name, dropped_depth):
    keep = go_function_nested("keep_small", 1)
    repo = make_repo(
        tmp_path,
        {"report.go": PACKAGE_LINE + go_function_nested(dropped_name, dropped_depth) + keep},
    )
    base = head_of(repo)
    (repo / "report.go").write_text(PACKAGE_LINE + keep)
    commit_all(repo, f"drop {dropped_name}")
    return repo, base


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

        report = nesting_review_report(tmp_path, repo, f"{base}...HEAD")

        assert measured_functions(report, "nesting") == ["added_deep", "edited_deep"]
        assert violation_summary(report) == [
            ("added_deep", "nesting", 4, 3),
            ("edited_deep", "nesting", 5, 3),
        ]

    def test_should_list_a_removed_over_limit_function_as_resolved_with_its_last_score_and_no_violation(
        self, tmp_path
    ):
        repo, base = repo_after_dropping(tmp_path, "legacy_parse", 5)

        report = nesting_review_report(tmp_path, repo, f"{base}...HEAD")

        assert [
            (item["file"], item["function"], item["metric"], item["value"], item["limit"])
            for item in report["resolved"]
        ] == [("report.go", "legacy_parse", "nesting", 5, 3)]
        assert report["violations"] == []

    def test_should_leave_a_removed_function_under_every_limit_out_of_the_resolved_list(
        self, tmp_path
    ):
        repo, base = repo_after_dropping(tmp_path, "trim_cell", 1)

        report = nesting_review_report(tmp_path, repo, f"{base}...HEAD")

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

        report = nesting_review_report(tmp_path, repo, "main...HEAD")

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

        report = nesting_review_report(tmp_path, repo, "main...HEAD")

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

        report = nesting_review_report(tmp_path, repo, f"{base}...HEAD")

        assert violation_summary(report) == []
        assert [item["value"] for item in report["measurements"]
                if item["metric"] == "nesting"] == [1]


class TestResolvedReadsTheHeadRef:
    def test_should_list_a_removed_over_limit_function_as_resolved_when_only_the_working_tree_still_holds_it(
        self, tmp_path
    ):
        repo, base = repo_after_dropping(tmp_path, "legacy_parse", 5)
        brought_back = (
            PACKAGE_LINE + go_function_nested("legacy_parse", 5) + go_function_nested("keep_small", 1)
        )
        (repo / "report.go").write_text(brought_back)

        report = nesting_review_report(tmp_path, repo, f"{base}...HEAD")

        assert [item["function"] for item in report["resolved"]] == ["legacy_parse"]
