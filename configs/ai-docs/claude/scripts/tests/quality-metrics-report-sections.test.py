import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    CRAP_LIMIT,
    DEFERRED_CRAP_SCORE,
    DEFERRED_LABEL,
    FunctionMeasure,
    crap_record,
    deferred_records,
    entry_headings,
    file_record,
    measured,
    report,
    section,
    target,
)


class TestExceptions:
    def test_should_open_with_1_exception_naming_the_function_its_score_the_splits_score_and_the_diff_link(
        self, tmp_path
    ):
        split_diff = tmp_path / "split_buildReport.diff"
        split_diff.write_text("--- a/src/report.py\n+++ b/src/report.py\n")
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(split_diff),
        }
        run = measured(crap_record("src/report.py", "buildReport", 42))

        verdict = report.build_verdict(run, exceptions=[claim])

        exceptions = section(verdict, "Exceptions")
        assert "(1)" in exceptions.splitlines()[0]
        [entry] = entry_headings(exceptions)
        assert entry.startswith("### 1. [metrics]")
        assert "buildReport" in entry
        assert "CRAP 42" in entry
        assert "split CRAP 6" in entry
        assert f"]({split_diff})" in entry
        assert verdict.index("## Exceptions") < verdict.index("## Open violations")

    def test_should_list_a_kept_over_limit_function_as_a_violation_when_no_split_diff_file_is_linked(
        self, tmp_path
    ):
        unsaved_diff = tmp_path / "split_buildReport.diff"
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(unsaved_diff),
        }
        run = measured(crap_record("src/report.py", "buildReport", 42))

        verdict = report.build_verdict(run, exceptions=[claim])

        assert "(0)" in section(verdict, "Exceptions").splitlines()[0]
        violations = section(verdict, "Open violations")
        assert "(1)" in violations.splitlines()[0]
        [entry] = entry_headings(violations)
        assert "buildReport" in entry
        assert "CRAP 42" in entry


    def test_should_keep_an_unfixable_violation_and_a_rejected_exception_open_and_first(
        self, tmp_path
    ):
        split_diff = tmp_path / "split_splitCells.diff"
        split_diff.write_text("--- a/src/cells.py\n+++ b/src/cells.py\n")
        rejected_claim = {
            "file": "src/cells.py", "function": "splitCells", "metric": "crap",
            "split_value": 5, "diff_path": str(split_diff), "rejected": True,
        }
        run = measured(
            crap_record("src/rows.py", "mergeRows", 45),
            crap_record("src/cells.py", "splitCells", 36),
        )

        verdict = report.build_verdict(run, exceptions=[rejected_claim])

        assert "(0)" in section(verdict, "Exceptions").splitlines()[0]
        violations = section(verdict, "Open violations")
        assert "(2)" in violations.splitlines()[0]
        merge_rows, split_cells = sorted(entry_headings(violations))
        assert "mergeRows" in merge_rows
        assert "splitCells" in split_cells
        assert "exception rejected" in split_cells
        assert verdict.index("## Open violations") < verdict.index("## Ranked: CRAP")


