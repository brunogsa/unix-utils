"""The record key the metrics verdict prints under each raw
record a judge must rule on, so the judge can copy it into a
finding's `**Record**:` line or a dismissal line.

Usage:
  ./run-tests.py <this file>
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import (
    crap_record,
    file_record,
    function_record,
    measured,
    report,
)
from quality_metrics_support import verdict_section as section

RECORD_LINE = re.compile(r"^  \*\*Record\*\*: `(?P<key>[^`]+)`$", re.M)


def _duplicate(file, line, other_file, other_line):
    return {
        **file_record(file, "test_duplication", 1.0, 0.82),
        "line": line, "other_file": other_file, "other_line": other_line,
    }


def _ruled_run():
    """A report with one record in every section a judge rules
    on, plus sections it never rules on."""
    return {
        **measured(
            function_record("src/cells.py", "splitCells", "crap", 36, 16),
            file_record("src/a.py", "unused_code", 2, 0),
            _duplicate("tests/cells_test.py", 186, "tests/cells_test.py", 874),
        ),
        "gate_input_violations": [
            {"kind": "opt_out", "file": "layers.yaml", "value": "ts.size"}
        ],
        "dead_code_candidates": [{
            "file": "src/a.py", "line": 7, "function": None, "scope": "file",
            "metric": "dead_code", "value": 1, "limit": 0,
            "name": "unused_helper", "kind": "function", "tool": "vulture",
        }],
        "surviving_mutants": [{
            "file": "src/a.py", "line": 4, "scope": "file", "metric": "mutation",
            "value": 1, "limit": 0, "mutator": "ArithmeticOperator",
            "replacement": "a - b", "status": "survived",
        }],
        "mutants_not_run": [
            {"file": "src/c.ts", "lines": "10-20", "label": "not run (budget)"}
        ],
        "sources": [{
            "metric": "coverage", "language": "python",
            "source": {"kind": "repo", "tool": "pytest-cov"},
            "exit_class": None, "side_pr_candidate": None,
        }],
    }


class TestRecordLineUnderEachRuledRecord:
    @pytest.mark.parametrize("section_title, key", [
        ("Open violations", "crap src/cells.py:10 splitCells"),
        ("Open violations", "unused_code src/a.py"),
        ("Gate input violations", "opt_out layers.yaml"),
        ("Duplication candidates", "test_duplication tests/cells_test.py:186 ~ tests/cells_test.py:874"),
        ("Dead code candidates", "dead_code src/a.py:7 unused_helper"),
        ("Surviving mutants", "mutation src/a.py:4 ArithmeticOperator"),
    ])
    def test_should_print_the_records_key_on_the_line_right_under_its_bullet(
        self, section_title, key
    ):
        lines = section(report.build_verdict(_ruled_run()), section_title).splitlines()

        record_line = f"  **Record**: `{key}`"
        assert record_line in lines
        assert lines[lines.index(record_line) - 1].startswith("- ")

    @pytest.mark.parametrize("section_title", ["Mutants not run", "Coverage sources"])
    def test_should_print_no_record_key_in_a_section_no_judge_rules_on(self, section_title):
        listed = section(report.build_verdict(_ruled_run()), section_title)

        assert RECORD_LINE.findall(listed) == []

    def test_should_give_two_records_with_the_same_location_distinct_keys_by_report_order(self):
        clone = _duplicate("tests/cells_test.py", 186, "tests/cells_test.py", 874)
        run = measured(clone, dict(clone))

        listed = section(report.build_verdict(run), "Duplication candidates")

        assert RECORD_LINE.findall(listed) == [
            "test_duplication tests/cells_test.py:186 ~ tests/cells_test.py:874",
            "test_duplication tests/cells_test.py:186 ~ tests/cells_test.py:874 #2",
        ]

    def test_should_print_no_record_key_for_a_violation_the_judge_accepted_as_an_exception(
        self, tmp_path
    ):
        split_diff = tmp_path / "split_buildReport.diff"
        split_diff.write_text("--- a/src/report.py\n+++ b/src/report.py\n")
        claim = {
            "file": "src/report.py", "function": "buildReport", "metric": "crap",
            "split_value": 6, "diff_path": str(split_diff), "rejected": False,
        }

        verdict = report.build_verdict(
            measured(crap_record("src/report.py", "buildReport", 42)), exceptions=[claim]
        )

        assert RECORD_LINE.findall(verdict) == []
