import importlib
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
crap = importlib.import_module("quality_metrics.crap")
declaring = importlib.import_module("quality_metrics.declaration")
functions = importlib.import_module("quality_metrics.functions")
touched = importlib.import_module("quality_metrics.touched")

# Python declares crap and coverage; Bash opts coverage out.
DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  python:
    extensions: [.py]
    metrics: [crap, coverage]
  bash:
    extensions: [.sh]
    metrics: [crap]
"""

SOURCE_FILE = "src/invoice_totals.py"


def load_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION_TEXT)
    return declaring.load_declaration(path)


def function_measure(name, start, end, complexity):
    return functions.FunctionMeasure(
        name=name, start=start, end=end, nloc=end - start + 1,
        complexity=complexity, nesting=None, parameters=None,
    )


def lcov_report(path, hits_by_line):
    lines = [f"SF:{path}"]
    lines += [f"DA:{line},{hits}" for line, hits in hits_by_line.items()]
    lines.append("end_of_record")
    return "\n".join(lines)


def measure_crap(declaration, language, path, measured, lcov_text):
    target = touched.Target(Path(path), language, touched.WHOLE_FILE)
    return crap.crap_measurements(
        declaration, target, measured, crap.parse_lcov(lcov_text)
    )


def crap_by_function(records):
    return {record["function"]: record["value"] for record in records}


def flagged_functions(records):
    return sorted(
        record["function"] for record in records if functions.is_over_limit(record)
    )


class TestCrapScoring:
    def test_should_flag_an_uncovered_complexity_4_function_at_crap_20_and_pass_a_half_covered_one_at_6(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("apply_discount", 1, 10, 4),
            function_measure("round_to_cents", 12, 21, 4),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 0, 2: 0, 3: 0, 4: 0,
            12: 5, 13: 5, 14: 0, 15: 0,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        assert crap_by_function(records) == {"apply_discount": 20, "round_to_cents": 6}
        assert flagged_functions(records) == ["apply_discount"]

    def test_should_flag_complexity_8_at_exactly_crap_8_and_pass_complexity_7_at_full_coverage(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [
            function_measure("split_payment", 1, 20, 8),
            function_measure("sum_lines", 22, 40, 7),
        ]
        lcov_text = lcov_report(SOURCE_FILE, {
            1: 3, 2: 3, 3: 3, 22: 3, 23: 3, 24: 3,
        })

        records = measure_crap(declaration, "python", SOURCE_FILE, measured, lcov_text)

        assert crap_by_function(records) == {"split_payment": 8, "sum_lines": 7}
        assert flagged_functions(records) == ["split_payment"]


class TestCoverageOptOut:
    def test_should_score_crap_at_full_coverage_when_the_language_opts_coverage_out(
        self, tmp_path
    ):
        declaration = load_declaration(tmp_path)
        measured = [function_measure("deploy_release", 1, 30, 4)]
        no_coverage_data = ""

        opted_out = measure_crap(
            declaration, "bash", "bin/deploy.sh", measured, no_coverage_data
        )
        tool_failed = measure_crap(
            declaration, "python", SOURCE_FILE, measured, no_coverage_data
        )

        assert crap_by_function(opted_out) == {"deploy_release": 4}
        assert flagged_functions(opted_out) == []
        assert crap_by_function(tool_failed) == {"deploy_release": 20}
        assert flagged_functions(tool_failed) == ["deploy_release"]
