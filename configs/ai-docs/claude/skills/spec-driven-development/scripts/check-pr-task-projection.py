#!/usr/bin/env python3
"""check-pr-task-projection.py - self-review validator: the Task
Breakdown's dependency graph, projected onto the PR Breakdown's
partition, respects PR order.

Usage:
  check-pr-task-projection.py <plan-file>

check-tasks-dag.sh validates the Task Breakdown's own graph.
check-pr-dag.sh validates the PR Breakdown's own graph. Neither
validates the PROJECTION of one onto the other, so a plan can pass
both individually while still being wrong: a task in an early PR can
depend on a task that lives in a later PR the early PR never lists
as a dependency. /implement's dispatch rule then treats that missing
id as "belongs to an earlier PR, already satisfied" and silently
dispatches the task before its real prerequisite has run.

Extracts "## Task Breakdown" and "## PR Breakdown" via plan-section.sh
(never a per-line regex — PR Breakdown entries wrap across physical
lines, and a line-oriented read silently drops the wrapped clause).
Detects, each with its own diagnostic:
  - a task id claimed by no PR;
  - a task id claimed by more than one PR;
  - a PR entry naming a task id the Task Breakdown does not define;
  - a task whose dependency lives in a PR that is neither the same
    PR nor a transitive ancestor of it in the PR graph (the
    cross-level violation — subsumes both a cross-level cycle and
    the silent early-PR-assumption defect above).

Exit codes:
  0 - PR Breakdown is absent, reads "Single PR.", or every task's
      dependency projection onto the PR partition is consistent.
  1 - one of the four defects above was found (diagnostics on stderr).
  2 - usage error (wrong arg count, plan file missing, a breakdown
      section carries real entries that could not be parsed).
"""
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_SECTION = SCRIPT_DIR / "plan-section.sh"

# A PR label's bold span tolerates the optional "[<status>] "
# prefix plan-template.md documents (e.g. "**[Done] PR-1**"),
# mirroring check-pr-dag.sh's own permissive label regex.
PR_ENTRY_RE = re.compile(
    r"\*\*[^*]*PR-(?P<pid>\d+)[^*]*\*\*(?P<body>.*?)"
    r"Depends on:\s*(?P<deps>[^.]*)\.",
    re.S,
)
TASKS_CLAUSE_RE = re.compile(r"Tasks:\s*(?P<tasks>[\d,\s]+)\.")

# Task headings split the section into per-task chunks so a
# dependency block can never leak into a neighboring task,
# mirroring check-tasks-dag.sh's own state-machine boundary.
TASK_HEADING_SPLIT_RE = re.compile(r"^### (\d+)\. ", re.M)
TASK_DEPS_BLOCK_RE = re.compile(r"\*\*Depends on\*\*:\n((?:- .*\n?)+)")


def extract_section(plan_file: Path, heading_pattern: str) -> str:
    """Return one "##"-depth section's body via the shared extractor,
    so trailing "---" divider trimming stays in one place."""
    try:
        result = subprocess.run(
            [str(PLAN_SECTION), str(plan_file), "##", heading_pattern],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"error: failed to extract plan section: {exc}", file=sys.stderr)
        sys.exit(2)
    return result.stdout


def parse_pr_entries(section: str):
    """Return (pr_tasks, pr_deps): PR-id -> claimed task ids, and
    PR-id -> the PR ids it depends on."""
    pr_tasks: dict[str, list[str]] = {}
    pr_deps: dict[str, list[str]] = {}
    for match in PR_ENTRY_RE.finditer(section):
        pid = match.group("pid")
        tasks_match = TASKS_CLAUSE_RE.search(match.group("body"))
        pr_tasks[pid] = re.findall(r"\d+", tasks_match.group("tasks")) if tasks_match else []
        pr_deps[pid] = re.findall(r"PR-(\d+)", match.group("deps"))
    return pr_tasks, pr_deps


def parse_task_entries(section: str) -> dict[str, list[str]]:
    """Return task id -> the task ids it depends on, for every
    "### N." entry in a Task Breakdown section."""
    chunks = TASK_HEADING_SPLIT_RE.split(section)
    task_deps: dict[str, list[str]] = {}
    for tid, body in zip(chunks[1::2], chunks[2::2]):
        deps_match = TASK_DEPS_BLOCK_RE.search(body)
        task_deps[tid] = re.findall(r"- Task (\d+)", deps_match.group(1)) if deps_match else []
    return task_deps


