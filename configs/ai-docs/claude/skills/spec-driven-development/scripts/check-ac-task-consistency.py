#!/usr/bin/env python3
"""check-ac-task-consistency.py - assert every Test Design row's cited
ACs are declared by the tasks that row cites.

A plan's `## Test Design` annotates each it() row with the ACs it proves
and the tasks that write it (`// AC-17 T14`), while each task under
`## Task Breakdown` separately declares its own
`**Testable Acceptance criteria**`. Nothing else joins the two, so a row
can cite an AC its task never claims. check-ac-coverage.sh does not
cover this: in annotated form it runs completeness against the spec only,
and never reads the task-side field at all.

Usage:
  check-ac-task-consistency.py <plan-path>

stdout: one `OK: ...` line on a consistent plan, naming what was checked
stderr: one `line <n>: T<k> lacks AC-<m>` per mismatch, or a diagnostic
exit: 0 consistent, 1 at least one mismatch, 2 usage error or a section
      that is absent or holds nothing to check
"""

import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EXTRACT_DESIGN_TESTS = SCRIPT_DIR / "extract-design-tests.sh"

SECTION_HEADING = re.compile(r"^## ")
DESIGN_HEADING = re.compile(r"^## Test Design[ \t]*$")
TASKS_HEADING = re.compile(r"^## Task Breakdown[ \t]*$")
DESCRIBE_CALL = re.compile(r'describe\("[^"]*"')
IT_CALL = re.compile(r'it\("[^"]*"')
TASK_HEADING = re.compile(r"^### (\d+)\.")
AC_FIELD = re.compile(r"\*\*Testable Acceptance criteria\*\*")
AC_TOKEN = re.compile(r"AC-\d+")


def exit_with_usage_error(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def find_design_row_lines(lines):
    """The 1-based plan line number of every Test Design it() row.

    extract-design-tests.sh emits exactly one row per such line and has
    no line-number mode, so this walk mirrors the three rules its awk
    shares: the `## ` section bounds, the describe() skip, and the it()
    match. The caller zips the two by position and refuses to guess when
    the counts disagree."""
    row_lines = []
    in_design = False

    for number, text in enumerate(lines, 1):
        if SECTION_HEADING.match(text):
            if in_design:
                break
            in_design = bool(DESIGN_HEADING.match(text))
            continue
        if not in_design:
            continue
        if DESCRIBE_CALL.search(text):
            continue
        if IT_CALL.search(text):
            row_lines.append(number)

    return row_lines


def read_task_declarations(lines):
    """Map each `### <n>.` task in the Task Breakdown to the AC tokens
    its `**Testable Acceptance criteria**` field names.

    Returns the set of task numbers that have a heading, and the subset
    of those mapped to their declared ACs. A task missing from the
    second dict has no criteria field at all, which is a different
    defect from a field that names the wrong ACs.

    Scoped to the Task Breakdown section: a `### <n>.` heading elsewhere
    in the plan belongs to another section's numbering."""
    headings = set()
    declared = {}
    in_tasks = False
    current = None

    for text in lines:
        if SECTION_HEADING.match(text):
            if in_tasks:
                break
            in_tasks = bool(TASKS_HEADING.match(text))
            continue
        if not in_tasks:
            continue

        heading = TASK_HEADING.match(text)
        if heading:
            current = int(heading.group(1))
            headings.add(current)
            continue

        if current is not None and AC_FIELD.search(text):
            declared.setdefault(current, set(AC_TOKEN.findall(text)))

    return headings, declared


def read_annotation_rows(plan):
    """The `<title>\tcrumb\t<ACs>\t<tasks>` rows of the plan's Test
    Design, delegated to the single-source annotation parser."""
    result = subprocess.run(
        [str(EXTRACT_DESIGN_TESTS), "--annotations", str(plan)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        exit_with_usage_error(
            f"no it(\"...\") rows to check in the '## Test Design' "
            f"section of {plan}"
        )
    return [line.split("\t") for line in result.stdout.splitlines()]


def find_mismatches(rows, row_lines, headings, declared):
    """Every cited (task, AC) pair the task does not declare, plus the
    count of pairs actually checked."""
    mismatches = []
    checked = 0

    for row, line in zip(rows, row_lines):
        acs = row[2].split()
        for task_token in row[3].split():
            task = int(task_token[1:])
            if task not in headings:
                mismatches.append(
                    f"line {line}: {task_token} has no task heading"
                )
                continue
            if task not in declared:
                mismatches.append(
                    f"line {line}: {task_token} has no "
                    f"**Testable Acceptance criteria** field"
                )
                continue
            for ac in acs:
                checked += 1
                if ac not in declared[task]:
                    mismatches.append(
                        f"line {line}: {task_token} lacks {ac}"
                    )

    return mismatches, checked


def main():
    if len(sys.argv) != 2:
        print(
            f"usage: {Path(sys.argv[0]).name} <plan-path>",
            file=sys.stderr,
        )
        sys.exit(2)

    plan = Path(sys.argv[1])
    if not plan.is_file():
        exit_with_usage_error(f"plan file not found: {plan}")

    lines = plan.read_text(encoding="utf-8").splitlines()

    if not any(DESIGN_HEADING.match(text) for text in lines):
        exit_with_usage_error(f"no '## Test Design' section in {plan}")
    if not any(TASKS_HEADING.match(text) for text in lines):
        exit_with_usage_error(f"no '## Task Breakdown' section in {plan}")

    rows = read_annotation_rows(plan)
    row_lines = find_design_row_lines(lines)

    if len(rows) != len(row_lines):
        exit_with_usage_error(
            f"{len(rows)} annotation rows but {len(row_lines)} it() lines "
            f"found in {plan}; the shared extract-design-tests.sh parser "
            f"and this one disagree"
        )

    headings, declared = read_task_declarations(lines)
    mismatches, checked = find_mismatches(
        rows, row_lines, headings, declared
    )

    if mismatches:
        for mismatch in mismatches:
            print(mismatch, file=sys.stderr)
        sys.exit(1)

    print(
        f"OK: {len(rows)} Test Design rows, {checked} task-AC citations "
        f"checked; every cited AC is declared by its task."
    )


if __name__ == "__main__":
    main()