class TestDeferredMetrics:
    def test_should_list_deferred_metrics_first_beside_the_exceptions_with_a_count(self):
        label = "pessimistic, tooling deferred"
        deferred = [
            {
                **crap_record("src/report.py", name, DEFERRED_CRAP_SCORE),
                "pessimistic": True, "label": label,
            }
            for name in ("buildReport", "mergeRows")
        ]

        verdict = report.build_verdict(measured(*deferred))

        deferred_section = section(verdict, "Deferred metrics")
        assert "(1)" in deferred_section.splitlines()[0]
        [entry] = entry_headings(deferred_section)
        assert entry.startswith("### 1. [metrics]")
        assert "CRAP" in entry
        assert "2 measurements" in entry
        assert label in entry
        assert verdict.index("## Deferred metrics") < verdict.index("## Exceptions")
        violations = section(verdict, "Open violations")
        assert "(2)" in violations.splitlines()[0]
        assert "buildReport" in violations
        assert "mergeRows" in violations

    def test_should_not_list_a_failed_test_run_as_a_deferred_metric_and_still_build_the_verdict(self):
        failed_run = [
            {**crap_record("src/report.py", "buildReport", 42), "pessimistic": True}
        ]

        verdict = report.build_verdict(measured(*failed_run))

        deferred_section = section(verdict, "Deferred metrics")
        assert "(0)" in deferred_section.splitlines()[0]
        assert entry_headings(deferred_section) == []
        assert "buildReport" in section(verdict, "Open violations")

    def test_should_mark_a_failed_test_runs_unlabelled_0_percent_coverage_as_pessimistic_in_the_ranking(self):
        failed_run = {**file_record("src/report.py", "coverage", 0, 80), "pessimistic": True}
        measured_zero = file_record("src/other.py", "coverage", 0, 80)

        verdict = report.build_verdict(measured(failed_run, measured_zero))

        entries = entry_headings(section(verdict, "Ranked: coverage"))
        [failed_entry] = [entry for entry in entries if "src/report.py" in entry]
        [measured_entry] = [entry for entry in entries if "src/other.py" in entry]
        assert "coverage 0 (pessimistic)" in failed_entry
        assert "pessimistic" not in measured_entry

    def test_should_print_the_deferred_label_on_a_deferred_crap_violation_but_not_on_a_measured_one(self):
        function = FunctionMeasure("buildReport", 4, 30, 26, 12, None, None)
        [deferred] = deferred_records.deferred_crap_measurements(target("src/deferred.py"), [function])
        run = measured(crap_record("src/measured.py", "mergeRows", DEFERRED_CRAP_SCORE), deferred)

        verdict = report.build_verdict(run)

        entries = entry_headings(section(verdict, "Open violations"))
        [deferred_entry] = [entry for entry in entries if "buildReport" in entry]
        [measured_entry] = [entry for entry in entries if "mergeRows" in entry]
        assert deferred_entry.count(DEFERRED_LABEL) == 1
        assert DEFERRED_LABEL not in measured_entry

    def test_should_print_the_deferred_label_once_on_a_valueless_deferred_violation(self):
        function = FunctionMeasure("tangle", 4, 30, 26, 12, None, None)
        run = measured(
            deferred_records.deferred_measurement(
                target("src/deferred.py"), "crap", CRAP_LIMIT, function
            )
        )

        verdict = report.build_verdict(run)

        [entry] = entry_headings(section(verdict, "Ranked: CRAP"))
        assert entry.count(DEFERRED_LABEL) == 1


class TestGateInputViolations:
    def test_should_list_each_gate_input_violation_in_its_own_section_after_the_open_violations(self):
        run = {
            **measured(crap_record("src/report.py", "buildReport", 42)),
            "gate_input_violations": [
                {"kind": "declaration_change", "file": "layers.yaml", "value": "excluded_paths"},
                {"kind": "opt_out", "file": "layers.yaml", "value": "ts.size"},
            ],
        }

        verdict = report.build_verdict(run)

        gate_section = section(verdict, "Gate input violations")
        assert "(2)" in gate_section.splitlines()[0]
        first, second = entry_headings(gate_section)
        assert "declaration_change" in first and "layers.yaml" in first
        assert "excluded_paths" in first
        assert "opt_out" in second and "layers.yaml" in second
        assert "ts.size" in second
        assert verdict.index("## Open violations") < verdict.index("## Gate input violations")

    def test_should_show_0_gate_input_violations_when_the_report_has_none(self):
        verdict = report.build_verdict(measured())

        assert "(0)" in section(verdict, "Gate input violations").splitlines()[0]


class TestNoGitVerdict:
    def test_should_name_the_no_git_verdict_and_state_the_removed_code_check_and_base_ref_reads_were_skipped(self):
        run = measured(crap_record("tool.sh", "main", 3))

        verdict = report.build_verdict(run, in_git=False)

        assert (
            report.verdict_filename("2026-11-15_22-30", in_git=False)
            == "verdict_quality-gate_no-git_2026-11-15_22-30.md"
        )
        assert (
            report.verdict_filename("2026-11-15_22-30", in_git=True)
            == "verdict_metrics_2026-11-15_22-30.md"
        )
        skipped = section(verdict, "Skipped")
        assert "removed-code check" in skipped
        assert "base-ref" in skipped
        assert "Skipped" not in report.build_verdict(run)
