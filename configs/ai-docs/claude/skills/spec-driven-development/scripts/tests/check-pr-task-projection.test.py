"""Blackbox CLI tests for check-pr-task-projection.py.

Fixtures: none on disk except what each test writes to tmp_path - every
plan is a minimal, hand-built Task Breakdown + PR Breakdown pair, small
enough that the expected FAIL/OK verdict is verifiable by eye.

Usage:
  pytest scripts/tests/check-pr-task-projection.test.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "check-pr-task-projection.py"


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
1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.

2. **PR-2** - Second slice. Tasks: 3. Depends on: PR-1.
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
    # without claiming a dependency on it - only the first
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
    # list names it - the orphan-task defect (Task 27 belonging
    # to no PR).
    pr_body = "1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.\n"
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 3" in result.stderr
    assert "no PR" in result.stderr


def test_should_report_a_task_claimed_by_more_than_one_pr(tmp_path):
    pr_body = (
        "1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.\n\n"
        "2. **PR-2** - Second slice. Tasks: 2, 3. Depends on: PR-1.\n"
    )
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 2" in result.stderr
    assert "PR-1" in result.stderr and "PR-2" in result.stderr


def test_should_report_a_pr_entry_naming_a_task_id_the_task_breakdown_does_not_define(tmp_path):
    pr_body = (
        "1. **PR-1** - First slice. Tasks: 1, 2, 4. Depends on: none.\n\n"
        "2. **PR-2** - Second slice. Tasks: 3. Depends on: PR-1.\n"
    )
    plan = _write_plan(tmp_path, task_body=HAPPY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 4" in result.stderr
    assert "PR-1" in result.stderr


def test_should_report_a_cross_level_task_dependency_landing_in_a_non_ancestor_pr(tmp_path):
    # Task 9 (in PR-1) depends on Task 10 (in PR-2); PR-1 has no
    # deps, so PR-2 is neither PR-1 nor its ancestor - the
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
        "1. **PR-1** - First slice, given a long enough description that this "
        "entry wraps onto\na second physical line before its Tasks and "
        "Depends-on clause appears. Tasks: 9. Depends on: none.\n\n"
        "2. **PR-2** - Second slice. Tasks: 10. Depends on: none.\n"
    )
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 9" in result.stderr
    assert "Task 10" in result.stderr
    assert "PR-2" in result.stderr


def test_should_report_a_finding_when_a_task_names_its_dependencies_inline_instead_of_as_task_bullets(tmp_path):
    # The inline form parses as dependency-free, so every
    # projection check below it passes vacuously - the fail-open
    # the grammar guard closes, as a finding (exit 1).
    task_body = (
        "### 1. First task\n\n"
        "**Depends on**: none\n\n"
        "### 2. Second task\n\n"
        "**Depends on**: Task 1\n"
    )
    pr_body = "1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.\n"
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 2" in result.stderr
    assert "- Task N" in result.stderr


def test_should_report_a_finding_when_a_task_depends_on_opens_with_a_bare_colon_and_lists_no_task_bullet(tmp_path):
    task_body = (
        "### 1. First task\n\n"
        "**Depends on**:\n\n"
        "### 2. Second task\n\n"
        "**Depends on**: none\n"
    )
    pr_body = "1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.\n"
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 1" in result.stderr


def test_should_exit_0_when_a_bare_depends_on_is_followed_by_a_lone_none_bullet(tmp_path):
    task_body = (
        "### 1. First task\n\n"
        "**Depends on**:\n"
        "- none\n\n"
        "### 2. Second task\n\n"
        "**Depends on**:\n"
        "- Task 1\n"
    )
    pr_body = "1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.\n"
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "bullets",
    ["- none\n- Task 1\n", "- Task 1\n- none\n"],
    ids=["none-before-task", "none-after-task"],
)
def test_should_report_a_finding_when_a_none_bullet_is_mixed_with_a_task_bullet_under_one_depends_on(tmp_path, bullets):
    task_body = (
        "### 1. First task\n\n"
        "**Depends on**: none\n\n"
        "### 2. Second task\n\n"
        f"**Depends on**:\n{bullets}"
    )
    pr_body = "1. **PR-1** - First slice. Tasks: 1, 2. Depends on: none.\n"
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 2" in result.stderr


CLARIFY_TASK_BODY = """\
### 1. First task

