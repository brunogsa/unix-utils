#!/usr/bin/env bash
# implement-loop-state.sh - pure verdict script for the /implement task loop.
#
# Usage:
#   implement-loop-state.sh <state-file>
#   implement-loop-state.sh --budget <state-file>
#   implement-loop-state.sh --next-eligible <state-file>
#   implement-loop-state.sh --eligible-set <state-file>
#
# With no flag, reads a /implement run's JSON state file and
# prints one JSON verdict on stdout, for phase "tasks" only:
#   {"action": "retry|stuck|next-task|wait|gates|halted|halt-budget", "task": "<id or empty>", "reason": "..."}
#
# --budget, --next-eligible and --eligible-set are
# phase-independent query modes; see "Design" below for what
# each answers and why.
#
# Examples:
#   implement-loop-state.sh /tmp/implement_abc123.json
#   implement-loop-state.sh --budget /tmp/implement_abc123.json
#   implement-loop-state.sh --next-eligible /tmp/state.json
#   implement-loop-state.sh --eligible-set /tmp/state.json
#
# Pure: no writes, no clock reads, deterministic — the same state file always
# yields the same verdict. The orchestrator (main session AI) is the fallible
# recorder of raw facts (attempt outcomes, phase, report paths); this script is
# the infallible judge that turns those facts into one of seven actions.
#
# Design:
#   - The "current task" is whichever task the LAST entry in `attempts[]`
#     belongs to — not `tasks[].status`, which the orchestrator may lag on.
#   - A task is "terminal" (no longer blocks the per-task loop) once its
#     `status` is "done" or "blocked" — but a "blocked" task still blocks the
#     batch from reaching the gates; see the "halted" note below.
#   - Failure-signature comparison lowercases, drops any whitespace-delimited
#     token containing "/" (path-like), strips digits, then collapses
#     whitespace — so two failures differing only by a line number or a tmp
#     path count as the same signature.
#   - A "blocked" attempt verdicts "stuck" on its first occurrence, with no
#     retry and no signature comparison: it means the subagent hit something
#     only a human can clear, so re-dispatching the same task would burn a
#     dispatch to reach the same wall. Routing it through the script (rather
#     than letting the caller shortcut to "stuck" itself) keeps every attempt
#     inside the same budget accounting.
#   - The gates phase is reachable only when every task in the batch ended
#     "done". Once the current task passes and no non-terminal task remains,
#     the script checks for a "blocked" task among `tasks[]`: any found means
#     the batch verdicts "halted" instead of "gates", so a run with an
#     unresolved blocked task stops for the human rather than running gates
#     over an incomplete batch.
#   - "next-task" only ever names a DAG-eligible task: one whose `depends_on`
#     ids (from the plan's "Depends on" clause, seeded verbatim at §2.3) are
#     each either "done" in this unit's own `tasks[]`, or absent from it
#     entirely. An absent id belongs to an earlier PR that pr-awareness.md's
#     stop predicate already required to be `[Done]` before this unit could
#     start, so treating "absent" as "satisfied" is deliberate, not a gap —
#     it also means a seeding typo that mis-writes an id is swallowed rather
#     than caught here. Among eligible tasks the lowest id wins, same
#     tiebreak as before. If pending tasks remain but none are eligible, the
#     verdict is "wait" when a sibling is still `in_progress` — it may
#     become eligible once that sibling reports — or "halted" when
#     in_progress is zero, a real same-unit dependency deadlock (e.g. every
#     remaining task depends on one this run just marked "blocked") that is
#     a runtime dead end for the human, not a script failure.
#   - The batch-wide dispatch budget (BATCH_CAP_MULT * task count +
#     GATE_FIX_ALLOWANCE) is checked before any per-task logic: it is the
#     backstop for a runaway gate-fixing loop (gate_dispatches piling up),
#     since a single task alone can never exceed MAX_ATTEMPTS + 1 attempts
#     before the per-task "stuck" verdict already caught it. Its caller halts
#     the run and waits for the human — it does not proceed to the
#     batch-end flow. `--budget` answers this same threshold
#     question for a caller outside phase "tasks" (see below).
#   - This no-flag mode only verdicts phase "tasks" (retry/stuck/
#     next-task/wait/gates/halted/halt-budget). Any other phase is a
#     caller misuse it fails loud on rather than guess a verdict
#     for. The gate and batch-end flow that run after the task
#     loop are linear, but they DO call this script: `--budget`
#     (the repo-green fix loop's stop condition) and
#     `--next-eligible` (the stuck-task pick after a failed
#     attempt) — both bypass the phase guard and the
#     attempts[]-dependent logic entirely, since neither one
#     judges a "tasks"-phase attempt.
#
# Exit codes:
#   0 - answer printed on stdout: a verdict (no flag), or a
#       budget/eligibility answer (--budget/--next-eligible).
#
#   1 - usage error, missing file, invalid JSON, or (no-flag
#       mode only) a phase this script has no verdict for.
#       Fail-loud by design: this is not the fail-open
#       component — that's claude-implement-stop-hook.sh.

