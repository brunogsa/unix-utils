#!/usr/bin/env python3
# implement-loop-state.py - Pure verdict script for the /implement task loop
#
# Usage:
#   implement-loop-state.py <state-file>
#   implement-loop-state.py --budget <state-file>
#   implement-loop-state.py --next-eligible <state-file>
#   implement-loop-state.py --eligible-set <state-file>
#
# stdin: none
# stdout: one JSON verdict/answer object (shape depends on the flag)
# exit: 0 on success, 1 on usage error, missing/invalid state
#       file, or (no-flag mode) a phase this script has no verdict for

import json
import re
import sys
from pathlib import Path

# Pure: no writes, no clock reads, deterministic -- the same state
# file always yields the same verdict. The orchestrator (main
# session AI) is the fallible recorder of raw facts (attempt
# outcomes, phase, report paths); this script is the infallible
# judge that turns those facts into one of seven actions.

# Tunable constants.
MAX_ATTEMPTS = 3
STUCK_CONSECUTIVE = 3
BATCH_CAP_MULT = 4
GATE_FIX_ALLOWANCE = 2

# NOTE: this text still names the script "implement-loop-state.sh"
# (not .py) because it is replayed byte-for-byte against a golden
# table captured from the original shell script -- see
# scripts/tests/implement-loop-state.test.py. Renaming the
# self-reference is Task 14's job (full rename to
# resolve-task-loop-verdict), not this conversion's.
USAGE = 'usage: implement-loop-state.sh <state-file>\n       implement-loop-state.sh --budget <state-file>\n       implement-loop-state.sh --next-eligible <state-file>\n       implement-loop-state.sh --eligible-set <state-file>\n\nWith no flag, reads a /implement run\'s JSON state file at phase "tasks" and\nprints one JSON verdict:\n  {"action": "retry|stuck|next-task|wait|gates|halted|halt-budget", "task": "...", "reason": "..."}\n\n--budget: is the batch\'s dispatch budget exhausted? Works at any phase.\n  {"exhausted": true|false, "total_dispatches": N, "budget_threshold": N, "reason": "..."}\n\n--next-eligible: which pending task is DAG-eligible to dispatch next? Works\nat any phase, and does not depend on attempts[-1].result. Checks the same\nbatch dispatch budget --budget and --eligible-set check; once it\'s\nexhausted this answers "none" regardless of eligibility (reason names the\nbudget). Otherwise "none" with a non-zero in_progress means wait for a live\nsibling, not halt.\n  {"task": "<id or the literal string \\"none\\">", "in_progress": N, "reason": "..."}\n\n--eligible-set: every task dispatchable right now, for a parallel wave. Works\nat any phase. Empty tasks[] with in_progress > 0 means wait; empty with\nin_progress 0 means the wave drained. exhausted true forces tasks[] empty.\n  {"tasks": ["<id>", ...], "in_progress": N, "exhausted": true|false, "reason": "..."}\n\nExamples:\n  implement-loop-state.sh /tmp/implement_abc123.json\n  implement-loop-state.sh --budget /tmp/implement_abc123.json\n  implement-loop-state.sh --next-eligible /tmp/implement_abc123.json\n  implement-loop-state.sh --eligible-set /tmp/implement_abc123.json\n'


def normalize_signature(signature: str) -> str:
    # Two failures differing only by a line number or a tmp path
    # count as the same signature: lowercase, drop any
    # whitespace-delimited token containing "/" (path-like), strip
    # digits, then collapse whitespace.
    lowered = signature.lower()
    kept_tokens = [token for token in lowered.split() if "/" not in token]
    digits_stripped = re.sub(r"\d", "", " ".join(kept_tokens))
    return re.sub(r"\s+", " ", digits_stripped).strip()


def emit_verdict(action: str, task: str, reason: str) -> None:
    print(json.dumps({"action": action, "task": task, "reason": reason}, indent=2))


def emit_budget(exhausted: bool, total: int, threshold: int, reason: str) -> None:
    # Same key-plus-reason shape as emit_verdict, not a second ad
    # hoc convention.
    print(json.dumps({
        "exhausted": exhausted,
        "total_dispatches": total,
        "budget_threshold": threshold,
        "reason": reason,
    }, indent=2))