def get_ancestor_prs(pid: str, pr_deps: dict[str, list[str]]) -> set[str]:
    """Return every PR reachable by following "Depends on" edges from
    pid, cycle-safe via the visited set (a genuine PR-graph cycle is
    check-pr-dag.sh's own diagnostic, not this script's)."""
    seen: set[str] = set()
    stack = list(pr_deps.get(pid, []))
    while stack:
        candidate = stack.pop()
        if candidate not in seen:
            seen.add(candidate)
            stack.extend(pr_deps.get(candidate, []))
    return seen


def find_projection_problems(task_deps, pr_tasks, pr_deps) -> list[str]:
    """Return one diagnostic string per defect found, in a fixed
    category order (unowned, duplicate, undefined, cross-level) with
    ids sorted numerically within each category for deterministic
    output."""
    problems: list[str] = []

    owning_prs: dict[str, list[str]] = {}
    for pid, task_ids in pr_tasks.items():
        for tid in task_ids:
            owning_prs.setdefault(tid, []).append(pid)

    unowned = sorted(set(task_deps) - set(owning_prs), key=int)
    for tid in unowned:
        problems.append(
            f"Task {tid} is defined in the Task Breakdown but claimed by no PR"
        )

    owner: dict[str, str] = {}
    for tid in sorted(owning_prs, key=int):
        prs = owning_prs[tid]
        if tid not in task_deps:
            for pid in sorted(prs, key=int):
                problems.append(
                    f"PR-{pid} Tasks: list names Task {tid}, which the "
                    "Task Breakdown does not define"
                )
            continue
        if len(prs) > 1:
            labels = ", ".join(f"PR-{p}" for p in sorted(prs, key=int))
            problems.append(
                f"Task {tid} is claimed by more than one PR: {labels}"
            )
            continue
        owner[tid] = prs[0]

    for tid in sorted(owner, key=int):
        home_pid = owner[tid]
        allowed = get_ancestor_prs(home_pid, pr_deps) | {home_pid}
        for dep_tid in task_deps.get(tid, []):
            dep_home = owner.get(dep_tid)
            if dep_home is None or dep_home in allowed:
                continue
            problems.append(
                f"Task {tid} in PR-{home_pid} depends on Task {dep_tid}, "
                f"which lives in PR-{dep_home} — PR-{dep_home} is neither "
                f"PR-{home_pid} nor an ancestor of it in the PR graph"
            )

    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <plan-file>", file=sys.stderr)
        return 2

    plan_file = Path(sys.argv[1])
    if not plan_file.is_file():
        print(f"error: plan file not found: {plan_file}", file=sys.stderr)
        return 2

    pr_section = extract_section(plan_file, "^PR Breakdown[[:space:]]*$")
    trimmed = pr_section.strip()

    if not trimmed:
        print("OK: PR Breakdown has nothing to validate (section absent).")
        return 0
    if trimmed == "Single PR.":
        print("OK: PR Breakdown has nothing to validate (reads 'Single PR.').")
        return 0

    pr_tasks, pr_deps = parse_pr_entries(pr_section)
    if not pr_tasks:
        print(
            "error: PR Breakdown section found but no PR-N entries "
            "could be parsed from it",
            file=sys.stderr,
        )
        return 2

    task_section = extract_section(plan_file, "^Task Breakdown[[:space:]]*$")
    task_deps = parse_task_entries(task_section)
    if not task_deps:
        print(
            "error: Task Breakdown section found but no task entries "
            "could be parsed from it",
            file=sys.stderr,
        )
        return 2

    problems = find_projection_problems(task_deps, pr_tasks, pr_deps)
    if problems:
        print(
            "FAIL (task-to-PR projection): the task graph, projected "
            "onto the PR partition, is inconsistent:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(
        f"OK: {len(task_deps)} task(s) across {len(pr_tasks)} PR(s), "
        "projection is consistent (no unowned, duplicate, undefined, "
        "or cross-level task)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
