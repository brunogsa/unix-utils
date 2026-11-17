"""Blackbox CLI tests for get-plan-tasks-for-branch.py.

Fixtures: each test writes a throwaway plan_*.md under tmp_path
and runs the script on it. Nothing reads the live repo.

Usage:
  ./run-tests.py <this file>
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "get-plan-tasks-for-branch.py"

BRANCH_PR1 = "feat/cdpi-791-2027-merge/pr1"
BRANCH_PR9 = "feat/cdpi-791-2027-merge/pr9"
BRANCH_PR10 = "feat/cdpi-791-2027-merge/pr10"

PLAN_INTRO = """# Plan: 2027 contract merge

## Tasks

### Task 8. Controller wiring for SAS

**Branch**: `feat/cdpi-791-2027-merge/pr1` named in a task body, not a PR entry

"""


def _pr_entry(heading, tasks_line, branch_line):
    return f"""### {heading}

{tasks_line}

**Depends on**: none

{branch_line}

Prose naming `{BRANCH_PR1}` in passing.

"""


def _plan_with_breakdown(*entries):
    return PLAN_INTRO + "## PR Breakdown\n\nMode: merge\n\n" + "".join(entries)


def _run(plan, branch):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(plan), branch],
        capture_output=True,
        text=True,
    )


def _write_plan(tmp_path, text):
    plan = tmp_path / "plan_2027-contract-merge.md"
    plan.write_text(text, encoding="utf-8")
    return plan


class TestTaskIdsPrintedForTheBranch:
    def test_should_print_the_task_ids_of_the_pr_whose_branch_matches_exactly_as_a_comma_list_without_spaces(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry(
                    "PR-1. [Done] BKO API key",
                    "**Tasks**: 14",
                    f"**Branch**: `{BRANCH_PR1}`",
                ),
                _pr_entry(
                    "PR-9. IS child and fork",
                    "**Tasks**: 10, 11",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
                _pr_entry(
                    "PR-10. [Done] SAS consumer fork",
                    "**Tasks**: 12",
                    f"**Branch**: `{BRANCH_PR10}`",
                ),
            ),
        )

        completed = _run(plan, BRANCH_PR9)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "10,11\n"

    def test_should_not_match_a_branch_that_only_shares_a_prefix_with_another_pr_branch(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry(
                    "PR-10. [Done] SAS consumer fork",
                    "**Tasks**: 12",
                    f"**Branch**: `{BRANCH_PR10}`",
                ),
                _pr_entry(
                    "PR-1. [Done] BKO API key",
                    "**Tasks**: 14",
                    f"**Branch**: `{BRANCH_PR1}`",
                ),
            ),
        )

        completed = _run(plan, BRANCH_PR1)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "14\n"

    def test_should_ignore_a_pr_entry_written_inside_a_fenced_code_block(
        self, tmp_path
    ):
        fenced_example = (
            "```md\n"
            + _pr_entry(
                "PR-99. Example entry",
                "**Tasks**: 99",
                f"**Branch**: `{BRANCH_PR9}`",
            )
            + "```\n\n"
        )
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                fenced_example,
                _pr_entry(
                    "PR-9. IS child and fork",
                    "**Tasks**: 10, 11",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
            ),
        )

        completed = _run(plan, BRANCH_PR9)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "10,11\n"


class TestFallbackToEveryTask:
    def test_should_print_nothing_and_succeed_when_no_pr_entry_names_the_branch(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry(
                    "PR-9. IS child and fork",
                    "**Tasks**: 10, 11",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
                _pr_entry("PR-11. Script CNPJs by brand", "**Tasks**: 15", "**Branch**:"),
            ),
        )

        completed = _run(plan, "feat/nope")

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""

    def test_should_print_nothing_and_succeed_for_an_empty_branch_name_while_several_pr_entries_have_no_branch_yet(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry("PR-11. Script CNPJs by brand", "**Tasks**: 15", "**Branch**:"),
                _pr_entry("PR-12. Script agreements by CNPJ", "**Tasks**: 16", "**Branch**:"),
            ),
        )

        completed = _run(plan, "")

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""

    def test_should_print_nothing_and_succeed_when_the_plan_has_no_pr_breakdown(
        self, tmp_path
    ):
        plan = _write_plan(tmp_path, PLAN_INTRO)

        completed = _run(plan, BRANCH_PR1)

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == ""


class TestFailures:
    def test_should_fail_naming_both_pr_headings_when_two_pr_entries_name_the_same_branch(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry(
                    "PR-9. IS child and fork",
                    "**Tasks**: 10, 11",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
                _pr_entry(
                    "PR-25. contractMerge2 on v2 SKU routes",
                    "**Tasks**: 29",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
            ),
        )

        completed = _run(plan, BRANCH_PR9)

        assert completed.returncode != 0
        assert completed.stdout == ""
        assert "PR-9. IS child and fork" in completed.stderr
        assert "PR-25. contractMerge2 on v2 SKU routes" in completed.stderr

    def test_should_fail_naming_the_pr_heading_when_the_matching_entry_has_no_tasks_line(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry(
                    "PR-6. [Done] Controller wiring for SAS",
                    "",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
            ),
        )

        completed = _run(plan, BRANCH_PR9)

        assert completed.returncode != 0
        assert completed.stdout == ""
        assert "PR-6. [Done] Controller wiring for SAS" in completed.stderr

    def test_should_fail_naming_the_pr_heading_when_the_matching_entry_lists_no_task_ids(
        self, tmp_path
    ):
        plan = _write_plan(
            tmp_path,
            _plan_with_breakdown(
                _pr_entry(
                    "PR-6. [Done] Controller wiring for SAS",
                    "**Tasks**:",
                    f"**Branch**: `{BRANCH_PR9}`",
                ),
            ),
        )

        completed = _run(plan, BRANCH_PR9)

        assert completed.returncode != 0
        assert completed.stdout == ""
        assert "PR-6. [Done] Controller wiring for SAS" in completed.stderr

    def test_should_fail_naming_the_path_when_the_plan_file_does_not_exist(
        self, tmp_path
    ):
        missing_plan = tmp_path / "plan_missing.md"

        completed = _run(missing_plan, BRANCH_PR9)

        assert completed.returncode != 0
        assert completed.stdout == ""
        assert str(missing_plan) in completed.stderr
