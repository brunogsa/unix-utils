import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    commit_all, head_of, make_repo, measure_report, run_measure,
)
from quality_metrics_duplication_support import (
    COSTING, DECLARATION, PRICING, measure_uncommitted_changes,
)


class TestDuplicationCorpusExcludedPaths:
    def test_should_ignore_a_tracked_clone_under_an_excluded_directory_while_flagging_the_same_clone_outside_it(
        self, tmp_path
    ):
        repo = make_repo(
            tmp_path,
            {
                "src/pricing.py": PRICING,
                "dist/costing.py": COSTING,
            },
        )
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION)

        excluded_peer = measure_report(
            repo, declaration_path, "--files", "src/pricing.py"
        )["duplication_candidates"]
        (repo / "src/costing.py").write_text(COSTING)
        included_peer = measure_report(
            repo, declaration_path, "--files", "src/pricing.py"
        )["duplication_candidates"]

        assert excluded_peer == []
        assert {item["other_file"] for item in included_peer} == {"src/costing.py"}


class TestDuplicationBetweenUncommittedFiles:
    def test_should_flag_two_new_uncommitted_files_that_duplicate_each_other(self, tmp_path):
        violations = measure_uncommitted_changes(
            tmp_path,
            {},
            {"src/pricing.py": PRICING, "src/costing.py": COSTING},
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
            ("code_duplication", "src/costing.py"),
        }


class TestDuplicationInsideOneFile:
    def test_should_flag_a_function_copied_below_its_original_in_the_same_file(self, tmp_path):
        violations = measure_uncommitted_changes(
            tmp_path,
            {"src/pricing.py": PRICING},
            {"src/pricing.py": PRICING + "\n" + COSTING},
        )

        assert {(item["metric"], item["file"]) for item in violations} == {
            ("code_duplication", "src/pricing.py"),
        }


class TestWorkingTreeDifferingFromHeadRef:
    def test_should_exit_not_measured_naming_the_head_ref_when_a_touched_file_was_edited_after_the_head_commit(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {"src/pricing.py": "x = 1\n"})
        base = head_of(repo)
        (repo / "src/pricing.py").write_text(PRICING)
        commit_all(repo, "add pricing")
        (repo / "src/pricing.py").write_text(PRICING + "\nlater = 1\n")
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION)

        result = run_measure(repo, declaration_path, "--diff", f"{base}...HEAD")

        assert result.returncode == 2
        assert result.stdout == ""
        assert "HEAD" in result.stderr