**Depends on**: none

### 2. [Clarify] Confirm the row cap with the warehouse team

**Depends on**: none

### 3. Third task

**Depends on**:
- Task 2
"""


def test_should_exit_0_when_a_clarify_task_is_claimed_by_no_pr(tmp_path):
    pr_body = (
        "### PR-1. First slice\n\n"
        "**Tasks**: 1\n\n"
        "**Depends on**: none\n\n"
        "### PR-2. Second slice\n\n"
        "**Tasks**: 3\n\n"
        "**Depends on**: PR-1\n"
    )
    plan = _write_plan(tmp_path, task_body=CLARIFY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_report_a_pr_that_lists_a_clarify_task_because_a_clarify_task_has_no_commit(tmp_path):
    pr_body = (
        "### PR-1. First slice\n\n"
        "**Tasks**: 1, 2\n\n"
        "**Depends on**: none\n\n"
        "### PR-2. Second slice\n\n"
        "**Tasks**: 3\n\n"
        "**Depends on**: PR-1\n"
    )
    plan = _write_plan(tmp_path, task_body=CLARIFY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "PR-1" in result.stderr
    assert "Task 2" in result.stderr
    assert "clarify task has no commit and belongs to no PR" in result.stderr


def test_should_exit_0_when_a_task_in_a_pr_with_no_ancestor_depends_on_a_clarify_task(tmp_path):
    # The clarify answer arrives through Linear, outside the PR
    # graph, so PR-2 needs no dependency edge toward anything.
    pr_body = (
        "### PR-1. First slice\n\n"
        "**Tasks**: 1\n\n"
        "**Depends on**: none\n\n"
        "### PR-2. Second slice\n\n"
        "**Tasks**: 3\n\n"
        "**Depends on**: none\n"
    )
    plan = _write_plan(tmp_path, task_body=CLARIFY_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 0, result.stderr


def test_should_pass_every_deterministic_plan_gate_and_the_projection_check_on_a_plan_with_a_clarify_task():
    fixture_dir = Path(__file__).parent / "fixtures" / "clarify-task"
    plan = fixture_dir / "plan_clarify.md"
    spec = fixture_dir / "spec_widget.md"
    gates = subprocess.run(
        ["bash", str(SCRIPT.parent / "check-deterministic-gates.sh"), str(plan), str(spec)],
        capture_output=True,
        text=True,
    )
    assert gates.returncode == 0, gates.stdout
    projection = _run(plan)
    assert projection.returncode == 0, projection.stderr


GATE_TASK_BODY = """\
### 1. First task

**Depends on**: none

### 2. [Gate] Prove on Stage that a 10k-row export finishes under 30s

**Depends on**: none

**Tests (planned)**: N/A - gate task, no code

### 3. Third task

