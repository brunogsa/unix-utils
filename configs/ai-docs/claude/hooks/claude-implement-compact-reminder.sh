#!/usr/bin/env bash
# claude-implement-compact-reminder - After a compaction, re-inject the §9
#     batch-end checklist for THIS session's mid-flight /implement run.
#
# Usage (Claude Code SessionStart hook, matcher: compact):
#   stdin:  hook event JSON ({ session_id, source, ... })
#   stdout: optional JSON ({ hookSpecificOutput: { additionalContext } })
#
# Rationale:
#   A long /implement batch passes through many compactions. Each one can
#   summarize the doc-resident §9 finalize steps (gate, tails, triage,
#   package, diffview pane, PR) out of working memory — the "orchestrator
#   forgot the steps" failure. The batch-end [Reminder] task (implement skill §2.1) keeps
#   them in view each turn, and the Stop hook (claude-implement-stop-hook.sh)
#   blocks stopping before phase reaches 'presented'. This hook is the third
#   guard: it fires at the compaction boundary itself — the one moment
#   working memory resets — and re-injects the remaining §9 checklist so the
#   batch never ends at the last task's commit.
#
#   The checklist is RECONSTRUCTED from the state file, not echoed from a
#   stored string: the PR step appears only when pr.wanted, and the diffview
#   command carries the run's real batch_base_sha.
#
# Session scoping — identical to claude-implement-stop-hook.sh:
#   State file path is keyed by session_id. No file for this session id →
#   silent exit 0. A compaction keeps the same session_id, so the file the
#   run created is the one this hook finds. (A cross-session resume renames
#   nothing and is handled by the skill's §2.1 resume-guard, not here.)
#
# Safeguards (all silent no-ops — never break Claude on a tooling/state gap):
#   - jq missing → exit 0.
#   - No session_id, no state file for it, or corrupt JSON → exit 0.
#   - phase is anything other than tasks|gates|tails (e.g. presented, halted)
#     → exit 0: the batch is finished or halted, nothing to re-inject.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && exit 0

state_file="/tmp/implement_$session_id.json"
[ -f "$state_file" ] || exit 0

jq empty "$state_file" >/dev/null 2>&1 || exit 0

phase=$(jq -r '.phase // empty' "$state_file" 2>/dev/null || true)
case "$phase" in
  tasks|gates|tails) ;;   # mid-flight — fall through and re-inject
  *) exit 0 ;;            # presented|halted|unknown — nothing to remind
esac

slug=$(jq -r '.slug // "unknown"' "$state_file" 2>/dev/null || true)
base_sha=$(jq -r '.batch_base_sha // ""' "$state_file" 2>/dev/null || true)
pr_wanted=$(jq -r '.pr.wanted // false' "$state_file" 2>/dev/null || true)

# The PR step is conditional: only a run that opted into a PR writes one.
pr_step=""
[ "$pr_wanted" = "true" ] && pr_step=" → write the PR via the create-pr skill"

# Fall back to a literal placeholder if the sha somehow wasn't recorded.
sha_display="${base_sha:-<BATCH_BASE_SHA>}"

read -r -d '' DIRECTIVE <<EOF || true
A /implement batch for '$slug' is mid-flight (state phase: '$phase'). This compaction may have dropped the §9 batch-end steps from working memory — do NOT let the batch end at the last task's commit.

Resume the §9 finalize procedure (implement skill §9). Remaining steps, in order:
repo-green gate → refactor∥auto-review tails (parallel) → triage the two reports → print the batch-end package → open the diff for review: nvim -c 'DiffviewOpen $sha_display' in a side tmux pane via the open-in-tmux skill$pr_step.

Verify the batch-end [Reminder] task is still in your TaskList; if this compaction dropped it, re-create it with the step checklist in its SUBJECT (§2.1). The run is done only when phase reaches 'presented'.
EOF

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