def emit_next_eligible(task: str, running: int, reason: str) -> None:
    # Reuses emit_verdict's "task"/"reason" fields as one family.
    print(json.dumps({"task": task, "in_progress": running, "reason": reason}, indent=2))


def emit_eligible_set(tasks: list, running: int, exhausted: bool, reason: str) -> None:
    # The whole dispatchable set, plus the two counts its caller
    # needs to tell "wait for a sibling" from "the wave drained".
    print(json.dumps({
        "tasks": tasks,
        "in_progress": running,
        "exhausted": exhausted,
        "reason": reason,
    }, indent=2))


def fail(message: str) -> None:
    # Fail-loud by design: this is not the fail-open component --
    # that role belongs to claude-implement-stop-hook.sh.
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def in_progress_count(state: dict) -> int:
    # The script owns this count rather than leaving the caller to
    # compute it, so the orchestrator stays the recorder of raw
    # facts and never becomes a second judge.
    return sum(1 for task in state["tasks"] if task.get("status") == "in_progress")


class BudgetStatus:
    """task_count/total_dispatches/budget_threshold/exhausted for
    one state file, computed once and shared by --budget,
    --eligible-set, --next-eligible, and the no-flag backstop below
    -- so the one comparison can't drift into four slightly
    different ones."""

    __slots__ = ("task_count", "total_dispatches", "budget_threshold", "exhausted")

    def __init__(self, task_count: int, total_dispatches: int, budget_threshold: int):
        self.task_count = task_count
        self.total_dispatches = total_dispatches
        self.budget_threshold = budget_threshold
        # The batch-wide dispatch budget (BATCH_CAP_MULT * task
        # count + GATE_FIX_ALLOWANCE) is the backstop for a runaway
        # gate-fixing loop (gate_dispatches piling up), since a
        # single task alone can never exceed MAX_ATTEMPTS + 1
        # attempts before the per-task "stuck" verdict already
        # caught it.
        self.exhausted = total_dispatches >= budget_threshold


def compute_budget_status(state: dict) -> BudgetStatus:
    task_count = len(state["tasks"])
    attempts_n = len(state["attempts"])
    gate_n = state.get("gate_dispatches") or 0
    total_dispatches = attempts_n + gate_n
    budget_threshold = BATCH_CAP_MULT * task_count + GATE_FIX_ALLOWANCE
    return BudgetStatus(task_count, total_dispatches, budget_threshold)


def budget_clause(status: BudgetStatus, *, verb: str) -> str:
    return (
        f"total dispatches ({status.total_dispatches}) {verb} the batch budget "
        f"({status.budget_threshold} = {BATCH_CAP_MULT}x{status.task_count} tasks "
        f"+ {GATE_FIX_ALLOWANCE} gate allowance)"
    )


def eligible_tasks(state: dict, exclude_id: str) -> list:
    # DAG-eligible, non-terminal tasks, lowest id first. Shared by
    # the "pass" branch below and --next-eligible, so the
    # eligibility rule is authored once.
    #
    # exclude_id: the "pass" branch's own current task, whose
    # tasks[].status may still read "pending" here -- status can
    # lag attempts[]. It needs an explicit exclusion on top of the
    # status check. Pass "" for no exclusion.
    #
    # --next-eligible has no "current task": any task it should
    # exclude already carries a terminal status, set by its own
    # caller before asking what runs next -- the status check alone
    # covers it there.
    #
    # "in_progress" is excluded as a third non-terminal status
    # because it means already dispatched -- the only thing
    # stopping a parallel wave from dispatching one task into two
    # worktrees.
    status_by_id = {task["id"]: task["status"] for task in state["tasks"]}

    def is_eligible(task: dict) -> bool:
        if exclude_id and task["id"] == exclude_id:
            return False
        if task["status"] in ("done", "blocked", "in_progress"):
            return False
        deps = task.get("depends_on") or []
        # An absent dependency id belongs to an earlier PR that
        # pr-awareness.md's stop predicate already required to be
        # done before this unit could start, so treating "absent"
        # as "satisfied" is deliberate, not a gap.
        return all(status_by_id.get(dep, "done") == "done" for dep in deps)

    eligible = [task for task in state["tasks"] if is_eligible(task)]
    eligible.sort(key=lambda task: int(task["id"]))
    return eligible


