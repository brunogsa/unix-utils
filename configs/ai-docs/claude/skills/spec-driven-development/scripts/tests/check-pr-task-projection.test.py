"""Blackbox CLI tests for check-pr-task-projection.py.

Fixtures: none on disk except what each test writes to tmp_path — every
plan is a minimal, hand-built Task Breakdown + PR Breakdown pair, small
enough that the expected FAIL/OK verdict is verifiable by eye. One test
also runs the checker against the repo's real plan_script-overhaul.md as
a regression fixture. That plan is session-scoped and untracked, so the
test skips rather than fails once the session that wrote it is gone.

Usage:
  pytest scripts/tests/check-pr-task-projection.test.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-pr-task-projection.py"
REPO_ROOT = Path(__file__).parents[7]


def _write_plan(tmp_path, *, task_body, pr_body):
    """Write a minimal plan_<slug>.md fixture with only the two sections
    the checker reads, and return its path."""
    text = (
        "## Task Breakdown\n\n"
        f"{task_body}\n\n"
        "## PR Breakdown\n\n"
        f"{pr_body}\n"
    )
    path = tmp_path / "plan_fixture.md"
    path.write_text(text, encoding="utf-8")
    return path


def _run(plan_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(plan_path)],
        capture_output=True,
        text=True,
    )


HAPPY_TASK_BODY = """\
### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 2
"""

HAPPY_PR_BODY = """\
1. **PR-1** — First slice. Tasks: 1, 2. Depends on: none.

2. **PR-2** — Second slice. Tasks: 3. Depends on: PR-1.
"""

HAPPY_HEADING_PR_BODY = """\
### PR-1. First slice

**Tasks**: 1, 2

**Depends on**: none

### PR-2. [Done] Second slice

**Tasks**: 3

**Depends on**: PR-1
"""


def test_should_exit_0_when_every_task_lands_in_its_own_pr_or_an_ancestor_pr(tmp_path):
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=HAPPY_PR_BODY)
    result = _run(plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_exit_0_when_each_pr_is_its_own_heading_and_every_task_lands_in_its_own_or_an_ancestor_pr(tmp_path):
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=HAPPY_HEADING_PR_BODY)
    result = _run(plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_report_a_cross_level_task_dependency_when_each_pr_is_its_own_heading(tmp_path):
    # Same defect as the one-line-entry case below, written in
    # the heading grammar: Task 3 sits in PR-1 but depends on
    # Task 2 in PR-2, which PR-1 does not depend on.
    pr_body = (
        "### PR-1. First slice\n\n"
        "**Tasks**: 1, 3\n\n"
        "**Depends on**: none\n\n"
        "### PR-2. Second slice\n\n"
        "**Tasks**: 2\n\n"
        "**Depends on**: none\n"
    )
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 3" in result.stderr
    assert "Task 2" in result.stderr
    assert "PR-2" in result.stderr


def test_should_ignore_a_bolded_pr_label_and_a_second_depends_on_written_in_an_entrys_prose(tmp_path):
    # The prose below a PR's fields may discuss another PR
    # without claiming a dependency on it — only the first
    # Depends on field of the entry counts, and a bolded label
    # opens no new entry.
    pr_body = (
        "### PR-1. First slice\n\n"
        "**Tasks**: 1, 2\n\n"
        "**Depends on**: none\n\n"
        "Sequenced ahead of **PR-2** so the validators land first. "
        "Depends on: PR-2 is the shape we rejected.\n\n"
        "### PR-2. Second slice\n\n"
        "**Tasks**: 3\n\n"
        "**Depends on**: PR-1\n"
    )
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_exit_0_when_the_plan_has_no_pr_breakdown_section_at_all(tmp_path):
    path = tmp_path / "plan_fixture.md"
    path.write_text("## Task Breakdown\n\n" + HAPPY_TASK_BODY + "\n", encoding="utf-8")
    result = _run(path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_exit_0_when_the_pr_breakdown_reads_the_literal_single_pr_escape(tmp_path):
    path = tmp_path / "plan_fixture.md"
    path.write_text(
        "## Task Breakdown\n\n" + HAPPY_TASK_BODY + "\n"
        "## PR Breakdown\n\nSingle PR.\n",
        encoding="utf-8",
    )
    result = _run(path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_report_a_task_claimed_by_no_pr(tmp_path):
    # Task 3 is defined in the Task Breakdown but no PR's Tasks
    # list names it — the orphan-task defect (Task 27 belonging
    # to no PR).
    pr_body = "1. **PR-1** — First slice. Tasks: 1, 2. Depends on: none.\n"
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 3" in result.stderr
    assert "no PR" in result.stderr


def test_should_report_a_task_claimed_by_more_than_one_pr(tmp_path):
    pr_body = (
        "1. **PR-1** — First slice. Tasks: 1, 2. Depends on: none.\n\n"
        "2. **PR-2** — Second slice. Tasks: 2, 3. Depends on: PR-1.\n"
    )
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 2" in result.stderr
    assert "PR-1" in result.stderr and "PR-2" in result.stderr


def test_should_report_a_pr_entry_naming_a_task_id_the_task_breakdown_does_not_define(tmp_path):
    pr_body = (
        "1. **PR-1** — First slice. Tasks: 1, 2, 4. Depends on: none.\n\n"
        "2. **PR-2** — Second slice. Tasks: 3. Depends on: PR-1.\n"
    )
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 4" in result.stderr
    assert "PR-1" in result.stderr


def test_should_report_a_cross_level_task_dependency_landing_in_a_non_ancestor_pr(tmp_path):
    # Task 9 (in PR-1) depends on Task 10 (in PR-2); PR-1 has no
    # deps, so PR-2 is neither PR-1 nor its ancestor — the
    # cross-level violation subsuming both the cross-level cycle
    # and the silent-dispatch defects.
    #
    # PR-1's entry deliberately wraps its title onto a second
    # physical line before its Tasks/Depends-on clause, per the
    # parsing warning that a line-oriented read drops it.
    task_body = (
        "### 9. Task depending on a later PR\n\n"
        "**Depends on**:\n"
        "- Task 10\n\n"
        "### 10. Prerequisite task\n\n"
        "**Depends on**: none\n"
    )
    pr_body = (
        "1. **PR-1** — First slice, given a long enough description that this "
        "entry wraps onto\na second physical line before its Tasks and "
        "Depends-on clause appears. Tasks: 9. Depends on: none.\n\n"
        "2. **PR-2** — Second slice. Tasks: 10. Depends on: none.\n"
    )
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 9" in result.stderr
    assert "Task 10" in result.stderr
    assert "PR-2" in result.stderr


def test_should_exit_0_on_the_real_script_overhaul_plan_27_tasks_18_prs():
    real_plan = REPO_ROOT / "plan_script-overhaul.md"
    if not real_plan.is_file():
        pytest.skip(f"session-scoped plan absent: {real_plan.name}")
    result = _run(real_plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")
