#!/usr/bin/env bash
# claude-tasklist-stop-hook - Re-prompt Claude when the session's tasklist still has work.
#
# Usage (Claude Code Stop hook):
#   stdin: hook event JSON ({ session_id, stop_hook_active, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# Rationale:
#   When Claude finishes a turn but the TaskList still has pending or in_progress
#   tasks, we want it to continue rather than wait for the user to type "keep going".
#   The Stop hook fires after the agent's response; if work remains, this hook
#   blocks the stop and feeds back a reason that nudges the next turn.
#
# Safeguards:
#   - Honors `stop_hook_active=true` — if Claude is already in a stop-blocked loop,
#     this hook bows out so the loop can break naturally.
#   - jq missing → silent no-op (don't break Claude on tooling gaps).
#   - Session dir missing → silent no-op.
#
# NO env-var opt-out by design — a `CLAUDE_TASKLIST_HOOK=off` switch would let
# Claude silence its own accountability mechanism via a Bash call. To disable,
# edit settings.json and remove this hook from the Stop array.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)

[ "$stop_hook_active" = "true" ] && exit 0
[ -z "$session_id" ] && exit 0

tasks_dir="$HOME/.claude/tasks/$session_id"
[ -d "$tasks_dir" ] || exit 0

# Count pending + in_progress tasks. Iterate explicitly to avoid grep/pipe
# exit-code quirks under set -eo pipefail.
pending=0
for f in "$tasks_dir"/*.json; do
    [ -f "$f" ] || continue
    status=$(jq -r '.status // empty' "$f" 2>/dev/null || true)
    case "$status" in
        pending|in_progress) pending=$((pending + 1)) ;;
    esac
done

[ "$pending" -eq 0 ] && exit 0

jq -n --arg n "$pending" \
    '{decision: "block", reason: ("Tasklist still has " + $n + " pending/in_progress task(s). Run TaskList to see them and either complete the next one, or mark stale ones as deleted.")}'
