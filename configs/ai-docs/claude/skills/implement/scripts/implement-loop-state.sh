#!/usr/bin/env bash
# implement-loop-state.sh - pure verdict script for the /implement task loop.
#
# Usage:
#   implement-loop-state.sh <state-file>
#
# Reads a /implement run's JSON state file and prints one JSON verdict on stdout:
#   {"action": "retry|stuck|next-task|gates|halt-budget", "task": "<id or empty>", "reason": "..."}
#
# Examples:
#   implement-loop-state.sh ~/.claude/implement-runs/abc123.json
#   implement-loop-state.sh --help
#
# Pure: no writes, no clock reads, deterministic — the same state file always
# yields the same verdict. The orchestrator (main session AI) is the fallible
# recorder of raw facts (attempt outcomes, phase, report paths); this script is
# the infallible judge that turns those facts into one of five actions.
#
# Design:
#   - The "current task" is whichever task the LAST entry in `attempts[]`
#     belongs to — not `tasks[].status`, which the orchestrator may lag on.
#   - A task is "terminal" (no longer blocks the batch) once its `status` is
#     "done" or "blocked".
#   - Failure-signature comparison lowercases, drops any whitespace-delimited
#     token containing "/" (path-like), strips digits, then collapses
#     whitespace — so two failures differing only by a line number or a tmp
#     path count as the same signature.
#   - The batch-wide dispatch budget (BATCH_CAP_MULT * task count +
#     GATE_FIX_ALLOWANCE) is checked before any per-task logic: it is the
#     backstop for a runaway gate-fixing loop (gate_dispatches piling up),
#     since a single task alone can never exceed MAX_ATTEMPTS before the
#     per-task "stuck" verdict already caught it.
#   - The script only knows how to verdict phase "tasks" (retry/stuck/
#     next-task/gates). Any other phase is a caller misuse the script
#     fails loud on rather than guess a verdict for — after the task
#     loop, the gate and batch-end flow run linearly with no verdict call.
#
# Exit codes:
#   0 - verdict printed on stdout.
#   1 - usage error, missing file, invalid JSON, or a state this script has
#       no verdict for. Fail-loud by design: this is not the fail-open
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

Reads a /implement run's JSON state file and prints one JSON verdict:
  {"action": "retry|stuck|next-task|gates|halt-budget", "task": "...", "reason": "..."}

Examples:
  implement-loop-state.sh ~/.claude/implement-runs/abc123.json
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
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

fail() {
  echo "error: $1" >&2
  exit 1
}

task_count=$(jq '.tasks | length' "$state_file")
attempts_count=$(jq '.attempts | length' "$state_file")
gate_dispatches=$(jq '.gate_dispatches // 0' "$state_file")
total_dispatches=$((attempts_count + gate_dispatches))
budget_threshold=$((BATCH_CAP_MULT * task_count + GATE_FIX_ALLOWANCE))

# Batch-wide budget backstop, checked before any per-task logic — see the
# design note above on why a single task alone can never trigger this first.
if [ "$total_dispatches" -ge "$budget_threshold" ]; then
  emit_verdict "halt-budget" "" \
    "total dispatches ($total_dispatches) reached the batch budget ($budget_threshold = ${BATCH_CAP_MULT}x${task_count} tasks + $GATE_FIX_ALLOWANCE gate allowance)"
  exit 0
fi

phase=$(jq -r '.phase' "$state_file")

if [ "$phase" != "tasks" ]; then
  fail "no verdict defined for phase '$phase' (this script only verdicts phase 'tasks')"
fi

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
      next_task=$(printf '%s' "$remaining_json" | jq -r '.[0].id')
      emit_verdict "next-task" "$next_task" "task $current_task passed; dispatch next pending task $next_task"
    else
      emit_verdict "gates" "" "task $current_task passed and every other task is done or blocked; proceed to the test-presence gate"
    fi
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
    elif [ "$n_attempts" -ge "$MAX_ATTEMPTS" ]; then
      emit_verdict "stuck" "$current_task" \
        "task $current_task reached the $MAX_ATTEMPTS-attempt cap without a consistent pass"
    else
      emit_verdict "retry" "$current_task" \
        "task $current_task failed attempt $n_attempts of $MAX_ATTEMPTS; retry"
    fi
    ;;
  *)
    fail "unknown attempt result '$last_result' for task $current_task (expected pass, fail, or timeout)"
    ;;
esac
