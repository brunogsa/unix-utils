"""Blackbox CLI tests for get-fix-apply-list.py.

Fixtures: each test writes a throwaway verdict_quality-gate_*.md
under tmp_path and runs the script on it. Nothing reads the
live repo.

Usage:
  ./run-tests.py <this file>
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "get-fix-apply-list.py"

FIX_RULING = "**Standards check**: Fix\n"
SKIP_RULING = (
    '**Standards check**: Skip - "Split a function past the limit"; '
    "considered fix: extract the date parsing\n"
    "SKIPPED (judge ruled Skip)\n"
)

MERGED_VERDICT_BODY = f"""# quality-gate verdict

## Open violations (2)

### 1. Cyclomatic complexity of `parse_invoice` in billing/parse.py - 14, limit 10

### 2. Cyclomatic complexity of `load_rows` in billing/load.py - 12, limit 10

{SKIP_RULING}
## Gate input violations (1)

### 3. Missing coverage input in billing/parse.py - 0 lines measured

## Duplication candidates (1)

### 4. billing/parse.py:10-30 repeats billing/load.py:5-25

## Findings

### 5. [HIGH][metrics] CRAP score over the limit in billing/parse.py

### 6. [MEDIUM][refactor] Split the long function in billing/load.py

### 7. [LOW][auto-review] Null dereference in the invoice parser

### 8. [LOW][test-sdd] Missing planned test - task 2: "sums a column"

### 9. [LOW] Untagged finding about a missing planned test

### 10. [Done][HIGH][refactor] Already applied extraction

### 11. [QUESTION][MEDIUM][auto-review] Is the rounding intended?

### 12. [HIGH][auto-review] Wrong tax base in the invoice total

{SKIP_RULING}
## Fix review (1)

### 13. [HIGH][refactor] Extraction still pending review
"""


def _run(verdict, *flags):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *flags, str(verdict)],
        capture_output=True,
        text=True,
    )


def _write(tmp_path, body):
    verdict = tmp_path / "verdict_quality-gate_master_2026-11-17_10:00.md"
    verdict.write_text(body, encoding="utf-8")
    return verdict


class TestEntriesTheFixStepApplies:
    def test_should_list_only_the_in_scope_entries_the_judge_did_not_skip_in_file_order(
        self, tmp_path
    ):
        verdict = _write(tmp_path, MERGED_VERDICT_BODY)

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == ["1", "3", "5", "6", "7"]

    def test_should_print_nothing_when_no_entry_is_in_scope(self, tmp_path):
        verdict = _write(
            tmp_path,
            "## Findings\n\n### 1. [LOW][test-sdd] Missing planned test\n",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""

    def test_should_exit_1_naming_the_file_when_the_verdict_is_unreadable(
        self, tmp_path
    ):
        completed = _run(tmp_path / "missing.md")

        assert completed.returncode == 1
        assert "missing.md" in completed.stderr


class TestFencedTextInsideAnEntryBody:
    def test_should_not_start_a_finding_at_a_heading_line_inside_a_code_fence(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            "## Findings\n\n"
            "### 1. [HIGH][refactor] Split the parser\n\n"
            "```md\n### 99. [HIGH][refactor] x\n```\n",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == ["1"]

    def test_should_keep_an_entry_on_the_list_when_its_skipped_line_sits_inside_a_code_fence(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            "## Findings\n\n"
            "### 1. [HIGH][refactor] Split the parser\n\n"
            "```\nSKIPPED (judge ruled Skip)\n```\n",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == ["1"]


def _finding(ruling, section="## Findings", heading="### 4. [HIGH][refactor] Split"):
    return f"{section}\n\n{heading}\n\n{ruling}"


class TestJudgeRulingCheck:
    def test_should_flag_an_entry_holding_two_standards_check_lines(self, tmp_path):
        verdict = _write(tmp_path, _finding(FIX_RULING + FIX_RULING))

        completed = _run(verdict, "--check")

        assert completed.returncode == 1
        assert completed.stdout.startswith("4: ")
        assert "more than one" in completed.stdout

    def test_should_flag_a_ruling_that_is_neither_fix_nor_a_skip_with_a_rule_and_a_considered_fix(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            _finding('**Standards check**: Skip - "a rule"\nSKIPPED (judge ruled Skip)\n'),
        )

        completed = _run(verdict, "--check")

        assert completed.returncode == 1
        assert completed.stdout.startswith("4: ")
        assert "neither" in completed.stdout

    def test_should_flag_a_skip_whose_considered_fix_is_empty(self, tmp_path):
        verdict = _write(
            tmp_path,
            _finding(
                '**Standards check**: Skip - "a rule"; considered fix: \n'
                "SKIPPED (judge ruled Skip)\n"
            ),
        )

        completed = _run(verdict, "--check")

        assert completed.returncode == 1
        assert completed.stdout.startswith("4: ")

    def test_should_flag_a_skip_with_no_skipped_line_after_it(self, tmp_path):
        verdict = _write(
            tmp_path,
            _finding(
                '**Standards check**: Skip - "Split a function past the limit"; '
                "considered fix: extract the date parsing\n"
            ),
        )

        completed = _run(verdict, "--check")

        assert completed.returncode == 1
        assert completed.stdout.startswith("4: ")
        assert "SKIPPED" in completed.stdout

    def test_should_flag_a_skip_that_cites_a_standards_file_by_name_instead_of_quoting_the_rule(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            _finding(
                '**Standards check**: Skip - "code-standards says keep it"; '
                "considered fix: extract the date parsing\n"
                "SKIPPED (judge ruled Skip)\n"
            ),
        )

        completed = _run(verdict, "--check")

        assert completed.returncode == 1
        assert completed.stdout.startswith("4: ")
        assert "quote" in completed.stdout

    def test_should_flag_a_ruling_over_the_char_cap_on_an_open_violations_entry(
        self, tmp_path
    ):
        long_ruling = (
            '**Standards check**: Skip - "Split a function past the limit"; '
            "considered fix: " + "extract the date parsing " * 30 + "\n"
            "SKIPPED (judge ruled Skip)\n"
        )
        verdict = _write(
            tmp_path,
            _finding(
                long_ruling,
                section="## Open violations (1)",
                heading="### 4. Cyclomatic complexity of `parse_invoice` - 14",
            ),
        )

        completed = _run(verdict, "--check")

        assert completed.returncode == 1
        assert completed.stdout.startswith("4: ")
        assert "chars" in completed.stdout

    def test_should_accept_a_fix_a_no_ruling_entry_and_a_well_formed_skip(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            "## Findings\n\n"
            f"### 1. [HIGH][refactor] Split the parser\n\n{FIX_RULING}\n"
            "### 2. [HIGH][metrics] No ruling yet\n\n"
            f"### 3. [HIGH][auto-review] Wrong tax base\n\n{SKIP_RULING}",
        )

        completed = _run(verdict, "--check")

        assert completed.returncode == 0, completed.stdout
        assert completed.stdout == ""
