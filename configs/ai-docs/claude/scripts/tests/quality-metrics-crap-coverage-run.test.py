import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, head_of, make_repo, run_measure
from quality_metrics_crap_coverage_support import (
    DECLARATION_TEXT,
    RUN_DECLARATION_TEXT,
    SOURCE_BASE,
    SOURCE_CHANGED,
    TEST_FILE_NAME,
    TEST_FILE_TEXT,
    lcov_report,
    make_fixture_repo,
    measure_repo,
    records_for,
)

# Coverage records nothing when every file is omitted, so a
# passing run writes no coverage data.
OMIT_EVERYTHING = "[run]\nomit = *\n"

ONE_DAY_IN_SECONDS = 86400


class TestCoverageCollection:
    def test_should_read_0_percent_coverage_with_no_tooling_ask_when_the_repo_has_no_tests(
        self, tmp_path
    ):
        repo = make_fixture_repo(tmp_path)

        result = measure_repo(tmp_path, repo)

        # Exit 1 is a violation (0% is under 90%).
        # Exit 2 would be a tool failure.
        assert result.returncode == 1
        assert result.stderr == ""
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] == 0
        assert "pessimistic" not in coverage_record

    def test_should_treat_a_coverage_file_older_than_its_test_run_as_no_coverage_data(
        self, tmp_path
    ):
        repo = make_fixture_repo(tmp_path, {
            ".coveragerc": OMIT_EVERYTHING,
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=90.0),
        })
        stale_lcov = repo / "coverage" / "lcov.info"
        stale_lcov.parent.mkdir()
        stale_lcov.write_text(
            lcov_report("invoice_totals.py", {1: 1, 2: 1, 3: 1, 4: 1})
        )
        last_run = stale_lcov.stat().st_mtime - ONE_DAY_IN_SECONDS
        os.utime(stale_lcov, (last_run, last_run))

        result = measure_repo(tmp_path, repo)

        assert result.returncode == 1
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] == 0
        assert "pessimistic" not in coverage_record


class TestFailedTestRun:
    def test_should_score_crap_and_coverage_at_0_percent_marked_pessimistic_while_complexity_still_reports_when_tests_fail(
        self, tmp_path
    ):
        # The failing test still runs the changed
        # lines, so real coverage is above 0 and only
        # the red build explains 0%.
        repo = make_fixture_repo(tmp_path, {
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=85.0),
        })

        result = measure_repo(tmp_path, repo)

        assert result.returncode == 1
        (coverage_record,) = records_for(result, "coverage")
        (crap_record,) = records_for(result, "crap")
        assert coverage_record["value"] == 0
        assert coverage_record["pessimistic"] is True
        assert crap_record["value"] == 6
        assert crap_record["pessimistic"] is True
        (nesting_record,) = records_for(result, "nesting")
        (parameters_record,) = records_for(result, "parameters")
        assert nesting_record["value"] == 1
        assert parameters_record["value"] == 2


UNRELATED_SOURCE = "def shipping_fee(weight):\n    return weight * 2\n"
UNRELATED_TEST_TEXT = (
    "from shipping import shipping_fee\n\n\n"
    "def test_fee_of_three_kilos():\n"
    "    assert shipping_fee(3) == 6\n"
)

# The exclusion marker keeps the block out of coverage, as a
# type-only change leaves no executable line behind. It is
# fixture text for the measured repo, not a suppression here,
# so the literal is built in two parts.
COVERAGE_EXCLUSION_MARKER = "# pragma: no " + "cover"
TYPE_ONLY_BASE = (
    SOURCE_BASE
    + f"\nif False:  {COVERAGE_EXCLUSION_MARKER}\n"
    "    pass\n"
)
TYPE_ONLY_CHANGE = TYPE_ONLY_BASE + "    from decimal import Decimal\n"


class TestChangedFileCoverageReading:
    def test_should_count_every_changed_line_of_a_file_absent_from_the_coverage_report_as_uncovered(
        self, tmp_path
    ):
        # The passing test runs shipping.py only, so the
        # report lists it but never invoice_totals.py.
        repo = make_fixture_repo(tmp_path, {
            "shipping.py": UNRELATED_SOURCE,
            "test_shipping.py": UNRELATED_TEST_TEXT,
        })

        result = measure_repo(tmp_path, repo)

        assert result.returncode == 1
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["file"] == "invoice_totals.py"
        assert coverage_record["value"] == 0
        assert "pessimistic" not in coverage_record

    def test_should_read_not_applicable_no_coverable_lines_when_only_type_declarations_change(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "invoice_totals.py": TYPE_ONLY_BASE,
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=100),
        })
        (repo / "invoice_totals.py").write_text(TYPE_ONLY_CHANGE)

        result = measure_repo(tmp_path, repo)

        # Exit 0: neither passed nor failed, so no violation.
        assert result.returncode == 0
        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] is None
        assert coverage_record["status"] == (
            "not applicable: no coverable lines"
        )
        assert json.loads(result.stdout)["violations"] == []


def branchy_function(name, complexity):
    """A function of the given cyclomatic complexity: one `if`
    per point above 1."""
    branches = "".join(f"    if value == {n}:\n        return {n}\n" for n in range(complexity - 1))
    return f"def {name}(value):\n{branches}    return 0\n"


class TestRemovedFunctionScoredAtBase:
    def test_should_list_a_removed_untested_complexity_31_function_as_resolved_at_crap_31(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "legacy.py": branchy_function("legacy_parse", 31),
            "keep.py": "def keep():\n    return 1\n",
        })
        base = head_of(repo)
        (repo / "legacy.py").unlink()
        commit_all(repo, "drop the legacy parser")
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION_TEXT)

        result = run_measure(repo, declaration_path, "--diff", f"{base}...HEAD")

        report = json.loads(result.stdout)
        assert [
            (item["file"], item["function"], item["metric"], item["value"])
            for item in report["resolved"]
        ] == [("legacy.py", "legacy_parse", "crap", 31)]


class TestDiffCoverageOnHeadRefExport:
    def test_should_read_the_head_ref_coverage_when_an_uncommitted_test_file_breaks_pytest_collection(
        self, tmp_path
    ):
        repo = make_repo(tmp_path, {
            "invoice_totals.py": SOURCE_BASE,
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=90.0),
        })
        base = head_of(repo)
        (repo / "invoice_totals.py").write_text(SOURCE_CHANGED)
        commit_all(repo, "discount a positive rate")
        (repo / "test_untracked_draft.py").write_text("def broken(:\n")
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(RUN_DECLARATION_TEXT)

        result = run_measure(
            repo, declaration_path, "--diff", f"{base}...HEAD"
        )

        (coverage_record,) = records_for(result, "coverage")
        assert coverage_record["value"] == 100
        assert "pessimistic" not in coverage_record


class TestWorkingTreeDifferingFromHeadRef:
    def test_should_exit_not_measured_naming_the_head_ref_when_a_touched_file_was_edited_after_the_head_commit(
        self, tmp_path
    ):
        repo = make_fixture_repo(tmp_path, {
            TEST_FILE_NAME: TEST_FILE_TEXT.format(expected=90.0),
        })
        base = head_of(repo)
        commit_all(repo, "change the invoice totals")
        (repo / "invoice_totals.py").write_text(
            SOURCE_CHANGED + "\n\ndef later_edit():\n    return 1\n"
        )
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(RUN_DECLARATION_TEXT)

        result = run_measure(
            repo, declaration_path, "--diff", f"{base}...HEAD"
        )

        assert result.returncode == 2
        assert result.stdout == ""
        assert "HEAD" in result.stderr