set -eo pipefail

# Tunable constants.
MAX_ATTEMPTS=3
STUCK_CONSECUTIVE=3
BATCH_CAP_MULT=4
GATE_FIX_ALLOWANCE=2

usage() {
  cat <<'EOF'
usage: implement-loop-state.sh <state-file>
       implement-loop-state.sh --budget <state-file>
       implement-loop-state.sh --next-eligible <state-file>
       implement-loop-state.sh --eligible-set <state-file>

With no flag, reads a /implement run's JSON state file at phase "tasks" and
prints one JSON verdict:
  {"action": "retry|stuck|next-task|wait|gates|halted|halt-budget", "task": "...", "reason": "..."}

--budget: is the batch's dispatch budget exhausted? Works at any phase.
  {"exhausted": true|false, "total_dispatches": N, "budget_threshold": N, "reason": "..."}

--next-eligible: which pending task is DAG-eligible to dispatch next? Works
at any phase, and does not depend on attempts[-1].result. "none" with a
non-zero in_progress means wait for a live sibling, not halt.
  {"task": "<id or the literal string \"none\">", "in_progress": N, "reason": "..."}

--eligible-set: every task dispatchable right now, for a parallel wave. Works
at any phase. Empty tasks[] with in_progress > 0 means wait; empty with
in_progress 0 means the wave drained. exhausted true forces tasks[] empty.
  {"tasks": ["<id>", ...], "in_progress": N, "exhausted": true|false, "reason": "..."}

Examples:
  implement-loop-state.sh /tmp/implement_abc123.json
  implement-loop-state.sh --budget /tmp/implement_abc123.json
  implement-loop-state.sh --next-eligible /tmp/implement_abc123.json
  implement-loop-state.sh --eligible-set /tmp/implement_abc123.json
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

mode="verdict"
if [ "${1:-}" = "--budget" ] || [ "${1:-}" = "--next-eligible" ] \
  || [ "${1:-}" = "--eligible-set" ]; then
  mode="${1#--}"
  shift
fi

if [ $# -ne 1 ]; then
  usage >&2
  exit 1
fi

state_file="$1"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required but not found on PATH" >&2
  exit 1
fi

if [ ! -f "$state_file" ]; then
  echo "error: state file not found: $state_file" >&2
  exit 1
fi

if ! jq empty "$state_file" >/dev/null 2>&1; then
  echo "error: state file is not valid JSON: $state_file" >&2
  exit 1
fi

# normalize_signature - lowercase, drop path-like tokens, strip digits, collapse whitespace.
normalize_signature() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | awk '{
        out = ""
        for (i = 1; i <= NF; i++) {
          if ($i !~ /\//) out = out $i " "
        }
        print out
      }' \
    | tr -d '0-9' \
    | tr -s '[:space:]' ' ' \
    | sed -e 's/^ *//' -e 's/ *$//'
}

emit_verdict() {
  local action="$1" task="$2" reason="$3"
  jq -n --arg action "$action" --arg task "$task" --arg reason "$reason" \
    '{action: $action, task: $task, reason: $reason}'
}

# emit_budget - JSON for --budget: same key-plus-reason
# shape as emit_verdict, not a second ad hoc convention.
emit_budget() {
  local exhausted="$1" total="$2" threshold="$3" reason="$4"
  jq -n --argjson exhausted "$exhausted" --argjson total "$total" \
    --argjson threshold "$threshold" --arg reason "$reason" \
    '{exhausted: $exhausted, total_dispatches: $total, budget_threshold: $threshold, reason: $reason}'
}

# emit_next_eligible - JSON for --next-eligible: reuses
# emit_verdict's "task"/"reason" fields as one family.
emit_next_eligible() {
  local task="$1" running="$2" reason="$3"
  jq -n --arg task "$task" --argjson in_progress "$running" \
    --arg reason "$reason" \
    '{task: $task, in_progress: $in_progress, reason: $reason}'
}

# emit_eligible_set - JSON for --eligible-set: the whole
# dispatchable set, plus the two counts its caller needs to
# tell "wait for a sibling" from "the wave drained".
emit_eligible_set() {
  local tasks="$1" running="$2" exhausted="$3" reason="$4"
  jq -n --argjson tasks "$tasks" --argjson in_progress "$running" \
    --argjson exhausted "$exhausted" --arg reason "$reason" \
    '{tasks: $tasks, in_progress: $in_progress, exhausted: $exhausted, reason: $reason}'
}

# in_progress_count - how many tasks are dispatched but not
# yet reported. The script owns this count rather than
# leaving the caller to jq it, so the orchestrator stays the
# recorder of raw facts and never becomes a second judge.
in_progress_count() {
  jq '[.tasks[] | select(.status == "in_progress")] | length' "$1"
}

fail() {
  echo "error: $1" >&2
  exit 1
}

# compute_budget_vars - sets task_count, total_dispatches,
# budget_threshold from BATCH_CAP_MULT/GATE_FIX_ALLOWANCE.
# Shared by the no-flag budget backstop below and --budget,
# so both read one formula instead of two that can drift.
compute_budget_vars() {
  local sf="$1" attempts_n gate_n
  task_count=$(jq '.tasks | length' "$sf")
  attempts_n=$(jq '.attempts | length' "$sf")
  gate_n=$(jq '.gate_dispatches // 0' "$sf")
  total_dispatches=$((attempts_n + gate_n))
  budget_threshold=$((BATCH_CAP_MULT * task_count + GATE_FIX_ALLOWANCE))
}

# eligible_tasks_json - DAG-eligible, non-terminal tasks,
# lowest id first. Shared by the "pass" branch below and by
# --next-eligible, so the eligibility rule is authored once.
#
# exclude_id: the "pass" branch's own current task, whose
# tasks[].status may still read "pending" here — see the
# design note above on tasks[].status lagging attempts[].
# It needs an explicit exclusion on top of the status check.
#
# Pass "" for no exclusion.
#
# --next-eligible has no "current task": any task it should
# exclude already carries a terminal status, set by its own
# caller before asking what runs next (failure-and-halt.md's
# §5.3) — the status check alone covers it there.
#
# "in_progress" is excluded as a third non-terminal status
# because it means already dispatched. That exclusion is the
# only thing stopping a parallel wave from dispatching one
# task into two worktrees.
eligible_tasks_json() {
  local sf="$1" exclude_id="$2"
  jq -c --arg cur "$exclude_id" '
    (reduce .tasks[] as $t ({}; .[$t.id] = $t.status)) as $status_map
    | [ .tasks[]
        | select($cur == "" or .id != $cur)
        | select(.status != "done" and .status != "blocked")
        | select(.status != "in_progress")
        | select(
            (.depends_on // []) as $deps
            | all($deps[]; . as $d
                | if ($status_map | has($d)) then $status_map[$d] == "done" else true end)
              )
      ]
    | sort_by(.id | tonumber)
  ' "$sf"
}

if [ "$mode" = "budget" ]; then
  compute_budget_vars "$state_file"
  if [ "$total_dispatches" -ge "$budget_threshold" ]; then
    exhausted=true
  else
    exhausted=false
  fi
  emit_budget "$exhausted" "$total_dispatches" "$budget_threshold" \
    "total dispatches ($total_dispatches) vs. the batch budget ($budget_threshold = ${BATCH_CAP_MULT}x${task_count} tasks + $GATE_FIX_ALLOWANCE gate allowance)"
  exit 0
fi

if [ "$mode" = "next-eligible" ]; then
  running=$(in_progress_count "$state_file")
  eligible_json=$(eligible_tasks_json "$state_file" "")
  eligible_count=$(printf '%s' "$eligible_json" | jq 'length')
  if [ "$eligible_count" -eq 0 ]; then
    emit_next_eligible "none" "$running" \
      "no pending task has every declared dependency satisfied (done, or absent from this unit's own tasks[]); a non-zero in_progress means wait for those siblings instead of halting"
  else
    next_task=$(printf '%s' "$eligible_json" | jq -r '.[0].id')
    emit_next_eligible "$next_task" "$running" \
      "lowest-id pending task whose dependencies are all done (or absent from this unit's own tasks[])"
  fi
  exit 0
fi

# --eligible-set is the only dispatch decider in a parallel
# wave, so it carries the batch budget the plain verdict
# path checks. Without it a wave of retries runs past the
# cap that exists to stop a runaway loop.
if [ "$mode" = "eligible-set" ]; then
  running=$(in_progress_count "$state_file")
  compute_budget_vars "$state_file"
  if [ "$total_dispatches" -ge "$budget_threshold" ]; then
    emit_eligible_set "[]" "$running" true \
      "total dispatches ($total_dispatches) reached the batch budget ($budget_threshold = ${BATCH_CAP_MULT}x${task_count} tasks + $GATE_FIX_ALLOWANCE gate allowance); dispatch nothing further and let any live sibling finish"
    exit 0
  fi
  set_json=$(eligible_tasks_json "$state_file" "" | jq -c '[.[].id]')
  emit_eligible_set "$set_json" "$running" false \
    "every task whose declared dependencies are all done and which is not already dispatched, lowest id first"
  exit 0
fi

compute_budget_vars "$state_file"

# Batch-wide budget backstop, checked before any per-task logic — see the
# design note above on why a single task alone can never trigger this first.
if [ "$total_dispatches" -ge "$budget_threshold" ]; then
  emit_verdict "halt-budget" "" \
    "total dispatches ($total_dispatches) reached the batch budget ($budget_threshold = ${BATCH_CAP_MULT}x${task_count} tasks + $GATE_FIX_ALLOWANCE gate allowance); halting the run here and waiting for the human"
  exit 0
fi

phase=$(jq -r '.phase' "$state_file")

if [ "$phase" != "tasks" ]; then
  fail "no verdict defined for phase '$phase' (this script only verdicts phase 'tasks')"
fi

attempts_count=$(jq '.attempts | length' "$state_file")
if [ "$attempts_count" -eq 0 ]; then
  fail "no attempts recorded yet; nothing to verdict for phase 'tasks'"
fi

current_task=$(jq -r '.attempts[-1].task' "$state_file")
last_result=$(jq -r '.attempts[-1].result' "$state_file")

case "$last_result" in
  pass)
    remaining_json=$(jq -c --arg cur "$current_task" \
      '[.tasks[] | select(.id != $cur) | select(.status != "done" and .status != "blocked")]' \
      "$state_file")
    remaining_count=$(printf '%s' "$remaining_json" | jq 'length')
    if [ "$remaining_count" -gt 0 ]; then
      # DAG-eligible: every declared depends_on id is either "done" in this
      # unit's own tasks[], or absent from it (an earlier PR's task, already
      # required done by the time this unit started — see the design note).
      eligible_json=$(eligible_tasks_json "$state_file" "$current_task")
      eligible_count=$(printf '%s' "$eligible_json" | jq 'length')
      if [ "$eligible_count" -eq 0 ]; then
        # No pending task is DAG-eligible right now, but that is not
        # necessarily a dead end: a non-zero in_progress means one or more
        # dispatched siblings just haven't reported yet, and dispatching
        # more or halting the run would be premature — only a true zero
        # in_progress means this really is a dependency deadlock.
        running=$(in_progress_count "$state_file")
        if [ "$running" -gt 0 ]; then
          emit_verdict "wait" "" \
            "task $current_task passed and $remaining_count task(s) remain, but $running sibling task(s) are still in_progress and haven't reported yet; dispatch nothing and wait for them before re-verdicting"
        else
          emit_verdict "halted" "" \
            "task $current_task passed and $remaining_count task(s) remain, but none have every declared dependency satisfied (likely blocked upstream); halting here for the human instead of dispatching an ineligible task"
        fi
      else
        next_task=$(printf '%s' "$eligible_json" | jq -r '.[0].id')
        emit_verdict "next-task" "$next_task" "task $current_task passed; dispatch next DAG-eligible pending task $next_task (lowest id among tasks whose dependencies are all done)"
      fi
    else
      blocked_count=$(jq '[.tasks[] | select(.status == "blocked")] | length' "$state_file")
      if [ "$blocked_count" -gt 0 ]; then
        emit_verdict "halted" "" \
          "task $current_task passed but $blocked_count task(s) ended blocked; halting here for the human instead of reaching the gates"
      else
        emit_verdict "gates" "" "task $current_task passed and every task in the batch is done; proceed to the test-presence gate"
      fi
    fi
    ;;
  blocked)
    emit_verdict "stuck" "$current_task" \
      "task $current_task reported blocked; only the human can clear it, so no retry is issued"
    ;;
  fail|timeout)
    task_attempts_json=$(jq -c --arg t "$current_task" '[.attempts[] | select(.task == $t)]' "$state_file")
    n_attempts=$(printf '%s' "$task_attempts_json" | jq 'length')

    signatures=()
    while IFS= read -r sig; do
      signatures+=("$(normalize_signature "$sig")")
    done < <(printf '%s' "$task_attempts_json" | jq -r '.[].signature')

    consecutive_identical=false
    if [ "$n_attempts" -ge "$STUCK_CONSECUTIVE" ]; then
      last_index=$((n_attempts - 1))
      first_of_window=$((n_attempts - STUCK_CONSECUTIVE))
      identical=true
      window_sig="${signatures[$first_of_window]}"
      for ((i = first_of_window; i <= last_index; i++)); do
        if [ "${signatures[$i]}" != "$window_sig" ]; then
          identical=false
          break
        fi
      done
      [ "$identical" = true ] && consecutive_identical=true
    fi

    if [ "$consecutive_identical" = true ]; then
      emit_verdict "stuck" "$current_task" \
        "task $current_task repeated the same failure signature $STUCK_CONSECUTIVE times in a row"
    elif [ "$n_attempts" -gt "$MAX_ATTEMPTS" ]; then
      emit_verdict "stuck" "$current_task" \
        "task $current_task exceeded the $MAX_ATTEMPTS-attempt cap without a consistent pass"
    else
      emit_verdict "retry" "$current_task" \
        "task $current_task failed attempt $n_attempts of $((MAX_ATTEMPTS + 1)); retry"
    fi
    ;;
  *)
    fail "unknown attempt result '$last_result' for task $current_task (expected pass, blocked, fail, or timeout)"
    ;;
esac
