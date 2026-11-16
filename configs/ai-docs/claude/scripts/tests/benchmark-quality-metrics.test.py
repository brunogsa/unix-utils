"""Tests for benchmark-quality-metrics.py: which metrics the benchmark
puts in the declaration's per_unit list.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/benchmark-quality-metrics.test.py
"""

import importlib
import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
declaring = importlib.import_module("quality_metrics.declaration")

SCRIPT = SCRIPTS_DIR / "benchmark-quality-metrics.py"

DECLARATION_BODY = """\
# Placement rule comment that must survive a rewrite.
ignored_extensions: [.md]

per_unit: []

languages:
  python:
    extensions: [.py]
    metrics: [size, nesting, crap, dependency_direction]
"""


def load_benchmark():
    spec = importlib.util.spec_from_file_location("benchmark_quality_metrics", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


benchmark = load_benchmark()


def write_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION_BODY)
    return path


class TestRunMeasured:
    def test_should_leave_out_a_check_whose_run_only_produced_pessimistic_results(self):
        red_build_report = (
            '{"measurements": [{"metric": "coverage", "value": 0,'
            ' "pessimistic": true}]}'
        )

        assert not benchmark.run_measured(1, red_build_report)

    def test_should_count_a_run_that_reports_a_real_violation_as_measured(self):
        report = '{"measurements": [{"metric": "size", "value": 61}]}'

        assert benchmark.run_measured(1, report)

    def test_should_leave_out_a_check_whose_run_could_not_measure(self):
        assert not benchmark.run_measured(benchmark.MEASURE_EXIT_UNMEASURED, "")


class TestDeclaredForTiming:
    def test_should_declare_coverage_beside_crap_so_the_test_run_is_timed(self):
        assert benchmark.metrics_declared_for("crap") == ["crap", "coverage"]

    def test_should_declare_only_the_check_itself_for_any_other_metric(self):
        assert benchmark.metrics_declared_for("size") == ["size"]


class TestMainGuards:
    def test_should_leave_per_unit_unchanged_and_exit_2_when_a_sample_file_is_missing(
        self, tmp_path, monkeypatch, capsys
    ):
        declaration_path = write_declaration(tmp_path)
        monkeypatch.setattr(benchmark, "SAMPLE_FILES", ("no/such/sample.py",))

        exit_code = benchmark.main(["--declaration", str(declaration_path)])

        assert exit_code == 2
        assert "per_unit: []" in declaration_path.read_text()
        assert "no/such/sample.py" in capsys.readouterr().err

    def test_should_exit_2_and_leave_the_file_untouched_when_a_block_style_per_unit_list_would_break_the_rewrite(
        self, tmp_path, monkeypatch
    ):
        declaration_path = write_declaration(tmp_path)
        block_style = DECLARATION_BODY.replace("per_unit: []", "per_unit:\n  - size")
        declaration_path.write_text(block_style)
        monkeypatch.setattr(benchmark, "SAMPLE_FILES", ())
        monkeypatch.setattr(benchmark, "benchmark", lambda repo_root: {})

        exit_code = benchmark.main(["--declaration", str(declaration_path)])

        assert exit_code == 2
        assert declaration_path.read_text() == block_style


class TestPerUnitSelection:
    def test_should_keep_a_check_timed_at_exactly_the_limit(self):
        limit = benchmark.PER_UNIT_LIMIT_SECONDS

        selected = benchmark.select_per_unit({"size": limit, "nesting": 0.4})

        assert selected == ["size", "nesting"]

    def test_should_leave_out_a_check_timed_just_over_the_limit(self):
        limit = benchmark.PER_UNIT_LIMIT_SECONDS

        selected = benchmark.select_per_unit({"size": 0.3, "crap": limit + 0.1})

        assert selected == ["size"]

    def test_should_place_a_check_from_the_declaration_alone_with_no_timing_at_run_time(
        self, tmp_path
    ):
        declaration_path = write_declaration(tmp_path)
        limit = benchmark.PER_UNIT_LIMIT_SECONDS
        benchmark.write_per_unit(
            declaration_path,
            benchmark.select_per_unit({"size": limit - 0.1, "crap": limit + 4.5}),
        )

        # A parallel run times size at 10 s, yet placement
        # gets no timing: it reads only the declaration.
        declaration = declaring.load_declaration(declaration_path)
        placed = declaring.metrics_to_run(declaration, "python", declaring.PER_UNIT_MODE)

        assert placed == ("size",)

    def test_should_keep_the_declarations_comments_on_rewrite(self, tmp_path):
        declaration_path = write_declaration(tmp_path)

        benchmark.write_per_unit(declaration_path, ["size"])

        assert "Placement rule comment that must survive" in declaration_path.read_text()
