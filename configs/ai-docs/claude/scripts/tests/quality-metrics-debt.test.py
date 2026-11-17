"""The report-only technical-debt score: remediation minutes
over the cost of writing the measured code, banded A to E."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import crap_record, file_record, function_record
from quality_metrics_support import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

debt = importlib.import_module("quality_metrics.debt")
measuring = importlib.import_module("quality_metrics.measuring")

LONG_FUNCTION = function_record("src/a.py", "build", "size", 90, 30)
MEASURED_LINES = 10


class TestDebtScore:
    def test_should_score_0_minutes_and_band_a_when_there_are_no_violations(self):
        score = debt.debt_score([], 100)

        assert score["minutes"] == 0
        assert score["ratio"] == 0
        assert score["band"] == "A"

    def test_should_divide_the_remediation_minutes_by_30_minutes_per_measured_line(self):
        score = debt.debt_score([LONG_FUNCTION], MEASURED_LINES)

        assert score["minutes"] == 20
        assert score["ratio"] == 20 / (30 * MEASURED_LINES)
        assert score["band"] == "B"

    def test_should_not_compute_a_ratio_or_a_band_when_no_line_was_measured(self):
        score = debt.debt_score([LONG_FUNCTION], 0)

        assert score["minutes"] == 20
        assert score["ratio"] is None
        assert score["band"] is None

    def test_should_cost_a_file_size_violation_more_than_a_function_size_one(self):
        file_size = file_record("src/a.py", "size", 900, 300)

        assert debt.debt_score([file_size], 1)["minutes"] == 60

    def test_should_count_a_pessimistic_violation_like_a_measured_one(self):
        pessimistic = {**crap_record("src/a.py", "build", 99), "pessimistic": True}

        assert debt.debt_score([pessimistic], 1)["minutes"] == debt.debt_score(
            [crap_record("src/a.py", "build", 99)], 1
        )["minutes"]

    def test_should_price_cognitive_complexity_at_5_minutes_plus_1_per_point_over_the_limit(self):
        record = function_record("src/a.py", "build", "cognitive_complexity", 20, 15)

        assert debt.debt_score([record], 1)["minutes"] == 10

    def test_should_price_cognitive_complexity_at_the_offset_when_it_has_no_value(self):
        record = function_record("src/a.py", "build", "cognitive_complexity", None, 15)

        assert debt.debt_score([record], 1)["minutes"] == 5

    def test_should_price_every_metric_the_registry_defines(self):
        assert set(measuring.METRIC_MODULES) == set(debt.REMEDIATION_MINUTES)

    def test_should_price_a_type_error_at_10_minutes_and_an_unused_code_finding_at_5(self):
        type_error = function_record("src/a.py", "build", "type_errors", 1, 0)
        unused_code = function_record("src/a.py", "build", "unused_code", 1, 0)

        assert debt.debt_score([type_error], 1)["minutes"] == 10
        assert debt.debt_score([unused_code], 1)["minutes"] == 5

    def test_should_price_a_dead_code_candidate_at_10_minutes_and_a_surviving_mutant_at_15(self):
        dead_code = function_record("src/a.py", "build", "dead_code", 1, 0)
        mutant = function_record("src/a.py", "build", "mutation", 1, 0)

        assert debt.debt_score([dead_code], 1)["minutes"] == 10
        assert debt.debt_score([mutant], 1)["minutes"] == 15

    def test_should_band_each_ratio_at_the_sonar_maintainability_edges(self):
        edges = [(0.05, "A"), (0.0501, "B"), (0.0999, "B"), (0.10, "C"),
                 (0.1999, "C"), (0.20, "D"), (0.4999, "D"), (0.50, "E")]

        assert [debt.band_for(ratio) for ratio, _ in edges] == [b for _, b in edges]

    def test_should_measure_nloc_from_the_file_size_records_only(self):
        records = [
            file_record("src/a.py", "size", 40, 300),
            file_record("src/b.py", "size", 25, 300),
            LONG_FUNCTION,
            file_record("src/a.py", "coverage", 80, 90),
        ]

        assert debt.measured_nloc(records) == 65
