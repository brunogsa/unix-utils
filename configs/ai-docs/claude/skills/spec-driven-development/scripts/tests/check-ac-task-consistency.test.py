"""Blackbox CLI tests for check-ac-task-consistency.py.

Fixtures: none on disk except what each test writes to tmp_path — every
plan is a minimal Test Design + Task Breakdown pair, small enough that
the expected OK/mismatch verdict is verifiable by eye. No test reads a
planning artifact from the repo, so no suite run can be steered, or
broken, by a document its author is still editing.

Usage:
  pytest scripts/tests/check-ac-task-consistency.test.py
"""

import subprocess
import sys
from pathlib import Path

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

**Testable Acceptance criteria**: AC-1, AC-2.

### 2. Recompose the existing PR body

**Files**: `scripts/compose.sh`

**Testable Acceptance criteria**: AC-2.
"""

ONE_LACKING_TASKS = """\
### 1. Export the plan PRs to Linear

**Testable Acceptance criteria**: AC-1, AC-2.

### 2. Recompose the existing PR body

**Testable Acceptance criteria**: AC-9.
"""

SINGLE_ROW_DESIGN = """\
```
describe("fixture", () => {
  it("should write one Linear issue per plan PR");            // AC-1 T1
});
```
"""


def _write_plan(tmp_path, *, design_body, task_body, trailer=""):
    """Write a plan_<slug>.md fixture holding only the two sections the
    gate reads, and return its path. A body of None omits that whole
    section, which is how the missing-section cases are built."""
    text = "# plan_fixture\n\n"
    if design_body is not None:
        text += f"## Test Design\n\n{design_body}\n---\n\n"
    if task_body is not None:
        text += f"## Task Breakdown\n\n{task_body}\n---\n"
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


def test_passes_when_every_cited_ac_is_declared_by_its_task(tmp_path):
    plan = _write_plan(
        tmp_path, design_body=CONSISTENT_DESIGN, task_body=CONSISTENT_TASKS
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr
    assert "2 Test Design rows" in result.stdout
    assert "3 task-AC citations" in result.stdout


def test_fails_when_a_row_cites_an_ac_its_task_does_not_declare(tmp_path):
    plan = _write_plan(
        tmp_path, design_body=CONSISTENT_DESIGN, task_body=ONE_LACKING_TASKS
    )
    expected_line = _line_of(plan, "existing-PR mode")
    result = _run(str(plan))
    assert result.returncode == 1
    assert f"line {expected_line}: T2 lacks AC-2" in result.stderr


def test_does_not_flag_the_row_tasks_that_do_declare_the_cited_ac(tmp_path):
    plan = _write_plan(
        tmp_path, design_body=CONSISTENT_DESIGN, task_body=ONE_LACKING_TASKS
    )
    result = _run(str(plan))
    assert result.stderr.count("lacks") == 1


def test_fails_when_a_row_cites_a_task_that_has_no_heading(tmp_path):
    design = SINGLE_ROW_DESIGN.replace("// AC-1 T1", "// AC-1 T9")
    plan = _write_plan(
        tmp_path, design_body=design, task_body=CONSISTENT_TASKS
    )
    expected_line = _line_of(plan, "one Linear issue per plan PR")
    result = _run(str(plan))
    assert result.returncode == 1
    assert f"line {expected_line}: T9 has no task heading" in result.stderr


def test_reports_a_cited_task_with_no_criteria_field_once_per_row(tmp_path):
    design = SINGLE_ROW_DESIGN.replace("// AC-1 T1", "// AC-1 AC-2 T1")
    plan = _write_plan(
        tmp_path,
        design_body=design,
        task_body="### 1. Export the plan PRs to Linear\n\n**Files**: `x.sh`\n",
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


def test_flags_a_cited_ac_when_the_task_field_names_no_ac_at_all(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=SINGLE_ROW_DESIGN,
        task_body=(
            "### 1. Export the plan PRs to Linear\n\n"
            "**Testable Acceptance criteria**: design-level — documented "
            "as a hard requirement.\n"
        ),
    )
    result = _run(str(plan))
    assert result.returncode == 1
    assert "T1 lacks AC-1" in result.stderr


def test_ignores_a_task_heading_outside_the_task_breakdown(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body=CONSISTENT_DESIGN,
        task_body=CONSISTENT_TASKS,
        trailer=(
            "\n## Appendix\n\n"
            "### 1. A same-numbered heading elsewhere\n\n"
            "**Testable Acceptance criteria**: AC-9.\n"
        ),
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr


def test_passes_trivially_when_no_row_carries_an_annotation(tmp_path):
    design = SINGLE_ROW_DESIGN.replace("            // AC-1 T1", "")
    plan = _write_plan(
        tmp_path, design_body=design, task_body=CONSISTENT_TASKS
    )
    result = _run(str(plan))
    assert result.returncode == 0, result.stderr
    assert "0 task-AC citations" in result.stdout


def test_exits_two_when_the_plan_has_no_test_design_section(tmp_path):
    plan = _write_plan(tmp_path, design_body=None, task_body=CONSISTENT_TASKS)
    result = _run(str(plan))
    assert result.returncode == 2
    assert "Test Design" in result.stderr


def test_exits_two_when_the_plan_has_no_task_breakdown_section(tmp_path):
    plan = _write_plan(
        tmp_path, design_body=CONSISTENT_DESIGN, task_body=None
    )
    result = _run(str(plan))
    assert result.returncode == 2
    assert "Task Breakdown" in result.stderr


def test_exits_two_when_the_test_design_section_holds_no_rows(tmp_path):
    plan = _write_plan(
        tmp_path,
        design_body="N/A — nothing designed yet.\n",
        task_body=CONSISTENT_TASKS,
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
