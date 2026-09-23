#!/usr/bin/env python3
"""check-ac-task-consistency.py - assert every Test Design row's cited
ACs are declared by the tasks that row cites, and that every task is
paired with exactly one Task Details entry.

A plan's `## Test Design` annotates each it() row with the ACs it proves
and the tasks that write it (`// AC-17 T14`). Each task under
`## Task Breakdown` gets a `### N.` heading with no AC field of its own;
its `**Testable Acceptance criteria**` field lives instead in the
`## Task Details` appendix, in a `<details><summary>Task N — ...`
entry. Nothing else joins the three, so a row can cite an AC its task's
entry never claims, or a task can be missing its entry entirely (or vice
versa). check-ac-coverage.sh does not cover this: in annotated form it
runs completeness against the spec only, and never reads the task-side
field at all.

This checker runs only at authoring time, from brainstorm self-review
against a freshly written plan — never against an old in-flight plan
the way /implement's parsers do — so it reads the Task Details appendix
only; a task's old-location body-side AC field (if any survives from
before the doc reshape) is not read.

Usage:
  check-ac-task-consistency.py <plan-path>

stdout: one `OK: ...` line on a consistent plan, naming what was checked
stderr: one `line <n>: T<k> lacks AC-<m>` per citation mismatch, one
        `Task <n> has no Task Details entry` or `Task Details entry for
        Task <n> names no existing task` per pairing mismatch, or a
        diagnostic
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
DETAILS_HEADING = re.compile(r"^## Task Details[ \t]*$")
DESCRIBE_CALL = re.compile(r'describe\("[^"]*"')
IT_CALL = re.compile(r'it\("[^"]*"')
TASK_HEADING = re.compile(r"^### (\d+)\.")
SUMMARY_TASK = re.compile(r"<summary>Task (\d+)")
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


def read_task_headings(lines):
    """The set of `### <n>.` task numbers declared under `## Task
    Breakdown`.

    Scoped to the Task Breakdown section: a `### <n>.` heading elsewhere
    in the plan (e.g. under `## Technical Decisions`) belongs to another
    section's numbering."""
    headings = set()
    in_tasks = False

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
            headings.add(int(heading.group(1)))

    return headings


def read_task_details(lines):
    """Map each `<summary>Task <n>` entry under `## Task Details` to the
    AC tokens its `**Testable Acceptance criteria**` field lists.

    Returns the set of task numbers with a Task Details entry, and the
    subset of those mapped to their declared ACs. An entry missing from
    the second dict has no criteria field at all, which is a different
    defect from a field that names no AC token.

    The field's tokens sit on the bullet lines below the field marker,
    not on the marker's own line, so this reads every line up to the
    next blank line as part of the field."""
    entries = set()
    declared = {}
    in_details = False
    current = None
    in_ac_field = False

    for text in lines:
        if SECTION_HEADING.match(text):
            if in_details:
                break
            in_details = bool(DETAILS_HEADING.match(text))
            continue
        if not in_details:
            continue

        summary = SUMMARY_TASK.search(text)
        if summary:
            current = int(summary.group(1))
            entries.add(current)
            in_ac_field = False
            continue

        if current is None:
            continue

        if AC_FIELD.search(text):
            declared.setdefault(current, set())
            in_ac_field = True
            continue

        if in_ac_field:
            if not text.strip():
                in_ac_field = False
                continue
            declared[current] |= set(AC_TOKEN.findall(text))

    return entries, declared


def find_pairing_mismatches(headings, detail_entries):
    """Every task/entry that has no counterpart on the other side."""
    mismatches = []

    for task in sorted(headings - detail_entries):
        mismatches.append(f"Task {task} has no Task Details entry")
    for task in sorted(detail_entries - headings):
        mismatches.append(
            f"Task Details entry for Task {task} names no existing task"
        )

    return mismatches


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


def find_citation_mismatches(rows, row_lines, headings, declared):
    """Every cited (task, AC) pair the task's Task Details entry does
    not declare, plus the count of pairs actually checked."""
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
    if not any(DETAILS_HEADING.match(text) for text in lines):
        exit_with_usage_error(f"no '## Task Details' section in {plan}")

    rows = read_annotation_rows(plan)
    row_lines = find_design_row_lines(lines)

    if len(rows) != len(row_lines):
        exit_with_usage_error(
            f"{len(rows)} annotation rows but {len(row_lines)} it() lines "
            f"found in {plan}; the shared extract-design-tests.sh parser "
            f"and this one disagree"
        )

    headings = read_task_headings(lines)
    detail_entries, declared = read_task_details(lines)

    mismatches = find_pairing_mismatches(headings, detail_entries)
    citation_mismatches, checked = find_citation_mismatches(
        rows, row_lines, headings, declared
    )
    mismatches.extend(citation_mismatches)

    if mismatches:
        for mismatch in mismatches:
            print(mismatch, file=sys.stderr)
        sys.exit(1)

    print(
        f"OK: {len(rows)} Test Design rows, {checked} task-AC citations "
        f"checked; every cited AC is declared by its task, and every "
        f"task is paired with a Task Details entry."
    )


if __name__ == "__main__":
    main()
