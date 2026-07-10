#!/usr/bin/env bash
# claude-implement-stop-hook - Block a Stop while a /implement run is mid-batch
#                              in THIS session; allow it once the run finishes.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Rationale:
#   /implement's task loop (the implement skill) writes a per-session
#   state file at ~/.claude/implement-runs/<session_id>.json while it works
#   through a batch. A natural Stop before the batch reaches `presented` or
#   `halted` would leave the run abandoned mid-way with no re-prompt. This
#   hook reads that same state file and blocks the stop until the batch is
#   actually done — session-scoped, so it never affects any session without
#   an active /implement run.
#
# Session scoping — the entire mechanism is one existence check:
#   State file path is keyed by session_id. No file for this session id →
#   silent exit 0 immediately, before any other check. Every other session
#   on this machine (no /implement run, or a different session id) pays the
#   cost of one failed `[ -f ... ]` and nothing else.
#
# Escape hatch: deleting the state file instantly un-scopes the session (the
# next Stop attempt finds no file and allows the stop).
#
# Safeguards (all silent no-ops — never break Claude on a tooling/state gap):
#   - jq missing → exit 0.
#   - stop_hook_active=true → exit 0 (mirrors claude-density-stop-hook.sh's
#     guard: an always-on hook must never spin an infinite stop-block loop).
#   - No session_id, no state file for it, or state file is corrupt JSON
#     → exit 0.
#   - phase is anything other than tasks|gates|tails (e.g. presented,
#     halted, or an unrecognized value) → exit 0, allow the stop.
#
# This hook supersedes claude-tasklist-stop-hook.sh (deleted as dormant —
# it was never wired into settings.json). Its safeguard style (stdin parse,
# stop_hook_active guard, jq guard, fail-open) is the template this hook
# follows, adapted to read a state file instead of a tasks dir.
#
# NO env-var opt-out by design — a kill switch would let Claude silence its
# own accountability mechanism via a Bash call. To disable, remove this
# hook's chaining from claude-stop-orchestrator.sh (or delete the state file
# to un-scope this one session).

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && exit 0

state_file="$HOME/.claude/implement-runs/$session_id.json"
[ -f "$state_file" ] || exit 0

jq empty "$state_file" >/dev/null 2>&1 || exit 0

phase=$(jq -r '.phase // empty' "$state_file" 2>/dev/null || true)

case "$phase" in
  tasks|gates|tails)
    reason="Implement run (session $session_id) is still in phase '$phase' — the batch \
isn't done yet. Keep working the task loop (see the implement skill and \
implement-loop-state.sh) instead of stopping; the run finishes on its own once \
phase reaches presented or halted."
    jq -n --arg r "$reason" '{decision: "block", reason: $r}'
    ;;
esac

exit 0