def load_state(state_file: Path) -> dict:
    if not state_file.is_file():
        fail(f"state file not found: {state_file}")
    try:
        return json.loads(state_file.read_text())
    except json.JSONDecodeError:
        fail(f"state file is not valid JSON: {state_file}")


def verdict_pass(state: dict, current_task: str) -> None:
    remaining = [
        task for task in state["tasks"]
        if task["id"] != current_task and task["status"] not in ("done", "blocked")
    ]
    if remaining:
        # DAG-eligible: every declared depends_on id is either
        # "done" in this unit's own tasks[], or absent from it (an
        # earlier PR's task, already required done by the time this
        # unit started).
        eligible = eligible_tasks(state, current_task)
        if not eligible:
            # No pending task is DAG-eligible right now, but that
            # is not necessarily a dead end: a non-zero in_progress
            # means one or more dispatched siblings just haven't
            # reported yet, and dispatching more or halting the run
            # would be premature -- only a true zero in_progress
            # means this really is a dependency deadlock.
            running = in_progress_count(state)
            if running > 0:
                emit_verdict("wait", "",
                    f"task {current_task} passed and {len(remaining)} task(s) remain, "
                    f"but {running} sibling task(s) are still in_progress and haven't "
                    f"reported yet; dispatch nothing and wait for them before re-verdicting")
            else:
                emit_verdict("halted", "",
                    f"task {current_task} passed and {len(remaining)} task(s) remain, "
                    f"but none have every declared dependency satisfied (likely blocked "
                    f"upstream); halting here for the human instead of dispatching an "
                    f"ineligible task")
        else:
            next_task = eligible[0]["id"]
            emit_verdict("next-task", next_task,
                f"task {current_task} passed; dispatch next DAG-eligible pending task "
                f"{next_task} (lowest id among tasks whose dependencies are all done)")
        return

    # The gates phase is reachable only when every task in the
    # batch ended "done": once the current task passes and no
    # non-terminal task remains, a "blocked" task among tasks[]
    # means the batch verdicts "halted" instead of "gates", so a
    # run with an unresolved blocked task stops for the human
    # rather than running gates over an incomplete batch.
    blocked_count = sum(1 for task in state["tasks"] if task["status"] == "blocked")
    if blocked_count > 0:
        emit_verdict("halted", "",
            f"task {current_task} passed but {blocked_count} task(s) ended blocked; "
            f"halting here for the human instead of reaching the gates")
    else:
        emit_verdict("gates", "",
            f"task {current_task} passed and every task in the batch is done; "
            f"proceed to the test-presence gate")


def verdict_fail_or_timeout(state: dict, current_task: str) -> None:
    task_attempts = [a for a in state["attempts"] if a["task"] == current_task]
    n_attempts = len(task_attempts)
    signatures = [normalize_signature(a["signature"]) for a in task_attempts]

    # A "blocked" attempt (handled by the caller before this
    # function runs) verdicts "stuck" on its first occurrence, with
    # no retry and no signature comparison -- but a repeated "fail"
    # needs the signature-window check below to tell "stuck in a
    # loop" from "still making forward progress".
    consecutive_identical = False
    if n_attempts >= STUCK_CONSECUTIVE:
        window = signatures[n_attempts - STUCK_CONSECUTIVE:]
        consecutive_identical = len(set(window)) == 1

    if consecutive_identical:
        emit_verdict("stuck", current_task,
            f"task {current_task} repeated the same failure signature "
            f"{STUCK_CONSECUTIVE} times in a row")
    elif n_attempts > MAX_ATTEMPTS:
        emit_verdict("stuck", current_task,
            f"task {current_task} exceeded the {MAX_ATTEMPTS}-attempt cap "
            f"without a consistent pass")
    else:
        emit_verdict("retry", current_task,
            f"task {current_task} failed attempt {n_attempts} of "
            f"{MAX_ATTEMPTS + 1}; retry")


