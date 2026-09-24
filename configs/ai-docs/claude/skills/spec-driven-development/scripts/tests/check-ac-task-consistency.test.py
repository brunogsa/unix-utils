"""Blackbox CLI tests for check-ac-task-consistency.py.

Fixtures: none on disk except what each test writes to tmp_path — every
plan is a minimal Test Design + Task Breakdown + Task Details trio,
small enough that the expected OK/mismatch verdict is verifiable by
eye. No test reads a planning artifact from the repo, so no suite run
can be steered, or broken, by a document its author is still editing.

Fixtures use the reshaped doc layout: a task's own `### N.` heading
(body side, under `## Task Breakdown`) carries no AC field any more —
its `**Testable Acceptance criteria**` field moved into the appendix,
under `## Task Details`, one `<details><summary>Task N — ...`
per task. Old-location reading (the field still on the body-side
heading) is deliberately not supported: this checker only ever runs
at authoring time, from brainstorm self-review against a freshly
written plan, never against an old in-flight plan the way /implement's
parsers do — so new-shape-only is the right tradeoff, not a gap.

Usage:
  pytest scripts/tests/check-ac-task-consistency.test.py
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPT = Path(__file__).parent.parent / "check-ac-task-consistency.py"

CONSISTENT_DESIGN = """\
```
// planning-chain
describe("fixture", () => {
  // Happy cases
  it("should write one Linear issue per plan PR");            // AC-1 T1
  it("should keep the named PR draft in existing-PR mode");   // AC-2 T1 T2
});
```
"""

CONSISTENT_TASKS = """\
### 1. Export the plan PRs to Linear

**Files**: `scripts/export.sh`

### 2. Recompose the existing PR body

**Files**: `scripts/compose.sh`
"""

CONSISTENT_DETAILS = """\
<details>
<summary>Task 1 — Export the plan PRs to Linear</summary>

**Testable Acceptance criteria**:
- AC-1
- AC-2

</details>

<details>
<summary>Task 2 — Recompose the existing PR body</summary>

**Testable Acceptance criteria**:
- AC-2

</details>
"""

ONE_LACKING_DETAILS = """\
<details>
<summary>Task 1 — Export the plan PRs to Linear</summary>

**Testable Acceptance criteria**:
- AC-1
- AC-2

</details>

<details>
<summary>Task 2 — Recompose the existing PR body</summary>

**Testable Acceptance criteria**:
- AC-9

</details>
"""

SINGLE_TASK = """\
### 1. Export the plan PRs to Linear

