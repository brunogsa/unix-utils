#!/usr/bin/env bash
# claude-agent-contract-stop-hook - At review handoff, gate on agent-file
#                            contract violations THIS session just wrote.
#
# Usage (Claude Code Stop hook):
#   stdin:  hook event JSON ({ session_id, stop_hook_active, transcript_path, ... })
#   stdout: optional JSON ({ decision: "block", reason: "..." }) to keep Claude going
#
# One checker, one gate:
#   - check-agent-contract.sh  frontmatter (name matches filename, non-empty
#                              description, model present) plus the six-heading
#                              body contract, or the "## Shadows" carve-out.
#
# Rationale:
#   agent-standards tells the model to run this checker after editing an agent
#   file, but nothing enforced it — the script's only automated caller is the
#   performance-check audit, which runs long after the edit that broke the
#   contract. A rule kept alive only by the model remembering it is exactly the
#   [Harness] case CLAUDE.md says to wire into the harness instead.
#
#   Stop is the right event, and the cheaper one. PostToolUse would re-validate
#   the whole directory on every Edit/Write in every session — a tax on the
#   hottest tool pair to catch a rare defect — and no PostToolUse hook exists
#   today, so it is also a new registration rather than one more leg on the
#   orchestrator that already chains three change-gated checkers.
#
# Scope — "agent files THIS SESSION wrote", narrowed twice:
#   - Session filter: which files this session's own Edit/Write/NotebookEdit
#     tool calls touched (read from transcript_path), keeping only paths under
#     an agents/ directory. A session that never touched one exits before doing
#     any work, so the common case costs a single jq pass.
#   - Output filter: the checker validates a whole DIRECTORY, so it also reports
#     agent files this session never opened. Those are filtered out of the block.
#     Without this, one pre-existing broken agent file would block every stop in
#     every session until someone fixed a file they never touched — the same
#     churn the markdown gate's diff filter exists to prevent.
#
#   The directory is derived per touched file rather than hardcoded, so this
#   works on the global ~/.claude/agents, on the unix-utils repo source, and on
#   a project-local .claude/agents alike.
#
# Enforcement vs. loop-safety:
#   Honors stop_hook_active=true → bows out, so this can never spin an infinite
#   stop-block loop. Because the guard bails on the post-fix stop, the hook
#   cannot re-verify its own fix — so the block tells the main session to re-run
#   the checker itself. That is cheap and deterministic here (one script, exit
#   code is the whole answer), which is why this gate fixes inline rather than
#   delegating to a subagent the way the markdown gate does.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/context gap):
#   - jq missing, or the checker missing/non-executable → exit 0.
#   - transcript_path missing/unreadable, or no Edit/Write/NotebookEdit calls
#     in it → exit 0 (fail open to "no block"; a missing session signal must
#     never widen the scope to every agent file on disk).
#   - No touched file under an agents/ directory → exit 0.
#   - Checker clean, or violations only in files this session never touched → exit 0.
#
# NO env-var opt-out by design — a kill switch would let Claude silence its own
# contract gate via a Bash call. To disable, remove this leg from the orchestrator.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

stop_hook_active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)
[ "$stop_hook_active" = "true" ] && exit 0

CHECKER="$HOME/.claude/skills/agent-standards/scripts/check-agent-contract.sh"
[ -x "$CHECKER" ] || exit 0

transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -n "$transcript_path" ] && [ -f "$transcript_path" ] || exit 0

# Absolute paths this session's own write tools touched. Same extraction as the
# markdown gate — one jq pass over the transcript, deduped.
session_files=$(jq -r '
    select(.message.content != null) | .message.content[]?
    | select(.type == "tool_use")
    | select(.name == "Edit" or .name == "Write" or .name == "NotebookEdit")
    | .input.file_path // empty
  ' "$transcript_path" 2>/dev/null | sort -u || true)
[ -n "$session_files" ] || exit 0

# Keep only agent files: a .md sitting directly inside a directory named
# "agents". The trailing-slash match anchors on the directory NAME, so a file
# merely mentioning "agents" in its own name never qualifies.
agent_files=$(printf '%s\n' "$session_files" | grep -E '/agents/[^/]+\.md$' || true)
[ -n "$agent_files" ] || exit 0

# One checker run per distinct agents directory — a session may touch the repo
# source and a project-local copy in the same turn.
agent_dirs=$(printf '%s\n' "$agent_files" | sed 's|/[^/]*$||' | sort -u)

# The checker prints "== <base>.md" headers with indented "  - <reason>" lines
# beneath each. Re-emit those rows as "<dir>/<base>.md: <reason>" so the block
# message points at a path the reader can open, and so the session filter below
# can match on the full path rather than a bare basename.
violations=""
while IFS= read -r d; do
  [ -n "$d" ] || continue
  [ -d "$d" ] || continue
  report=$("$CHECKER" "$d" 2>/dev/null || true)
  [ -n "$report" ] || continue
  violations+=$(printf '%s\n' "$report" | awk -v dir="$d" '
    /^== / { file = dir "/" substr($0, 4); next }
    /^  - / { if (file != "") print file ": " substr($0, 5) }
  ')$'\n'
done <<< "$agent_dirs"

violations=$(printf '%s' "$violations" | sed '/^$/d')
[ -z "$violations" ] && exit 0

# Drop violations in agent files this session never opened — another session's
# WIP, or drift that predates this turn. Blocking on those would make the gate
# unclearable by the session that hit it.
violations=$(printf '%s\n' "$violations" | while IFS= read -r v; do
  [ -n "$v" ] || continue
  printf '%s\n' "$agent_files" | grep -qxF "${v%%: *}" && printf '%s\n' "$v"
# A final non-match leaves grep's 1 as the loop's status, which set -e would
# turn into a non-zero hook exit — an "error" reading of the ordinary
# nothing-to-block case.
done || true)
[ -z "$violations" ] && exit 0

# Reasons are included rather than elided (the markdown gate omits its rule
# names) because nothing downstream re-derives them: there is no fixer subagent
# here, so the main session would have to re-run the checker just to learn what
# broke. They are short and bounded — one line per missing/duplicate/empty
# heading — so naming them costs less than the extra round-trip.
#
# Grouped one path per file, reasons joined, because a file missing all six
# headings emits six rows: repeating its absolute path on each would inject the
# same long string six times into the main context on every block. Split on the
# FIRST ": " only — the reasons contain their own (`missing required heading:
# ## Inputs`), so a field-separator split would truncate them.
list=$(printf '%s\n' "$violations" | awk '
  {
    i = index($0, ": ");
    if (i == 0) next;
    f = substr($0, 1, i - 1);
    msg = substr($0, i + 2);
    if (!(f in reasons)) { order[++n] = f; reasons[f] = msg }
    else reasons[f] = reasons[f] ", " msg;
  }
  END {
    for (k = 1; k <= n; k++)
      printf "%s%s (%s)", (k > 1 ? "; " : ""), order[k], reasons[order[k]];
  }
')

reason="Agent files you edited this session are off the agent-standards contract — ${list}. \
Fix them, then confirm with: check-agent-contract.sh <agents-directory> (exit 0 = clean)."

jq -n --arg r "$reason" '{decision: "block", reason: $r}'
