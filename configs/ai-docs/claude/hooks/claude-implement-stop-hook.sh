#!/usr/bin/env bash
# claude-implement-stop-hook - Block a Stop while ANY unit of a /implement run
#                              is mid-batch in THIS session; allow the stop
#                              once every unit has left tasks|gates|tails.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Rationale:
#   /implement's task loop (the implement skill) writes ONE state file PER
#   UNIT, all created upfront: /tmp/implement_<session_id>.json for a plain
#   <task-ids> run, or /tmp/implement_<session_id>_pr<N>.json per PR on a
#   PR-label run. A natural Stop before every unit reaches a stopping phase
#   would leave the batch abandoned mid-way with no re-prompt. This hook
#   globs every state file for the session and blocks the stop while ANY
#   unit's phase is still tasks|gates|tails — session-scoped, so it never
#   affects any session without an active /implement run.
#
# Session scoping — the entire mechanism is one existence check:
#   State file paths are keyed by session_id. No file matching this session
#   id → silent exit 0 immediately, before any other check. Every other
#   session on this machine (no /implement run, or a different session id)
#   pays the cost of one failed glob and nothing else.
#
# Escape hatch: deleting the session's state files instantly un-scopes the
# session (the next Stop attempt finds no files and allows the stop).
#
# Safeguards (all silent no-ops — never break Claude on a tooling/state gap):
#   - jq missing → exit 0.
#   - stop_hook_active=true → exit 0 (mirrors claude-markdown-standards-stop-hook.sh's
#     guard: an always-on hook must never spin an infinite stop-block loop).
#   - No session_id, or no state files match it → exit 0.
#   - A state file that is corrupt JSON is skipped (fail-open per-file), not
#     treated as blocking.
#   - A unit's phase other than tasks|gates|tails — including presented,
#     halted, and blocked — releases that unit; the stop is allowed once no
#     unit is left mid-flight. halted and blocked deliberately release the
#     stop: a run that stopped for the human (a failed gate, a triage
#     decision) must be allowed to stop, otherwise this hook would spin
#     against a wall only the human can clear.
#
# This hook supersedes claude-tasklist-stop-hook.sh (deleted as dormant —
# it was never wired into settings.json). Its safeguard style (stdin parse,
# stop_hook_active guard, jq guard, fail-open) is the template this hook
# follows, adapted to read per-unit state files instead of a tasks dir.
#
# NO env-var opt-out by design — a kill switch would let Claude silence its
# own accountability mechanism via a Bash call. To disable, remove this
# hook's chaining from claude-stop-orchestrator.sh (or delete the session's
# state files to un-scope this one session).

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && exit 0

shopt -s nullglob
state_files=(/tmp/implement_"$session_id"*.json)
shopt -u nullglob
[ "${#state_files[@]}" -eq 0 ] && exit 0

mid_flight_count=0
first_unit_desc=""
first_phase=""

for f in "${state_files[@]}"; do
  jq empty "$f" >/dev/null 2>&1 || continue   # corrupt JSON: skip, fail-open

  phase=$(jq -r '.phase // empty' "$f" 2>/dev/null || true)
  case "$phase" in
    tasks|gates|tails) ;;
    *) continue ;;
  esac

  mid_flight_count=$((mid_flight_count + 1))
  if [ -z "$first_phase" ]; then
    pr_label=$(jq -r '.pr_label // empty' "$f" 2>/dev/null || true)
    if [ -n "$pr_label" ]; then
      first_unit_desc="PR '$pr_label'"
    else
      first_unit_desc="the plain run"
    fi
    first_phase="$phase"
  fi
done

[ "$mid_flight_count" -eq 0 ] && exit 0

remaining=$((mid_flight_count - 1))
remaining_note=""
[ "$remaining" -gt 0 ] && remaining_note=" ($remaining more unit(s) still mid-flight)"

reason="Implement run (session $session_id): $first_unit_desc is still in phase \
'$first_phase'$remaining_note — the batch isn't done yet. Keep working the task \
loop (see the implement skill and implement-loop-state.sh) instead of stopping; \
each unit finishes on its own once its phase reaches presented, or halts for the \
human (halted/blocked)."
jq -n --arg r "$reason" '{decision: "block", reason: $r}'

exit 0
