#!/usr/bin/env python3
# export-open-scouts.py - export a session's open [Scout] tasks
#   as markdown, so /quality-gate's scout leg can judge them
#   without TaskList tools.
#
# Usage:
#   export-open-scouts.py <session_id> <out_path>
#   export-open-scouts.py --tasks-root <dir> <session_id> \
#     <out_path>
#
# Reads <tasks-root>/<session_id>/*.json (tasks-root defaults to
#   ~/.claude/tasks). Keeps a task whose status is pending and
#   whose subject contains [Scout].
#
# An in_progress scout is left out: a subagent or lateral
#   session may be fixing it, and exporting it would apply the
#   same fix twice.
#
# stdin: none.
#
# stdout: the number of tasks exported. <out_path> gets one
#   "## #<id> <subject>" section per task, in numeric id order,
#   with the task's description below; with 0 tasks, or no
#   session directory, it prints 0 and writes no file.
#
# exit: 0 success, 1 an unreadable or malformed task file (named
#   on stderr; no file is written), 2 bad arguments
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_NAME = "export-open-scouts.py"

DEFAULT_TASKS_ROOT = Path.home() / ".claude/tasks"

OPEN_STATUS = "pending"
SCOUT_MARK = "[Scout]"

# The TaskList subject carries a " <n>. [#<id>]" prefix ahead of
# its category tag; the section heading already shows the id.
SUBJECT_ID_PREFIX = re.compile(r"^\s*\d+\.\s*\[#\d+\]\s*")


class MalformedTaskError(Exception):
    pass


def read_task(task_path):
    try:
        task = json.loads(task_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MalformedTaskError(f"cannot read {task_path}: {error}") from error
    is_well_formed = (
        isinstance(task, dict)
        and isinstance(task.get("subject"), str)
        and isinstance(task.get("status"), str)
        and str(task.get("id", "")).isdigit()
    )
    if not is_well_formed:
        raise MalformedTaskError(
            f"{task_path} must hold an object with a numeric id, "
            "a string subject and a string status"
        )
    return task


def is_open_scout(task):
    return task["status"] == OPEN_STATUS and SCOUT_MARK in task["subject"]


def get_open_scouts(session_dir):
    if not session_dir.is_dir():
        return []
    tasks = [read_task(task_path) for task_path in session_dir.glob("*.json")]
    open_scouts = [task for task in tasks if is_open_scout(task)]
    return sorted(open_scouts, key=lambda task: int(task["id"]))


def get_scout_section(task):
    subject = SUBJECT_ID_PREFIX.sub("", task["subject"]).strip()
    description = (task.get("description") or "").strip()
    return f"## #{task['id']} {subject}\n\n{description}\n"


def main():
    parser = argparse.ArgumentParser(
        description="Export a session's open [Scout] tasks as markdown "
        "and print how many were exported."
    )
    parser.add_argument(
        "--tasks-root",
        type=Path,
        default=DEFAULT_TASKS_ROOT,
        help="directory holding one task directory per session "
        "(default: ~/.claude/tasks)",
    )
    parser.add_argument("session_id", help="the session whose tasks to read")
    parser.add_argument("out_path", type=Path, help="markdown file to write")
    arguments = parser.parse_args()
    try:
        open_scouts = get_open_scouts(arguments.tasks_root / arguments.session_id)
    except MalformedTaskError as error:
        print(f"{SCRIPT_NAME}: {error}", file=sys.stderr)
        sys.exit(1)
    if open_scouts:
        sections = [get_scout_section(task) for task in open_scouts]
        try:
            arguments.out_path.write_text("\n".join(sections), encoding="utf-8")
        except OSError as error:
            print(
                f"{SCRIPT_NAME}: cannot write {arguments.out_path}: {error}",
                file=sys.stderr,
            )
            sys.exit(1)
    print(len(open_scouts))


if __name__ == "__main__":
    main()
