"""Blackbox CLI tests for get-test-sdd-dispatch-list.py.

Fixtures: each test writes a throwaway verdict_test-sdd_*.md
under tmp_path and runs the script on it. Nothing reads the
live repo.

Usage:
  ./run-tests.py <this file>
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "get-test-sdd-dispatch-list.py"

VERDICT_BODY = """# test-sdd verdict

## Findings

### 1. [HIGH] Missing planned test - task 3: "parses a quoted field"

- **Task:** 3 - Parse quoted fields

### 2. [LOW] Unplanned tests added by the branch

- tests/parse.test.ts:39 rejects an empty row

### 3. [Done][HIGH] Missing planned test - task 4: "sums a column"

- **Task:** 4 - Sum a column

```md
### 4. [HIGH] Missing planned test - task 9: "inside a fence"
```
"""


MERGED_VERDICT_BODY = """# quality-gate verdict

## Findings

### 1. [HIGH][auto-review] Null dereference in parser

### 2. [MEDIUM][refactor][LINTER GAP] Split the long function

### 3. [LOW][metrics] CRAP score over the limit

### 4. [LOW][test-sdd] Missing planned test - task 2: "x"
"""


def _run(verdict):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(verdict)],
        capture_output=True,
        text=True,
    )


def _assert_nothing_dispatched(verdict, findings):
    verdict.write_text("## Findings\n\n" + findings, encoding="utf-8")

    completed = _run(verdict)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


class TestTestSddFindingsSentToTddCoder:
    def test_should_keep_the_unplanned_tests_finding_off_the_tdd_coder_dispatch_list_while_a_missing_planned_test_stays_on_it(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_test-sdd_master_2026-11-15_10:00.md"
        verdict.write_text(VERDICT_BODY, encoding="utf-8")

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            '### 1. [HIGH] Missing planned test - task 3: "parses a quoted field"',
            '### 3. [Done][HIGH] Missing planned test - task 4: "sums a column"',
        ]

    def test_should_keep_a_finding_the_human_marked_for_address_verdicts_on_the_dispatch_list_whether_the_mark_carries_a_message_or_not(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_test-sdd_master_2026-11-15_10:00.md"
        verdict.write_text(
            "## Findings\n\n"
            "### 1. [AI!][HIGH] Some planned test\n\n"
            "### 2. [AI!: use the csv fixture][MEDIUM] Other test\n\n"
            "### 3. [AI! use the csv fixture][LOW] Third test\n",
            encoding="utf-8",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            "### 1. [AI!][HIGH] Some planned test",
            "### 2. [AI!: use the csv fixture][MEDIUM] Other test",
            "### 3. [AI! use the csv fixture][LOW] Third test",
        ]

    def test_should_keep_the_unplanned_tests_finding_off_the_dispatch_list_even_when_the_human_marked_it_for_address_verdicts(
        self, tmp_path
    ):
        _assert_nothing_dispatched(
            tmp_path / "verdict_test-sdd_master_2026-11-15_10:00.md",
            "### 3. [AI!][LOW] Unplanned tests added by the branch\n",
        )

    def test_should_list_only_the_test_sdd_finding_from_a_merged_verdict_holding_one_finding_per_review_source(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_quality-gate_master_2026-11-16_10:00.md"
        verdict.write_text(MERGED_VERDICT_BODY, encoding="utf-8")

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            '### 4. [LOW][test-sdd] Missing planned test - task 2: "x"',
        ]

    def test_should_keep_the_unplanned_tests_finding_off_the_list_when_the_merged_verdict_tags_it_test_sdd(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_quality-gate_master_2026-11-16_10:00.md"

        _assert_nothing_dispatched(
            verdict,
            "### 2. [LOW][test-sdd] Unplanned tests added by the branch\n",
        )

    def test_should_list_a_merged_test_sdd_finding_the_human_marked_done_or_marked_for_address_verdicts(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_quality-gate_master_2026-11-16_10:00.md"
        verdict.write_text(
            "## Findings\n\n"
            "### 4. [Done][HIGH][test-sdd] Missing planned test - task 5\n\n"
            "### 5. [AI!: do it][HIGH][test-sdd] Missing planned test - task 6\n",
            encoding="utf-8",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            "### 4. [Done][HIGH][test-sdd] Missing planned test - task 5",
            "### 5. [AI!: do it][HIGH][test-sdd] Missing planned test - task 6",
        ]

    def test_should_keep_listing_findings_after_an_indented_fence_line_since_only_a_fence_at_column_zero_opens_a_code_block(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_test-sdd_master_2026-11-15_10:00.md"
        verdict.write_text(
            "## Findings\n\n"
            "- an indented fence inside a list item:\n"
            "  ```\n\n"
            '### 1. [HIGH] Missing planned test - task 3: "after the indent"\n',
            encoding="utf-8",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            '### 1. [HIGH] Missing planned test - task 3: "after the indent"',
        ]

    def test_should_leave_a_finding_off_the_dispatch_list_once_its_body_holds_a_skipped_annotation_line_while_an_unannotated_sibling_stays_listed(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_test-sdd_master_2026-11-15_10:00.md"
        verdict.write_text(
            "## Findings\n\n"
            '### 1. [HIGH] Missing planned test - task 3: "already ruled"\n\n'
            "- **Task:** 3 - Parse quoted fields\n\n"
            "SKIPPED (needs an answer: which delimiter does the csv use?)\n\n"
            '### 2. [HIGH] Missing planned test - task 4: "still open"\n\n'
            "- **Task:** 4 - Sum a column\n",
            encoding="utf-8",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            '### 2. [HIGH] Missing planned test - task 4: "still open"',
        ]

    def test_should_leave_a_skipped_test_sdd_finding_off_the_list_when_the_merged_verdict_tags_it_test_sdd(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_quality-gate_master_2026-11-16_10:00.md"
        verdict.write_text(
            "## Findings\n\n"
            '### 1. [LOW][test-sdd] Missing planned test - task 2: "ruled"\n\n'
            "SKIPPED (out of scope for this branch)\n\n"
            '### 2. [LOW][test-sdd] Missing planned test - task 5: "open"\n\n'
            "## Other section\n",
            encoding="utf-8",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            '### 2. [LOW][test-sdd] Missing planned test - task 5: "open"',
        ]

    def test_should_keep_listing_a_finding_whose_only_skipped_line_is_quoted_inside_a_fenced_code_block(
        self, tmp_path
    ):
        verdict = tmp_path / "verdict_test-sdd_master_2026-11-15_10:00.md"
        verdict.write_text(
            "## Findings\n\n"
            '### 1. [HIGH] Missing planned test - task 3: "quotes a ruling"\n\n'
            "```\n"
            "SKIPPED (quoted from another verdict)\n"
            "```\n",
            encoding="utf-8",
        )

        completed = _run(verdict)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.splitlines() == [
            '### 1. [HIGH] Missing planned test - task 3: "quotes a ruling"',
        ]

    def test_fails_with_a_stderr_message_when_the_verdict_file_is_unreadable(
        self, tmp_path
    ):
        completed = _run(tmp_path / "verdict_test-sdd_missing.md")

        assert completed.returncode != 0
        assert completed.stderr.strip() != ""
        assert completed.stdout == ""
