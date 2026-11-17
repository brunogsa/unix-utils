import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_crap_coverage_support import (
    SOURCE_FILE,
    coverage,
    crap,
    function_measure,
    functions,
    lcov_report,
    load_declaration,
    python_target,
    touched,
)


def measure_crap(declaration, language, path, measured, lcov_text):
    target = touched.Target(Path(path), language, touched.WHOLE_FILE)
    return crap.crap_measurements(
        declaration, target, measured,
        crap.parse_lcov(lcov_text).get(path, {}),
    )


def crap_by_function(records):
    return {record["function"]: record["value"] for record in records}


def flagged_functions(records):
    return sorted(
        record["function"] for record in records if functions.is_over_limit(record)
    )


class TestCrapScoring:
    def test_should_flag_an_uncovered_complexity_6_function_at_crap_42_and_pass_a_half_covered_complexity_4_one_at_6(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("apply_discount", 1, 10, 6),
            function_measure("round_to_cents", 12, 21, 4),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 0, 2: 0, 3: 0, 4: 0,
            12: 5, 13: 5, 14: 0, 15: 0,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        assert crap_by_function(records) == {"apply_discount": 42, "round_to_cents": 6}
        assert flagged_functions(records) == ["apply_discount"]

    def test_should_pass_a_score_of_exactly_30_and_flag_a_score_above_it(self, tmp_path):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("at_limit", 1, 10, 5),
            function_measure("over_limit", 12, 21, 6),
            function_measure("well_tested", 23, 40, 8),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 0, 2: 0, 12: 0, 13: 0, 23: 3, 24: 3,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        assert crap_by_function(records) == {"at_limit": 30, "over_limit": 42, "well_tested": 8}
        assert flagged_functions(records) == ["over_limit"]

    def test_should_flag_a_score_of_30_01(self):
        record = crap.crap_record(
            touched.Target(Path(SOURCE_FILE), "python", touched.WHOLE_FILE),
            function_measure("just_over", 1, 10, 5), 30.01,
        )

        assert functions.is_over_limit(record)


class TestCoverageOptOut:
    def test_should_score_crap_at_full_coverage_when_the_language_opts_coverage_out(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [function_measure("deploy_release", 1, 30, 6)]
        no_coverage_data = ""

        opted_out = measure_crap(
            declaration, "bash", "bin/deploy.sh", measured, no_coverage_data
        )
        tool_failed = measure_crap(
            declaration, "python", SOURCE_FILE, measured, no_coverage_data
        )

        assert crap_by_function(opted_out) == {"deploy_release": 6}
        assert flagged_functions(opted_out) == []
        assert crap_by_function(tool_failed) == {"deploy_release": 42}
        assert flagged_functions(tool_failed) == ["deploy_release"]


def covered_then_uncovered(covered_count, uncovered_count):
    """Hits for lines 1..N: the first covered_count run, the
    rest never."""
    return {
        line: 1 if line <= covered_count else 0
        for line in range(1, covered_count + uncovered_count + 1)
    }


class TestChangedLineCoverage:
    def test_should_flag_changed_line_coverage_under_90_percent(self):
        # Lines 21, 22 never run but were not changed. Line 11
        # was changed but holds no code, so it has no hit entry.
        hits = {**covered_then_uncovered(6, 4), 21: 0, 22: 0}
        target = python_target(set(range(1, 12)))

        record = coverage.coverage_measurement(target, hits)

        assert record["metric"] == "coverage"
        assert record["value"] == 60
        assert functions.is_over_limit(record)

    def test_should_pass_90_percent_and_fail_89_9_percent_changed_line_coverage(self):
        at_limit = coverage.coverage_measurement(
            python_target(set(range(1, 11))),
            covered_then_uncovered(9, 1),
        )
        under_limit = coverage.coverage_measurement(
            python_target(set(range(1, 1001))),
            covered_then_uncovered(899, 101),
        )

        assert at_limit["value"] == 90
        assert not functions.is_over_limit(at_limit)
        assert under_limit["value"] == 89.9
        assert functions.is_over_limit(under_limit)


class TestUncoveredChangedLines:
    def test_should_list_changed_lines_that_never_ran_as_collapsed_ranges(self):
        # Line 5 is covered; 1-4 and 6-8 are not.
        # Line 30 never ran but was not changed.
        hits = {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 0, 7: 0, 8: 0, 30: 0}
        target = python_target(set(range(1, 9)) | {10})

        record = coverage.coverage_measurement(target, hits)

        assert record["uncovered_lines"] == ["1-4", "6-8"]

    def test_should_list_a_single_uncovered_line_as_a_bare_number(self):
        record = coverage.coverage_measurement(
            python_target({3, 4}), {3: 1, 4: 0, 9: 0}
        )

        assert record["uncovered_lines"] == ["4"]

    def test_should_list_nothing_when_every_changed_line_ran(self):
        record = coverage.coverage_measurement(python_target({1, 2}), {1: 4, 2: 1})

        assert record["uncovered_lines"] == []

    def test_should_report_no_line_data_as_null_when_the_report_omits_the_file(self):
        record = coverage.coverage_measurement(python_target({1, 2}), None)

        assert record["uncovered_lines"] is None

    def test_should_report_null_for_a_file_whose_changed_lines_hold_no_code(self):
        record = coverage.coverage_measurement(python_target({1, 2}), {50: 0})

        assert record["uncovered_lines"] is None


class TestUncoveredFunctionLines:
    def test_should_list_only_the_functions_own_lines_that_never_ran(self, tmp_path):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("apply_discount", 1, 10, 6),
            function_measure("round_to_cents", 12, 21, 4),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 1, 2: 0, 3: 0, 4: 1, 5: 0,
            12: 5, 13: 5,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        uncovered = {record["function"]: record["uncovered_lines"] for record in records}
        assert uncovered == {"apply_discount": ["2-3", "5"], "round_to_cents": []}

    def test_should_report_null_when_the_coverage_tool_gave_no_line_data(self, tmp_path):
        declaration = load_declaration(tmp_path)
        measured = [function_measure("apply_discount", 1, 10, 6)]
        no_coverage_data = ""

        tool_failed = measure_crap(
            declaration, "python", SOURCE_FILE, measured, no_coverage_data
        )
        opted_out = measure_crap(
            declaration, "bash", "bin/deploy.sh", measured, no_coverage_data
        )

        assert [record["uncovered_lines"] for record in tool_failed + opted_out] == [None, None]


class TestUnroundedCompareTruncatedDisplay:
    def test_should_pass_crap_7_996_shown_as_7_99_and_fail_coverage_89_996_percent_shown_as_89_99_percent(self):
        target = python_target(None)
        crap_record = crap.crap_record(
            target, function_measure("split_payment", 1, 20, 7), 7.996
        )
        coverage_record = coverage.coverage_record(target, 89.996)

        assert not functions.is_over_limit(crap_record)
        assert functions.display_value(crap_record) == "7.99"
        assert functions.is_over_limit(coverage_record)
        assert functions.display_value(coverage_record) == "89.99"