**Files**: `x.sh`
"""

SINGLE_ROW_DESIGN = """\
```
describe("fixture", () => {
  it("should write one Linear issue per plan PR");            // AC-1 T1
});
```
"""


def _write_plan(
    tmp_path,
    *,
    design_body,
    task_body,
    details_body: Optional[str] = "",
    trailer="",
):
    """Write a plan_<slug>.md fixture holding only the sections the gate
    reads, and return its path. A body of None omits that whole
    section, which is how the missing-section cases are built."""
    text = "# plan_fixture\n\n"
    if design_body is not None:
        text += f"## Test Design\n\n{design_body}\n---\n\n"
    if task_body is not None:
        text += f"## Task Breakdown\n\n{task_body}\n---\n\n"
    text += "# Appendix\n\n"
    if details_body is not None:
        text += f"## Task Details\n\n{details_body}\n"
    text += trailer

    path = tmp_path / "plan_fixture.md"
    path.write_text(text, encoding="utf-8")
    return path


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _line_of(plan_path, needle):
    """The 1-based line number of the first fixture line holding needle.

    The expected `line <n>:` prefix is located independently of the gate
    under test, so a fixture edit cannot silently drift the assertion."""
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    return next(i for i, text in enumerate(lines, 1) if needle in text)


def test_passes_when_every_cited_ac_is_declared_by_its_tasks_details_entry(
    tmp_path,
):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr
    assert "2 Test Design rows" in result.stdout
    assert "3 task-AC citations" in result.stdout


def test_fails_when_a_row_cites_an_ac_its_tasks_details_entry_does_not_declare(
    tmp_path,
):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=ONE_LACKING_DETAILS,
    )
    expected_line = _line_of(plan, "existing-PR mode")
    result = _run(str(plan))
    assert result.returncode == 1
    assert f"line {expected_line}: T2 lacks AC-2" in result.stderr


def test_does_not_flag_the_row_tasks_that_do_declare_the_cited_ac(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=ONE_LACKING_DETAILS,
    )
    result = _run(str(plan))
    assert result.stderr.count("lacks") == 1


def test_fails_when_a_row_cites_a_task_that_has_no_heading(tmp_path):
    design = SINGLE_ROW_DESIGN.replace("// AC-1 T1", "// AC-1 T9")
    plan = _write_plan(
        tmp_path,
        design_body=design,
        task_body=CONSISTENT_TASKS,
        details_body=CONSISTENT_DETAILS,
    )
    expected_line = _line_of(plan, "one Linear issue per plan PR")
    result = _run(str(plan))
    assert result.returncode == 1
    assert f"line {expected_line}: T9 has no task heading" in result.stderr


def test_reports_a_cited_task_with_no_criteria_field_once_per_row(tmp_path):
    design = SINGLE_ROW_DESIGN.replace("// AC-1 T1", "// AC-1 AC-2 T1")
    details_no_ac_field = (
        "<details>\n"
        "<summary>Task 1 — Export the plan PRs to Linear</summary>\n\n"
        "**Files**: `x.sh`\n\n"
        "</details>\n"
    )
    plan = _write_plan(
        tmp_path,
        design_body=design,
        task_body=SINGLE_TASK,
        details_body=details_no_ac_field,
    )
    expected_line = _line_of(plan, "one Linear issue per plan PR")
    result = _run(str(plan))
    assert result.returncode == 1
    expected = (
        f"line {expected_line}: T1 has no "
        "**Testable Acceptance criteria** field"
    )
    assert expected in result.stderr
    assert result.stderr.count("T1 ") == 1


def test_flags_a_cited_ac_when_the_tasks_details_entry_names_no_ac_at_all(
    tmp_path,
):
    details_no_ac_token = (
        "<details>\n"
        "<summary>Task 1 — Export the plan PRs to Linear</summary>\n\n"
        "**Testable Acceptance criteria**:\n"
        "- design-level — documented as a hard requirement.\n\n"
        "</details>\n"
    )
    plan = _write_plan(
        tmp_path,
        design_body=SINGLE_ROW_DESIGN,
        task_body=SINGLE_TASK,
        details_body=details_no_ac_token,
    )
    result = _run(str(plan))
    assert result.returncode == 1
    assert "T1 lacks AC-1" in result.stderr


def test_ignores_a_task_heading_outside_the_task_breakdown(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=CONSISTENT_DETAILS,
        trailer=(
            "\n## Technical Decisions\n\n"
            "### 1. A same-numbered heading elsewhere\n\n"
            "**Testable Acceptance criteria**:\n- AC-9\n"
        ),
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr


def test_passes_trivially_when_no_row_carries_an_annotation(tmp_path):
    design = SINGLE_ROW_DESIGN.replace("            // AC-1 T1", "")
    plan = _write_plan(
        tmp_path,
        design_body=design,
        task_body=CONSISTENT_TASKS,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr
    assert "0 task-AC citations" in result.stdout


def test_fails_when_a_task_breakdown_entry_has_no_task_details_entry(
    tmp_path,
):
    details_missing_task_2 = (
        "<details>\n"
        "<summary>Task 1 — Export the plan PRs to Linear</summary>\n\n"
        "**Testable Acceptance criteria**:\n"
        "- AC-1\n"
        "- AC-2\n\n"
        "</details>\n"
    )
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=details_missing_task_2,
    )
    result = _run(str(plan))
    assert result.returncode == 1
    assert "Task 2 has no Task Details entry" in result.stderr


def test_fails_when_a_task_details_entry_names_no_existing_task(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=SINGLE_TASK,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 1
    assert (
        "Task Details entry for Task 2 names no existing task"
        in result.stderr
    )


def test_exits_two_when_the_plan_has_no_test_design_section(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=None,
        task_body=CONSISTENT_TASKS,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 2
    assert "Test Design" in result.stderr


def test_exits_two_when_the_plan_has_no_task_breakdown_section(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=None,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 2
    assert "Task Breakdown" in result.stderr


def test_exits_two_when_the_plan_has_no_task_details_section(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=None,
    )
    result = _run(str(plan))
    assert result.returncode == 2
    assert "Task Details" in result.stderr


def test_ignores_a_task_heading_inside_a_fenced_block_in_task_breakdown(
    tmp_path,
):
    """A fenced sample showing task-heading syntax (e.g. a template
    snippet) must not register as a real task — it would open a
    phantom task with no Task Details entry and trip the pairing
    check for no reason."""
    fenced_task_body = (
        CONSISTENT_TASKS
        + "\n```\n### 3. Example heading shown as sample markup\n```\n"
    )
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=fenced_task_body,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr


def test_ignores_a_summary_task_line_inside_a_fenced_block_in_task_details(
    tmp_path,
):
    """A fenced sample inside Task Details showing the
    `<summary>Task N` syntax must not register as a real entry — it
    would pair a phantom Task Details entry against no matching task
    heading."""
    fenced_details_body = (
        CONSISTENT_DETAILS
        + "\n```\n<summary>Task 9 — Example entry shown as sample markup</summary>\n```\n"
    )
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        details_body=fenced_details_body,
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr


def test_exits_two_when_the_test_design_section_holds_no_rows(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body="N/A — nothing designed yet.\n",
        task_body=CONSISTENT_TASKS,
        details_body=CONSISTENT_DETAILS,
    )
    result = _run(str(plan))
    assert result.returncode == 2
    assert "Test Design" in result.stderr


def test_exits_two_when_the_named_plan_is_missing(tmp_path):
    result = _run(str(tmp_path / "absent.md"))
    assert result.returncode == 2
    assert "plan file not found" in result.stderr


def test_exits_two_when_called_with_no_argument():
    result = _run()
    assert result.returncode == 2
    assert "usage:" in result.stderr