**Depends on**:
- Task 2
"""

GATE_PR_BODY_WITHOUT_THE_GATE = (
    "### PR-1. First slice\n\n"
    "**Tasks**: 1\n\n"
    "**Depends on**: none\n\n"
    "### PR-2. Second slice\n\n"
    "**Tasks**: 3\n\n"
    "**Depends on**: none\n\n"
    "**Gates**: Task 2\n"
)


def test_should_exit_0_when_a_gate_task_is_claimed_by_no_pr_and_a_code_task_in_a_pr_with_no_ancestor_depends_on_it(tmp_path):
    # A gate task runs before the PR it guards merges, outside
    # the PR graph, so PR-2 needs no dependency edge toward it.
    plan = _write_plan(tmp_path, task_body=GATE_TASK_BODY, pr_body=GATE_PR_BODY_WITHOUT_THE_GATE)
    result = _run(plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


def test_should_report_a_pr_that_lists_a_gate_task_because_a_gate_task_has_no_commit(tmp_path):
    pr_body = (
        "### PR-1. First slice\n\n"
        "**Tasks**: 1\n\n"
        "**Depends on**: none\n\n"
        "### PR-2. Second slice\n\n"
        "**Tasks**: 2, 3\n\n"
        "**Depends on**: none\n"
    )
    plan = _write_plan(tmp_path, task_body=GATE_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "PR-2" in result.stderr
    assert "Task 2" in result.stderr
    assert "gate task has no commit and belongs to no PR" in result.stderr


def test_should_report_a_no_code_task_claimed_by_no_pr_when_its_heading_lacks_the_gate_tag(tmp_path):
    # Only the heading tag exempts a task - a body that reads
    # like a gate does not.
    task_body = GATE_TASK_BODY.replace("### 2. [Gate] ", "### 2. ")
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=GATE_PR_BODY_WITHOUT_THE_GATE)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 2 is defined in the Task Breakdown but claimed by no PR" in result.stderr


def test_should_pass_every_deterministic_plan_gate_and_the_projection_check_on_a_plan_with_a_gate_task():
    fixture_dir = Path(__file__).parent / "fixtures" / "gate-task"
    plan = fixture_dir / "plan_gate.md"
    spec = fixture_dir / "spec_widget.md"
    gates = subprocess.run(
        ["bash", str(SCRIPT.parent / "check-deterministic-gates.sh"), str(plan), str(spec)],
        capture_output=True,
        text=True,
    )
    assert gates.returncode == 0, gates.stdout
    projection = _run(plan)
    assert projection.returncode == 0, projection.stderr


DIRECT_TASK_BODY = """\
### 1. [Direct] Add the shared helper to the personal dotfiles repo

**Depends on**: none

### 2. Call the shared helper from the export job

**Depends on**:
- Task 1
"""

DIRECT_PR_BODY_WITHOUT_THE_DIRECT_TASK = (
    "### PR-1. Export job slice\n\n"
    "**Tasks**: 2\n\n"
    "**Depends on**: none\n"
)


def test_should_exit_0_when_the_only_task_claimed_by_no_pr_is_a_direct_task_committed_straight_to_a_branch(tmp_path):
    # A direct task's commits land on a branch with no PR at
    # all, so no PR can claim it, and PR-1 needs no edge toward
    # it.
    plan = _write_plan(tmp_path, task_body=DIRECT_TASK_BODY, pr_body=DIRECT_PR_BODY_WITHOUT_THE_DIRECT_TASK)
    result = _run(plan)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("OK:")


@pytest.mark.parametrize(
    "status, tag",
    [("Done", "Direct"), ("Doing", "Direct"), ("Done", "Gate")],
    ids=["done-direct", "doing-direct", "done-gate"],
)
def test_should_exempt_a_tagged_task_claimed_by_no_pr_when_a_plan_status_marker_precedes_its_tag(tmp_path, status, tag):
    # The plan-status marker sits right after the task number,
    # ahead of every other tag.
    task_body = DIRECT_TASK_BODY.replace("### 1. [Direct] ", f"### 1. [{status}][{tag}] ")
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=DIRECT_PR_BODY_WITHOUT_THE_DIRECT_TASK)
    result = _run(plan)
    assert result.returncode == 0, result.stderr


def test_should_report_a_pr_that_lists_a_direct_task_because_a_direct_task_lands_outside_any_pr(tmp_path):
    pr_body = (
        "### PR-1. Export job slice\n\n"
        "**Tasks**: 1, 2\n\n"
        "**Depends on**: none\n"
    )
    plan = _write_plan(tmp_path, task_body=DIRECT_TASK_BODY, pr_body=pr_body)
    result = _run(plan)
    assert result.returncode == 1
    assert "PR-1" in result.stderr
    assert "Task 1" in result.stderr
    assert "direct task lands its commits outside any PR" in result.stderr


def test_should_report_a_task_claimed_by_no_pr_when_its_heading_lacks_the_direct_tag(tmp_path):
    # Only the heading tag exempts a task - committing
    # straight to a branch is a claim the plan must make
    # explicitly.
    task_body = DIRECT_TASK_BODY.replace("### 1. [Direct] ", "### 1. ")
    plan = _write_plan(tmp_path, task_body=task_body, pr_body=DIRECT_PR_BODY_WITHOUT_THE_DIRECT_TASK)
    result = _run(plan)
    assert result.returncode == 1
    assert "Task 1 is defined in the Task Breakdown but claimed by no PR" in result.stderr
