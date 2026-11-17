import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    CRAP_LIMIT,
    DEFERRED_CRAP_SCORE,
    DEFERRED_LABEL,
    FunctionMeasure,
    function_record,
    crap_record,
    deferred_records,
    file_record,
    measured,
    report,
    target,
)
from quality_metrics_support import (
    verdict_entry_headings as entry_headings,
    verdict_section as section,
)
from quality_metrics.collection import CoverageRun
from quality_metrics.failures import function_tool_failure_records
from quality_metrics.functions import FunctionToolError


# entangled_tests has no script module: the code-reviewer lens
# judges it, so the script never renders a section for it.
NO_SCRIPT_MODULE = {"entangled_tests"}
DECLARATION = Path(__file__).resolve().parent.parent / "quality-metrics.yaml"


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

    def test_should_mark_a_failed_test_runs_unlabelled_0_percent_coverage_as_pessimistic_in_the_open_violations(self):
        failed_run = {
            **file_record("src/report.py", "coverage", 0, 80),
            "flagged_below_limit": True, "pessimistic": True,
        }
        measured_zero = {
            **file_record("src/other.py", "coverage", 0, 80), "flagged_below_limit": True,
        }

        verdict = report.build_verdict(measured(failed_run, measured_zero))

        entries = entry_headings(section(verdict, "Open violations"))
        [failed_entry] = [entry for entry in entries if "src/report.py" in entry]
        [measured_entry] = [entry for entry in entries if "src/other.py" in entry]
        assert "Coverage 0 (pessimistic)" in failed_entry
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

    def test_should_render_a_crashed_function_tools_flagged_nesting_record_as_an_open_deferred_violation(
        self, tmp_path
    ):
        error = FunctionToolError("lizard", "lizard crashed with a traceback")
        headless_run = CoverageRun(
            tmp_path, tool_map=object(), environ={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}
        )
        records = function_tool_failure_records(
            target("src/deferred.py"), ["nesting"], error, headless_run
        )

        verdict = report.build_verdict(measured(*records))

        [entry] = entry_headings(section(verdict, "Open violations"))
        assert "src/deferred.py" in entry
        assert "Nesting" in entry
        assert entry.count(DEFERRED_LABEL) == 1

    @pytest.mark.parametrize("metric, title", [
        ("size", "Function size"),
        ("nesting", "Nesting"),
        ("parameters", "Parameters"),
        ("cognitive_complexity", "Cognitive complexity"),
        ("crap", "CRAP"),
    ])
    def test_should_title_a_crashed_function_tools_deferred_record_with_the_function_metrics_own_title(
        self, tmp_path, metric, title
    ):
        error = FunctionToolError("lizard", "lizard crashed with a traceback")
        headless_run = CoverageRun(
            tmp_path, tool_map=object(), environ={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}
        )
        records = function_tool_failure_records(
            target("src/deferred.py"), [metric], error, headless_run
        )

        verdict = report.build_verdict(measured(*records))

        [entry] = entry_headings(section(verdict, "Open violations"))
        assert f" - {title} " in entry
        assert "File size" not in entry

    def test_should_print_the_deferred_label_once_on_a_valueless_deferred_record(self):
        function = FunctionMeasure("tangle", 4, 30, 26, 12, None, None)
        run = measured(
            deferred_records.deferred_measurement(
                target("src/deferred.py"), "crap", CRAP_LIMIT, function
            )
        )

        verdict = report.build_verdict(run)

        [entry] = entry_headings(section(verdict, "Not measured"))
        assert entry.count(DEFERRED_LABEL) == 1


class TestUncoveredLinesInVerdict:
    def test_should_show_the_uncovered_ranges_under_a_coverage_and_a_crap_entry(self):
        low_coverage = {
            **file_record("src/untested.py", "coverage", 40, 90),
            "flagged_below_limit": True,
            "uncovered_lines": ["12-15", "40"],
        }
        risky = {**crap_record("src/report.py", "buildReport", 42), "uncovered_lines": ["7-9"]}

        verdict = report.build_verdict(measured(low_coverage, risky))

        violations = section(verdict, "Open violations")
        assert "Uncovered lines: 12-15, 40" in violations
        assert "Uncovered lines: 7-9" in violations

    def test_should_omit_the_uncovered_line_when_nothing_is_uncovered_or_nothing_was_measured(self):
        all_covered = {
            **file_record("src/tested.py", "coverage", 100, 90),
            "flagged_below_limit": True,
            "uncovered_lines": [],
        }
        not_measured = {
            **crap_record("src/report.py", "buildReport", 42),
            "uncovered_lines": None,
        }

        verdict = report.build_verdict(measured(all_covered, not_measured))

        assert "Uncovered lines" not in verdict


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


