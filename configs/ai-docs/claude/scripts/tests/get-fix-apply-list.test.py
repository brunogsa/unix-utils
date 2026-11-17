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

## Deferred metrics (1)

### 1. [metrics] Mutation score deferred for billing/parse.py

## Open violations (2)

- `parse_invoice` in billing/parse.py:12 - cyclomatic complexity 14 (limit 10)
  **Record**: `cyclomatic billing/parse.py:12 parse_invoice`
- `load_rows` in billing/load.py:40 - cyclomatic complexity 12 (limit 10)
  **Record**: `cyclomatic billing/load.py:40 load_rows`

## Duplication candidates (1)

- billing/parse.py:10 - test duplication 1.00 (limit 0.82)
  **Record**: `test_duplication billing/parse.py:10 ~ billing/load.py:5`

## Findings

### 2. [HIGH][metrics] Split `parse_invoice` by input format

**Record**: `cyclomatic billing/parse.py:12 parse_invoice`

### 3. [MEDIUM][metrics] Extract the shared row fixture

**Record**: `test_duplication billing/parse.py:10 ~ billing/load.py:5`

{SKIP_RULING}
### 4. [MEDIUM][refactor] Split the long function in billing/load.py

### 5. [LOW][auto-review] Null dereference in the invoice parser

### 6. [LOW][test-sdd] Missing planned test - task 2: "sums a column"

### 7. [LOW] Untagged finding about a missing planned test

### 8. [Done][HIGH][refactor] Already applied extraction

### 9. [QUESTION][MEDIUM][auto-review] Is the rounding intended?

### 10. [HIGH][auto-review] Wrong tax base in the invoice total

{SKIP_RULING}
## Dismissed records

- `cyclomatic billing/load.py:40 load_rows`: "Split a function past the limit" fits a table-driven loader badly; considered fix: one branch per column

## Fix review (1)

### 11. [HIGH][refactor] Extraction still pending review
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
        assert completed.stdout.splitlines() == ["2", "4", "5"]

    def test_should_never_list_a_numbered_entry_under_a_raw_metrics_record_section_since_only_judge_findings_enter(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            "## Open violations (1)\n\n"
            "### 1. Cyclomatic complexity of `parse_invoice` in billing/parse.py - 14, limit 10\n\n"
            "## Gate input violations (1)\n\n"
            "### 2. Missing coverage input in billing/parse.py - 0 lines measured\n\n"
            "## Findings\n\n"
            "### 3. [HIGH][metrics] Split `parse_invoice` by input format\n",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == ["3"]

    def test_should_print_nothing_when_no_entry_is_in_scope(self, tmp_path):
        verdict = _write(
            tmp_path,
            "## Findings\n\n### 1. [LOW][test-sdd] Missing planned test\n",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""

    def test_should_list_a_scout_finding_ruled_fix_while_leaving_off_a_scout_finding_the_judge_skipped_or_the_human_marked_done(
        self, tmp_path
    ):
        verdict = _write(
            tmp_path,
            "## Findings\n\n"
            "### 1. [MEDIUM][scout] Stale retry comment in the invoice parser\n\n"
            f"**Scout task**: #43\n\n{FIX_RULING}\n"
            "### 2. [LOW][scout] Dead config key in billing/settings.py\n\n"
            f"**Scout task**: #44\n\n{SKIP_RULING}\n"
            "### 3. [Done][LOW][scout] Unused mock in the parser spec\n\n"
            f"**Scout task**: #45\n\n{FIX_RULING}",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == ["1"]

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
