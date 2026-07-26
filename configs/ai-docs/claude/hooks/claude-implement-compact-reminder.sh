#!/usr/bin/env bash
# claude-implement-compact-reminder - After a compaction, re-inject the §9
#     batch-end checklist for THIS session's first mid-flight /implement unit.
#
# Usage (Claude Code SessionStart hook, matcher: compact):
#   stdin:  hook event JSON ({ session_id, source, ... })
#   stdout: optional JSON ({ hookSpecificOutput: { additionalContext } })
#
# Rationale:
#   /implement's task loop (the implement skill) writes ONE state file PER
#   UNIT, all created upfront: /tmp/implement_<session_id>.json for a plain
#   <task-ids> run, or /tmp/implement_<session_id>_pr<N>.json per PR on a
#   PR-label run. A long batch passes through many compactions, each of
#   which can summarize the doc-resident §9 finalize steps (gate, tails,
#   triage, package, diffview pane, PR) out of working memory — the
#   "orchestrator forgot the steps" failure. The batch-end [Reminder] task
#   (implement skill §2.2) keeps them in view each turn, and the Stop hook
#   (claude-implement-stop-hook.sh) blocks stopping while any unit is
#   mid-flight. This hook is the third guard: it fires at the compaction
#   boundary itself — the one moment working memory resets — and
#   re-injects the remaining §9 checklist for the FIRST mid-flight unit so
#   the batch never ends at the last task's commit.
#
#   The checklist is RECONSTRUCTED from the chosen unit's state file, not
#   echoed from a stored string: the PR step appears only when pr.wanted,
#   the diffview command carries the run's real batch_base_sha, and the
#   unit is named by its pr_label when the run has one (a PR-label run).
#
# Session scoping — identical to claude-implement-stop-hook.sh:
#   State file paths are keyed by session_id. No file matching this session
#   id → silent exit 0. A compaction keeps the same session_id, so the files
#   the run created are the ones this hook finds.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/state gap):
#   - jq missing → exit 0.
#   - No session_id, or no state files match it → exit 0.
#   - A state file that is corrupt JSON is skipped (fail-open per-file).
#   - No unit's phase is tasks|gates|tails (e.g. all presented/halted/
#     blocked) → exit 0: nothing mid-flight to re-inject.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && exit 0

shopt -s nullglob
state_files=(/tmp/implement_"$session_id"*.json)
shopt -u nullglob
[ "${#state_files[@]}" -eq 0 ] && exit 0

chosen_file=""
phase=""

for f in "${state_files[@]}"; do
  jq empty "$f" >/dev/null 2>&1 || continue   # corrupt JSON: skip, fail-open

  p=$(jq -r '.phase // empty' "$f" 2>/dev/null || true)
  case "$p" in
    tasks|gates|tails)
      chosen_file="$f"
      phase="$p"
      break
      ;;
  esac
done

[ -z "$chosen_file" ] && exit 0   # nothing mid-flight — nothing to remind

# Count other units still pending (not yet presented), for the "remaining" note.
pending_after=0
for f in "${state_files[@]}"; do
  [ "$f" = "$chosen_file" ] && continue
  jq empty "$f" >/dev/null 2>&1 || continue
  p=$(jq -r '.phase // empty' "$f" 2>/dev/null || true)
  [ "$p" = "presented" ] || pending_after=$((pending_after + 1))
done

slug=$(jq -r '.slug // "unknown"' "$chosen_file" 2>/dev/null || true)
base_sha=$(jq -r '.batch_base_sha // ""' "$chosen_file" 2>/dev/null || true)
pr_wanted=$(jq -r '.pr.wanted // false' "$chosen_file" 2>/dev/null || true)
pr_label=$(jq -r '.pr_label // empty' "$chosen_file" 2>/dev/null || true)

unit_desc="the plain run"
[ -n "$pr_label" ] && unit_desc="PR '$pr_label'"

# The PR step is conditional: only a run that opted into a PR writes one.
pr_step=""
[ "$pr_wanted" = "true" ] && pr_step=" → write the PR via the create-pr skill"

# Fall back to a literal placeholder if the sha somehow wasn't recorded.
sha_display="${base_sha:-<BATCH_BASE_SHA>}"

remaining_line=""
[ "$pending_after" -gt 0 ] && remaining_line="$pending_after more unit(s) remain after this one."

read -r -d '' DIRECTIVE <<EOF || true
A /implement batch for '$slug' has $unit_desc mid-flight (state phase: '$phase'). This compaction may have dropped the §9 batch-end steps from working memory — do NOT let the batch end at the last task's commit.

Resume the §9 finalize procedure (implement skill §9). Remaining steps, in order:
repo-green gate → refactor∥auto-review tails (parallel) → triage the two reports → print the batch-end package → open the diff for review: nvim -c 'DiffviewOpen $sha_display' in a side tmux pane via the open-in-tmux skill$pr_step.
$remaining_line

Verify the batch-end [Reminder] task is still in your TaskList; if this compaction dropped it, re-create it with the step checklist in its SUBJECT (§2.1). The run is done only when phase reaches 'presented'; a 'halted' unit is waiting on the human and won't resume on its own.
EOF

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