def main(argv: list) -> int:
    if argv and argv[0] in ("--help", "-h"):
        sys.stdout.write(USAGE)
        return 0

    mode = "verdict"
    if argv and argv[0] in ("--budget", "--next-eligible", "--eligible-set"):
        mode = argv[0].lstrip("-")
        argv = argv[1:]

    if len(argv) != 1:
        sys.stderr.write(USAGE)
        return 1

    state_file = Path(argv[0])
    state = load_state(state_file)
    status = compute_budget_status(state)

    if mode == "budget":
        emit_budget(status.exhausted, status.total_dispatches, status.budget_threshold,
                    budget_clause(status, verb="vs."))
        return 0

    # --next-eligible shares compute_budget_status with
    # --eligible-set (below) and the no-flag backstop, so its
    # sequential caller never dispatches a task past the same cap a
    # parallel wave respects.
    if mode == "next-eligible":
        running = in_progress_count(state)
        if status.exhausted:
            emit_next_eligible("none", running,
                budget_clause(status, verb="reached") +
                "; dispatch nothing further and let any live sibling finish")
            return 0
        eligible = eligible_tasks(state, "")
        if not eligible:
            emit_next_eligible("none", running,
                "no pending task has every declared dependency satisfied "
                "(done, or absent from this unit's own tasks[]); a "
                "non-zero in_progress means wait for those siblings "
                "instead of halting")
        else:
            emit_next_eligible(eligible[0]["id"], running,
                "lowest-id pending task whose dependencies are all done "
                "(or absent from this unit's own tasks[])")
        return 0

    # --eligible-set and --next-eligible (above) are the two direct
    # dispatch deciders (parallel wave, sequential pick), so both
    # carry the batch budget the plain verdict path checks. Without
    # it a wave of retries, or a sequential loop through repeated
    # stuck picks, runs past the cap that exists to stop a runaway
    # loop.
    if mode == "eligible-set":
        running = in_progress_count(state)
        if status.exhausted:
            emit_eligible_set([], running, True,
                budget_clause(status, verb="reached") +
                "; dispatch nothing further and let any live sibling finish")
            return 0
        eligible = eligible_tasks(state, "")
        emit_eligible_set([task["id"] for task in eligible], running, False,
            "every task whose declared dependencies are all done and "
            "which is not already dispatched, lowest id first")
        return 0

    # Batch-wide budget backstop, checked before any per-task
    # logic. Its caller halts the run and waits for the human -- it
    # does not proceed to the batch-end flow.
    if status.exhausted:
        emit_verdict("halt-budget", "",
            budget_clause(status, verb="reached") +
            "; halting the run here and waiting for the human")
        return 0

    # This no-flag mode only verdicts phase "tasks"
    # (retry/stuck/next-task/wait/gates/halted/halt-budget). Any
    # other phase is a caller misuse it fails loud on rather than
    # guess a verdict for.
    phase = state.get("phase")
    if phase != "tasks":
        fail(f"no verdict defined for phase '{phase}' (this script only verdicts phase 'tasks')")

    attempts = state["attempts"]
    if not attempts:
        fail("no attempts recorded yet; nothing to verdict for phase 'tasks'")

    # The "current task" is whichever task the LAST entry in
    # attempts[] belongs to -- not tasks[].status, which the
    # orchestrator may lag on.
    current_task = attempts[-1]["task"]
    last_result = attempts[-1]["result"]

    if last_result == "pass":
        verdict_pass(state, current_task)
    elif last_result == "blocked":
        emit_verdict("stuck", current_task,
            f"task {current_task} reported blocked; only the human can clear it, "
            f"so no retry is issued")
    elif last_result in ("fail", "timeout"):
        verdict_fail_or_timeout(state, current_task)
    else:
        fail(f"unknown attempt result '{last_result}' for task {current_task} "
             f"(expected pass, blocked, fail, or timeout)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
