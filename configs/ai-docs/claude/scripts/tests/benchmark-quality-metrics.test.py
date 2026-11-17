"""Tests for benchmark-quality-metrics.py: which metrics the
benchmark puts in the declaration's per_unit list.

Usage:
  ./run-tests.py <this file>
"""

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import load_script

declaring = importlib.import_module("quality_metrics.declaration")
DUPLICATION_METRICS = importlib.import_module("quality_metrics.duplication").DUPLICATION_METRICS

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
    """Run the script once; a wrong SCRIPT path names itself."""
    return load_script(SCRIPT, "benchmark_quality_metrics")


benchmark = load_benchmark()


@pytest.fixture
def declaration_path(tmp_path):
    """A fresh copy of DECLARATION_BODY on disk."""
    (tmp_path / "quality-metrics.yaml").write_text(DECLARATION_BODY)
    return tmp_path / "quality-metrics.yaml"


class TestRunMeasured:
    def test_should_count_a_run_that_only_produced_pessimistic_results_as_measured(self):
        red_build_report = (
            '{"measurements": [{"metric": "coverage", "value": 0,'
            ' "pessimistic": true}]}'
        )

        assert benchmark.run_measured(1, red_build_report)

    def test_should_count_a_run_that_reports_a_real_violation_as_measured(self):
        report = '{"measurements": [{"metric": "size", "value": 61}]}'

        assert benchmark.run_measured(1, report)

    def test_should_leave_out_a_check_whose_run_could_not_measure(self):
        assert not benchmark.run_measured(benchmark.measuring.EXIT_UNMEASURED, "")


class TestDeclaredForTiming:
    def test_should_declare_coverage_beside_crap_so_the_test_run_is_timed(self):
        assert benchmark.metrics_declared_for("crap") == ["crap", "coverage"]

    def test_should_declare_only_the_check_itself_for_any_other_metric(self):
        assert benchmark.metrics_declared_for("size") == ["size"]


PESSIMISTIC_STUB = """\
import sys
print('{"measurements": [{"metric": "size", "value": 0, "pessimistic": true}]}')
sys.exit(1)
"""


class TestMetricsTimed:
    def test_should_time_every_metric_the_measure_script_can_run_including_dependency_direction(self):
        assert "dependency_direction" in benchmark.metrics_with_a_module()


class TestPessimisticMetric:
    def test_should_keep_a_quick_metric_in_per_unit_and_not_exit_2_when_its_run_reads_pessimistic(
        self, declaration_path, tmp_path, monkeypatch
    ):
        stub = tmp_path / "pessimistic-stub.py"
        stub.write_text(PESSIMISTIC_STUB)
        monkeypatch.setattr(benchmark, "MEASURE_SCRIPT", stub)
        monkeypatch.setattr(benchmark, "metrics_with_a_module", lambda: ["size"])

        exit_code = benchmark.main(["--declaration", str(declaration_path)])

        assert exit_code == 0
        assert "per_unit: [size]" in declaration_path.read_text()


class TestMainGuards:
    def test_should_leave_per_unit_unchanged_and_exit_2_when_a_sample_file_is_missing(
        self, declaration_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(benchmark, "SAMPLE_FILES", ("no/such/sample.py",))

        exit_code = benchmark.main(["--declaration", str(declaration_path)])

        assert exit_code == 2
        assert "per_unit: []" in declaration_path.read_text()
        assert "no/such/sample.py" in capsys.readouterr().err

    def test_should_exit_2_with_one_stderr_line_naming_the_path_before_timing_anything_when_the_declaration_does_not_exist(
        self, tmp_path, monkeypatch, capsys
    ):
        missing = tmp_path / "no-such-dir" / "quality-metrics.yaml"

        def fail_if_timed(repo_root):
            raise AssertionError("timed the metrics before checking the declaration")

        monkeypatch.setattr(benchmark, "benchmark", fail_if_timed)

        exit_code = benchmark.main(["--declaration", str(missing)])

        error_lines = capsys.readouterr().err.strip().splitlines()
        assert exit_code == 2
        assert len(error_lines) == 1
        assert str(missing) in error_lines[0]

    def test_should_exit_2_and_leave_the_file_untouched_when_a_block_style_per_unit_list_would_break_the_rewrite(
        self, declaration_path, monkeypatch
    ):
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

    def test_should_never_place_a_duplication_check_per_unit_even_when_it_times_fast(self):
        fast = 0.1
        timings = {"size": fast, **{metric: fast for metric in DUPLICATION_METRICS}}

        selected = benchmark.select_per_unit(timings)

        assert selected == ["size"]

    def test_should_place_a_check_from_the_declaration_alone_with_no_timing_at_run_time(
        self, declaration_path
    ):
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

    def test_should_keep_the_declarations_comments_on_rewrite(self, declaration_path):

        benchmark.write_per_unit(declaration_path, ["size"])

        assert "Placement rule comment that must survive" in declaration_path.read_text()
