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
