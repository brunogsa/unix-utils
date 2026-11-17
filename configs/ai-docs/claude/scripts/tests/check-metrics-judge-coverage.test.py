"""Blackbox CLI tests for check-metrics-judge-coverage.py: every
record a metrics judge must rule on is cited by exactly one
`[metrics]` finding or exactly one dismissal line.

Fixtures: each test writes a throwaway metrics-report.json and
metrics-judge_*.md under tmp_path. Nothing reads the live repo.

Usage:
  ./run-tests.py <this file>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_report_support import report

SCRIPT = Path(__file__).resolve().parent.parent / "check-metrics-judge-coverage.py"

SPEC = "tests/merged_agreement_test.py"

LONG_TEST_BODY_KEY = f"size {SPEC}:184 (anonymous)"
LONGER_TEST_BODY_KEY = f"size {SPEC}:657 (anonymous)"
UNUSED_VARIABLE_KEY = "unused_code src/merged_agreement.py"
FIXTURE_CLONE_KEY = f"test_duplication {SPEC}:186 ~ {SPEC}:874"
DEAD_ERROR_KEY = "dead_code src/errors.py:6 InvalidItemDisciplineError"
SURVIVING_MUTANT_KEY = "mutation src/merged_agreement.py:42 ArithmeticOperator"
OPT_OUT_KEY = "opt_out quality-metrics.yaml"

EVERY_KEY = [
    LONG_TEST_BODY_KEY, LONGER_TEST_BODY_KEY, UNUSED_VARIABLE_KEY, OPT_OUT_KEY,
    FIXTURE_CLONE_KEY, DEAD_ERROR_KEY, SURVIVING_MUTANT_KEY,
]


def _size(line, value):
    return {
        "file": SPEC, "function": "(anonymous)", "scope": "function",
        "metric": "size", "value": value, "limit": 256, "line": line,
    }


def _report():
    """A report shaped like the PR5 run: two anonymous test
    bodies over the size limit in one file, so only the line
    tells their keys apart."""
    unused = {
        "file": "src/merged_agreement.py", "function": None, "scope": "file",
        "metric": "unused_code", "value": 1, "limit": 0, "line": None,
        "findings": [{"line": 106, "rule": "F841", "name": "derived_later"}],
    }
    violations = [_size(184, 407), _size(657, 936), unused]
    return {
        "measurements": violations,
        "violations": violations,
        "gate_input_violations": [
            {"kind": "opt_out", "file": "quality-metrics.yaml", "value": "python.size"}
        ],
        "duplication_candidates": [{
            "file": SPEC, "function": None, "scope": "file",
            "metric": "test_duplication", "value": 1.0, "limit": 0.82,
            "line": 186, "other_file": SPEC, "other_line": 874,
        }],
        "dead_code_candidates": [{
            "file": "src/errors.py", "function": None, "scope": "file",
            "metric": "dead_code", "value": 1, "limit": 0, "line": 6,
            "name": "InvalidItemDisciplineError", "kind": "class", "tool": "vulture",
        }],
        "surviving_mutants": [{
            "file": "src/merged_agreement.py", "line": 42, "scope": "file",
            "metric": "mutation", "value": 1, "limit": 0,
            "mutator": "ArithmeticOperator", "replacement": "total - fee",
            "status": "survived",
        }],
    }


def _finding(number, *keys, severity="MEDIUM"):
    records = ", ".join(f"`{key}`" for key in keys)
    return (
        f"### {number}. [{severity}][metrics] Split the long merged-agreement test body\n\n"
        "**[RECOMMENDED]**\n\n"
        f"**Record**: {records}\n\n"
        "The test body holds 3 arrange blocks.\n\n"
        "**Suggestion**\n\n"
        "Move each scenario into its own test.\n\n"
        "**Trade-off of not doing it**\n\n"
        "A failure names the whole body, not the scenario.\n"
    )


def _dismissal(key, reason="the clone is a fixture; a shared one hides what each test asserts"):
    return f"- `{key}`: {reason}\n"


def _judge(findings=(), dismissals=()):
    return (
        "# Metrics judge\n\n## Findings\n\n" + "\n".join(findings)
        + "\n## Dismissed records\n\n" + "".join(dismissals)
    )


def _run(tmp_path, judge_text, report_body=None, *flags):
    report_path = tmp_path / "metrics-report.json"
    report_path.write_text(json.dumps(report_body or _report()), encoding="utf-8")
    judge_path = tmp_path / "metrics-judge_2026-11-17_1201.md"
    judge_path.write_text(judge_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--report", str(report_path),
         "--judge", str(judge_path), *flags],
        capture_output=True, text=True,
    )


def _every_key_but(*left_out):
    return [key for key in EVERY_KEY if key not in left_out]


class TestEveryRecordRuledOnce:
    def test_should_pass_when_each_key_copied_from_the_rendered_verdict_is_in_one_finding_or_one_dismissal(
        self, tmp_path
    ):
        rendered = report.build_verdict(_report())
        keys = re.findall(r"^  \*\*Record\*\*: `([^`]+)`$", rendered, re.M)
        assert sorted(keys) == sorted(EVERY_KEY)
        judge = _judge(
            findings=[
                _finding(1, LONG_TEST_BODY_KEY, LONGER_TEST_BODY_KEY),
                _finding(2, *_every_key_but(LONG_TEST_BODY_KEY, LONGER_TEST_BODY_KEY, FIXTURE_CLONE_KEY)),
            ],
            dismissals=[_dismissal(FIXTURE_CLONE_KEY)],
        )

        completed = _run(tmp_path, judge)

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert completed.stdout == ""

    def test_should_count_a_question_finding_as_the_records_ruling(self, tmp_path):
        judge = _judge(findings=[_finding(1, *EVERY_KEY, severity="QUESTION")])

        completed = _run(tmp_path, judge)

        assert completed.returncode == 0, completed.stdout + completed.stderr


class TestRecordsRuledWrong:
    def test_should_fail_naming_the_key_no_finding_and_no_dismissal_cites(self, tmp_path):
        judge = _judge(findings=[_finding(1, *_every_key_but(DEAD_ERROR_KEY))])

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [f"{DEAD_ERROR_KEY}: no finding and no dismissal"]

    def test_should_fail_naming_the_key_both_a_finding_and_a_dismissal_cite(self, tmp_path):
        judge = _judge(
            findings=[_finding(1, *EVERY_KEY)], dismissals=[_dismissal(FIXTURE_CLONE_KEY)]
        )

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [
            f"{FIXTURE_CLONE_KEY}: cited 2 times (1 finding, 1 dismissal)"
        ]

    def test_should_fail_naming_the_key_two_findings_cite(self, tmp_path):
        judge = _judge(findings=[_finding(1, *EVERY_KEY), _finding(2, OPT_OUT_KEY)])

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [
            f"{OPT_OUT_KEY}: cited 2 times (2 findings, 0 dismissals)"
        ]

    def test_should_fail_naming_the_key_two_dismissals_cite(self, tmp_path):
        judge = _judge(
            findings=[_finding(1, *_every_key_but(DEAD_ERROR_KEY))],
            dismissals=[_dismissal(DEAD_ERROR_KEY), _dismissal(DEAD_ERROR_KEY)],
        )

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [
            f"{DEAD_ERROR_KEY}: cited 2 times (0 findings, 2 dismissals)"
        ]

    def test_should_fail_naming_a_cited_key_the_report_does_not_hold(self, tmp_path):
        mistyped = f"size {SPEC}:18 (anonymous)"
        judge = _judge(findings=[_finding(1, *EVERY_KEY, mistyped)])

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [f"{mistyped}: not a record in the report"]

    def test_should_fail_a_dismissal_line_with_no_reason(self, tmp_path):
        judge = _judge(
            findings=[_finding(1, *_every_key_but(DEAD_ERROR_KEY))],
            dismissals=[f"- `{DEAD_ERROR_KEY}`:  \n"],
        )

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [f"{DEAD_ERROR_KEY}: dismissal gives no reason"]

    def test_should_fail_a_line_in_the_dismissal_section_that_is_not_one_key_and_its_reason(
        self, tmp_path
    ):
        judge = _judge(
            findings=[_finding(1, *EVERY_KEY)],
            dismissals=["The remaining clones are fixtures, so all of them stay.\n"],
        )

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [
            "malformed dismissal line: The remaining clones are fixtures, so all of them stay."
        ]


class TestCitationsThatCountForNothing:
    def test_should_not_count_a_record_line_inside_a_code_fence(self, tmp_path):
        fenced = f"```\n**Record**: `{DEAD_ERROR_KEY}`\n```\n"
        judge = _judge(findings=[_finding(1, *_every_key_but(DEAD_ERROR_KEY)) + fenced])

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [f"{DEAD_ERROR_KEY}: no finding and no dismissal"]

    def test_should_not_count_a_record_line_under_a_finding_of_another_lens(self, tmp_path):
        other_lens = (
            "### 2. [LOW][refactor] Rename the error class\n\n"
            f"**Record**: `{DEAD_ERROR_KEY}`\n"
        )
        judge = _judge(findings=[_finding(1, *_every_key_but(DEAD_ERROR_KEY)), other_lens])

        completed = _run(tmp_path, judge)

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [f"{DEAD_ERROR_KEY}: no finding and no dismissal"]


class TestExceptionClaims:
    def _claim(self, tmp_path, rejected):
        split_diff = tmp_path / "split.diff"
        split_diff.write_text("--- a/tests/merged_agreement_test.py\n")
        claims_path = tmp_path / "metrics-exceptions.json"
        claims_path.write_text(json.dumps([{
            "file": SPEC, "function": "(anonymous)", "metric": "size",
            "diff_path": str(split_diff), "split_value": 120, "rejected": rejected,
        }]))
        return claims_path

    def test_should_require_no_ruling_for_a_violation_the_judge_accepted_as_an_exception(
        self, tmp_path
    ):
        claims_path = self._claim(tmp_path, rejected=False)
        judge = _judge(findings=[_finding(1, *_every_key_but(LONG_TEST_BODY_KEY, LONGER_TEST_BODY_KEY))])

        completed = _run(tmp_path, judge, None, "--exceptions", str(claims_path))

        assert completed.returncode == 0, completed.stdout + completed.stderr

    def test_should_require_a_ruling_for_a_violation_whose_exception_the_judge_rejected(
        self, tmp_path
    ):
        claims_path = self._claim(tmp_path, rejected=True)
        judge = _judge(findings=[_finding(1, *_every_key_but(LONG_TEST_BODY_KEY, LONGER_TEST_BODY_KEY))])

        completed = _run(tmp_path, judge, None, "--exceptions", str(claims_path))

        assert completed.returncode == 1
        assert completed.stdout.splitlines() == [
            f"{LONG_TEST_BODY_KEY}: no finding and no dismissal",
            f"{LONGER_TEST_BODY_KEY}: no finding and no dismissal",
        ]


class TestUnusableInput:
    def test_should_exit_2_naming_the_judge_file_when_it_is_missing(self, tmp_path):
        report_path = tmp_path / "metrics-report.json"
        report_path.write_text(json.dumps(_report()))

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--report", str(report_path),
             "--judge", str(tmp_path / "metrics-judge_missing.md")],
            capture_output=True, text=True,
        )

        assert completed.returncode == 2
        assert "metrics-judge_missing.md" in completed.stderr

    def test_should_exit_2_naming_the_report_when_it_is_not_json(self, tmp_path):
        report_path = tmp_path / "metrics-report.json"
        report_path.write_text("measure crashed\n")
        judge_path = tmp_path / "metrics-judge.md"
        judge_path.write_text(_judge())

        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--report", str(report_path), "--judge", str(judge_path)],
            capture_output=True, text=True,
        )

        assert completed.returncode == 2
        assert "metrics-report.json" in completed.stderr