class TestDuplicationCandidates:
    def test_should_list_each_clone_in_its_own_section_after_the_gate_inputs(self):
        run = measured(
            crap_record("src/report.py", "buildReport", 42),
            file_record("src/pricing.py", "code_duplication", 0.91, 0.82),
            file_record("tests/test_pricing.py", "test_duplication", 0.88, 0.82),
        )

        verdict = report.build_verdict(run)

        candidates = section(verdict, "Duplication candidates")
        assert "(2)" in candidates.splitlines()[0]
        first, second = entry_headings(candidates)
        assert first.startswith("### 2.") and "src/pricing.py" in first
        assert second.startswith("### 3.") and "tests/test_pricing.py" in second
        assert verdict.index("## Gate input violations") < verdict.index("## Duplication candidates")

    def test_should_keep_a_clone_out_of_the_open_violations(self):
        run = measured(file_record("src/pricing.py", "code_duplication", 0.91, 0.82))

        verdict = report.build_verdict(run)

        assert "(0)" in section(verdict, "Open violations").splitlines()[0]
        assert "src/pricing.py" not in section(verdict, "Open violations")

    def test_should_show_0_duplication_candidates_when_the_report_has_none(self):
        verdict = report.build_verdict(measured())

        assert "(0)" in section(verdict, "Duplication candidates").splitlines()[0]


class TestNotApplicable:
    def test_should_list_each_not_applicable_file_with_its_reason_outside_the_open_violations(self):
        run = {
            **measured(),
            "not_applicable": [
                {
                    "file": "tools/sync.py",
                    "metric": "dependency_direction",
                    "reason": "outside every package",
                }
            ],
        }

        verdict = report.build_verdict(run)

        listed = section(verdict, "Not applicable")
        assert "(1)" in listed.splitlines()[0]
        assert "tools/sync.py" in listed
        assert "Dependency direction" in listed
        assert "not applicable: outside every package" in listed
        assert "tools/sync.py" not in section(verdict, "Open violations")

    def test_should_show_0_not_applicable_files_when_the_report_has_none(self):
        verdict = report.build_verdict(measured())

        assert "(0)" in section(verdict, "Not applicable").splitlines()[0]


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


class TestWithinLimitMeasurements:
    def test_should_name_no_measurement_within_its_limit_and_keep_the_over_limit_and_valueless_ones(self):
        function = FunctionMeasure("unmeasured", 4, 30, 26, 12, None, None)
        run = measured(
            crap_record("src/report.py", "tidyHelper", 3),
            crap_record("src/report.py", "tangledBuild", 42),
            deferred_records.deferred_measurement(
                target("src/deferred.py"), "crap", CRAP_LIMIT, function
            ),
        )

        verdict = report.build_verdict(run)

        assert "## Ranked" not in verdict
        assert "tidyHelper" not in verdict
        assert "tangledBuild" in section(verdict, "Open violations")
        [unmeasured] = entry_headings(section(verdict, "Not measured"))
        assert "unmeasured" in unmeasured
        assert f"no value ({DEFERRED_LABEL})" in unmeasured

    def test_should_show_0_unmeasured_records_when_every_record_has_a_value(self):
        verdict = report.build_verdict(measured(crap_record("src/report.py", "tidyHelper", 3)))

        assert "(0)" in section(verdict, "Not measured").splitlines()[0]


class TestMetricTitles:
    @pytest.mark.parametrize("metric, title, section_title, make_record", [
        ("cognitive_complexity", "Cognitive complexity", "Open violations",
         lambda metric: function_record("src/report.py", "build", metric, 30, 10)),
        ("code_duplication", "Code duplication", "Duplication candidates",
         lambda metric: file_record("src/report.py", metric, 30, 10)),
    ])
    def test_should_title_a_listed_measurement_with_the_display_name_not_the_raw_metric_key(
        self, metric, title, section_title, make_record
    ):
        record = make_record(metric)

        verdict = report.build_verdict(measured(record))

        listed = section(verdict, section_title)
        assert f" - {title} " in listed
        assert metric not in listed

    def test_should_title_every_metric_the_declaration_lists_so_a_new_metric_cannot_render_a_raw_key(self):
        declaration = yaml.safe_load(DECLARATION.read_text())
        assert isinstance(declaration, dict)
        declared = {
            metric
            for language in declaration["languages"].values()
            for metric in language["metrics"]
        } - NO_SCRIPT_MODULE
        titled = {metric for metric, _scope in report.METRIC_TITLES}

        assert sorted(declared - titled) == []
