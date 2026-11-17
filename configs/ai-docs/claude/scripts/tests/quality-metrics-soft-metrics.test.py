"""Soft metrics (judge candidates) and metrics that may never
run per unit: declaration check, report routing, benchmark
placement.

Usage:
  ./run-tests.py <this file>
"""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import (
    load_measure_script,
    load_script,
    make_repo,
    run_measure,
)

declaring = importlib.import_module("quality_metrics.declaration")
failures = importlib.import_module("quality_metrics.failures")

BENCHMARK_SCRIPT = SCRIPTS_DIR / "benchmark-quality-metrics.py"
FAST_SECONDS = 0.1
EXIT_UNMEASURED = 2

DECLARATION = """\
ignored_extensions: [.md]
per_unit: [{per_unit}]
languages:
  python:
    extensions: [.py]
    metrics: [size]
"""


def over_limit_record(metric):
    return {
        "file": "src/pricing.py",
        "function": "price_cart",
        "scope": "function",
        "metric": metric,
        "value": 3,
        "limit": 0,
        "line": 4,
    }


def print_report_for(metric, capsys):
    script = load_measure_script()
    found = {
        "gate_input_violations": [],
        "not_applicable": [],
        "resolved": [],
        "unclaimed_files": [],
    }
    coverage_run = SimpleNamespace(sources=[], asks=[])

    exit_code = script._print_report([over_limit_record(metric)], found, coverage_run, None)

    return exit_code, json.loads(capsys.readouterr().out)


class TestPerUnitDeclaration:
    @pytest.mark.parametrize("metric", ["code_duplication", "type_errors"])
    def test_should_exit_2_when_per_unit_names_a_metric_that_may_never_run_per_unit(
        self, tmp_path, metric
    ):
        repo = make_repo(tmp_path, {"src/pricing.py": "x = 1\n"})
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION.format(per_unit=metric))

        result = run_measure(repo, declaration_path, "--files", "src/pricing.py")

        assert result.returncode == EXIT_UNMEASURED
        assert metric in result.stderr

    def test_should_accept_a_per_unit_list_of_metrics_that_run_fast(self, tmp_path):
        declaration_path = tmp_path / "quality-metrics.yaml"
        declaration_path.write_text(DECLARATION.format(per_unit="size"))

        declaration = declaring.load_declaration(declaration_path)

        assert declaration.per_unit == ("size",)


class TestSoftRouting:
    @pytest.mark.parametrize(
        ("metric", "key"),
        [
            ("dead_code", "dead_code_candidates"),
            ("mutation", "surviving_mutants"),
            ("code_duplication", "duplication_candidates"),
            ("test_duplication", "duplication_candidates"),
        ],
    )
    def test_should_list_an_over_limit_soft_record_under_its_own_key_not_violations(
        self, capsys, metric, key
    ):
        exit_code, report = print_report_for(metric, capsys)

        assert [item["metric"] for item in report[key]] == [metric]
        assert report["violations"] == []

    @pytest.mark.parametrize("metric", ["dead_code", "mutation"])
    def test_should_exit_0_when_a_soft_record_is_the_only_finding(self, capsys, metric):
        exit_code, _ = print_report_for(metric, capsys)

        assert exit_code == 0

    @pytest.mark.parametrize("metric", ["dead_code", "mutation"])
    def test_should_not_hold_the_commit_for_an_over_limit_soft_function_record(
        self, metric
    ):
        assert failures.holds_commit([over_limit_record(metric)]) is False

    def test_should_report_empty_soft_lists_when_nothing_soft_is_over_limit(self, capsys):
        _, report = print_report_for("size", capsys)

        assert report["dead_code_candidates"] == []
        assert report["surviving_mutants"] == []
        assert len(report["violations"]) == 1


class TestBenchmarkPlacement:
    def test_should_drop_every_never_per_unit_metric_even_when_it_times_fast(self):
        benchmark = load_script(BENCHMARK_SCRIPT, "benchmark_quality_metrics")
        timings = {"size": FAST_SECONDS}
        timings.update({metric: FAST_SECONDS for metric in declaring.NEVER_PER_UNIT_METRICS})

        assert benchmark.select_per_unit(timings) == ["size"]

    def test_should_never_run_a_judge_or_run_level_metric_per_unit(self):
        assert set(declaring.NEVER_PER_UNIT_METRICS) == {
            "code_duplication",
            "test_duplication",
            "unused_code",
            "type_errors",
            "dead_code",
            "mutation",
        }
