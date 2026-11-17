#!/usr/bin/env python3
# get-plan-tasks-for-branch.py - print the plan task ids one
#   branch's PR ships, for quality-gate's --tasks.
#
# Usage:
#   get-plan-tasks-for-branch.py <plan-path> <branch>
#
# stdin: none.
#
# stdout: the task ids of the "## PR Breakdown" entry whose
#   **Branch**: line equals <branch>, comma-separated with no
#   spaces (e.g. 10,11).
#
#   Empty when no entry names the branch or the plan has no
#   PR breakdown.
#
# exit: 0 success, 1 unreadable plan, branch named by 2+
#   entries, or the matching entry lists no task ids
import argparse
import importlib.util
import re
import sys
from pathlib import Path

SCRIPT_NAME = "get-plan-tasks-for-branch.py"

PR_BREAKDOWN_HEADING = "## PR Breakdown"

SECTION_END = re.compile(r"^#{1,2} ")

PR_ENTRY_HEADING = re.compile(r"^### (?P<title>.*?)\s*$")

BRANCH_LINE = re.compile(r"^\*\*Branch\*\*:(?P<value>.*)$")

TASKS_LINE = re.compile(r"^\*\*Tasks\*\*:(?P<value>.*)$")

PARSE_FENCES_PATH = Path(__file__).with_name("parse-fences.py")


def load_toggle_fence():
    spec = importlib.util.spec_from_file_location("parse_fences", PARSE_FENCES_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {PARSE_FENCES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.toggle_fence


def fail(message):
    print(f"{SCRIPT_NAME}: {message}", file=sys.stderr)
    sys.exit(1)


def read_plan(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(f"cannot read {path}: {error}")


def iter_lines_outside_fences(plan_text):
    toggle_fence = load_toggle_fence()
    fence_state = (False, "", 0)
    for line in plan_text.splitlines():
        previous_state = fence_state
        fence_state = toggle_fence(line, *fence_state)
        is_inside_fence = previous_state[0] or fence_state[0]
        if not is_inside_fence:
            yield line


def iter_pr_breakdown_lines(plan_text):
    is_in_breakdown = False
    for line in iter_lines_outside_fences(plan_text):
        if line.strip() == PR_BREAKDOWN_HEADING:
            is_in_breakdown = True
        elif SECTION_END.match(line):
            is_in_breakdown = False
        elif is_in_breakdown:
            yield line


def list_pr_entries(plan_text):
    """Each entry: heading title, branch (None when the Branch
    line is absent or blank, so no branch name matches it),
    and tasks text (None when no Tasks line)."""
    entries = []
    for line in iter_pr_breakdown_lines(plan_text):
        heading = PR_ENTRY_HEADING.match(line)
        if heading:
            entries.append({"title": heading["title"], "branch": None, "tasks": None})
            continue
        if not entries:
            continue
        branch = BRANCH_LINE.match(line)
        tasks = TASKS_LINE.match(line)
        if branch:
            branch_name = branch["value"].strip().strip("`").strip()
            entries[-1]["branch"] = branch_name or None
        elif tasks:
            entries[-1]["tasks"] = tasks["value"]
    return entries


def get_task_ids(entry):
    task_ids = [task_id.strip() for task_id in (entry["tasks"] or "").split(",")]
    return [task_id for task_id in task_ids if task_id]


def main():
    parser = argparse.ArgumentParser(
        description="Print the comma-separated task ids of the plan's "
        "PR Breakdown entry for a branch; empty when none names it."
    )
    parser.add_argument("plan", help="path to a plan_<slug>.md")
    parser.add_argument("branch", help="branch name, matched exactly")
    arguments = parser.parse_args()

    entries = list_pr_entries(read_plan(arguments.plan))
    matching_entries = [e for e in entries if e["branch"] == arguments.branch]
    if not matching_entries:
        return
    if len(matching_entries) > 1:
        titles = "; ".join(e["title"] for e in matching_entries)
        fail(f"branch {arguments.branch} must name one PR entry; named by: {titles}")
    entry = matching_entries[0]
    task_ids = get_task_ids(entry)
    if not task_ids:
        fail(f"PR entry '{entry['title']}' must list task ids on a **Tasks**: line")
    print(",".join(task_ids))


if __name__ == "__main__":
    main()
