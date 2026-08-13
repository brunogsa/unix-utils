#!/usr/bin/env bash
# claude-implement-compact-reminder - After a compaction,
#     re-inject what THIS session's first mid-flight
#     /implement unit still owes.
#
#     That is the task loop while a task is unfinished, or
#     the §8 batch-end checklist once every task is done.
#
# Usage (Claude Code SessionStart hook, matcher: compact):
#   stdin:  hook event JSON ({ session_id, source, ... })
#   stdout: optional JSON
#           ({ hookSpecificOutput: { additionalContext } })
#
# Rationale:
#   /implement's task loop (the implement skill) writes ONE
#   state file PER UNIT, all created upfront.
#
#   A plain <task-ids> run gets
#   /tmp/implement_<session_id>.json; a PR-label run gets
#   /tmp/implement_<session_id>_pr<N>.json per PR.
#
#   A long batch passes through many compactions, each of
#   which can summarize the doc-resident §8 batch-end steps
#   (quality-gate tail, repo-green gate, push, PR, package)
#   out of working memory.
#
#   That is the "orchestrator forgot the steps" failure.
#
#   The batch-end [Reminder] task (implement skill §2.2) keeps
#   them in view each turn, and the Stop hook
#   (claude-implement-stop-hook.sh) blocks stopping while any
#   unit is mid-flight.
#
#   This hook is the third guard.
#
#   It fires at the compaction boundary itself — the one moment
#   working memory resets — and re-injects the remaining §8
#   checklist for the FIRST mid-flight unit so the batch never
#   ends at the last task's commit.
#
#   The checklist is RECONSTRUCTED from the chosen unit's state
#   file, not echoed from a stored string.
#
#   The PR step appears only when pr.wanted, the notification
#   line carries the run's real batch_base_sha, and the unit
#   is named by its pr_label when the run has one (a PR-label
#   run).
#
#   Within that §8 list the push step is NOT conditional —
#   every batch end pushes, whether or not a PR was wanted
#   — so it is always present once the list is due.
#
# Why task state, not phase, picks which directive is due:
#   Phase 'tasks' covers the WHOLE task loop, so keying the
#   §8 directive on phase alone handed the batch-end
#   procedure to a unit with five tasks still unfinished.
#
#   That misfires twice. It ends the batch early: §8 falls
#   due only once implement-loop-state.sh verdicts the unit
#   to 'gates', which it does only after every task has
#   left the loop.
#
#   And its 'git push' step targets a branch that a
#   concurrent session may have loaded with its own
#   unreviewed commits — the same harm the subagent guard
#   below exists to prevent, reached down a second path.
#
#   claude-implement-stop-hook.sh answers the neighbouring
#   question ("is any unit mid-flight?") off the same
#   files, and its block reason is the wording the
#   task-loop branch here reuses, so the two read alike.
#
# Session scoping — identical to claude-implement-stop-hook.sh:
#   State file paths are keyed by session_id. No file matching
#   this session id → silent exit 0.
#
#   A compaction keeps the same session_id, so the files the
#   run created are the ones this hook finds.
#
# Why this hook skips a subagent's compaction:
#   A subagent inherits its parent's session_id,
#   so the state-file glob below can't tell it
#   apart from the orchestrator owning the batch.
#
#   Observed twice: a subagent absorbed this §8
#   directive -- including its 'git push' step --
#   into its own compaction summary, risking a push
#   of another session's unreviewed commits.
#
#   agent_id (falling back to agent_type) scopes
#   the reminder to the owning session only. Same
#   precedent as claude-explore-mandate-hook.sh and
#   claude-stopfailure-resume.sh.
#
# Safeguards (all silent no-ops — never break Claude on a
# tooling/state gap):
# - jq missing → exit 0.
# - No session_id, or no state files match it → exit 0.
#
# - agent_id or agent_type non-empty (a subagent's
#   compaction) → exit 0.
#
# - A state file that is corrupt JSON is skipped
#   (fail-open per-file).
#
# - No unit's phase is tasks|gates|tails (e.g. all
#   presented/halted/blocked) → exit 0: nothing
#   mid-flight to re-inject.
#

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && exit 0

# Only the session that OWNS the state file may be reminded of
# §8 -- see the header.
#
# A subagent shares its parent's session_id, so this is the one
# field that separates the orchestrator from the agents it
# spawned.
agent=$(printf '%s' "$input" | jq -r '.agent_id // .agent_type // empty' 2>/dev/null || true)
[ -n "$agent" ] && exit 0

shopt -s nullglob
state_files=(/tmp/implement_"$session_id"*.json)
shopt -u nullglob
[ "${#state_files[@]}" -eq 0 ] && exit 0

chosen_file=""
phase=""

for f in "${state_files[@]}"; do
  # corrupt JSON: skip, fail-open
  jq empty "$f" >/dev/null 2>&1 || continue

  p=$(jq -r '.phase // empty' "$f" 2>/dev/null || true)
  case "$p" in
    tasks|gates|tails)
      chosen_file="$f"
      phase="$p"
      break
      ;;
  esac
done

# nothing mid-flight — nothing to remind
[ -z "$chosen_file" ] && exit 0

# Count other units still pending (not yet presented), for the
# "remaining" note.
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

# The PR step is conditional: only a run that opted into a PR
# writes one.
# Its "create only" wording matters — the pr-creator agent runs
# the create-pr skill, which pushes by default otherwise.
pr_step=""
[ "$pr_wanted" = "true" ] && pr_step=" → open the draft PR via the pr-creator agent (create only; step 3 already pushed)"

# Fall back to a literal placeholder if the sha somehow wasn't
# recorded.
sha_display="${base_sha:-<BATCH_BASE_SHA>}"

remaining_line=""
[ "$pending_after" -gt 0 ] && remaining_line="$pending_after more unit(s) remain after this one."

# Which directive is due — see the header. "Unfinished" is
# every task the loop has not recorded as done, so a
# blocked or unreadable status lands in the task-loop
# branch, which withholds the push instead of guessing.
#
# A unit carrying no tasks[] at all counts zero unfinished
# and takes the §8 branch: that is the honest answer at
# phase gates|tails, where the loop has already drained.
unfinished_ids=$(jq -r '[.tasks[]? | select(.status != "done") | .id] | join(", ")' \
  "$chosen_file" 2>/dev/null || true)
unfinished_count=$(jq '[.tasks[]? | select(.status != "done")] | length' \
  "$chosen_file" 2>/dev/null || true)

if [ -n "$unfinished_ids" ]; then

read -r -d '' DIRECTIVE <<EOF || true
A /implement batch for '$slug' has $unit_desc still in phase '$phase', with $unfinished_count task(s) not yet done: $unfinished_ids. The batch isn't done yet, and this compaction may have dropped that from working memory.

Keep working the task loop (see the implement skill and implement-loop-state.sh) instead of winding the batch down: ask implement-loop-state.sh for the unit's next verdict and dispatch from there. Do NOT start the batch-end procedure — it falls due only when that verdict moves this unit to phase 'gates', which cannot happen while a task is still unfinished.
$remaining_line
EOF

else

read -r -d '' DIRECTIVE <<EOF || true
A /implement batch for '$slug' has $unit_desc mid-flight (state phase: '$phase'). This compaction may have dropped the §8 batch-end steps from working memory — do NOT let the batch end at the last task's commit.

Resume the §8 batch-end procedure (implement skill §8, detail in references/batch-end-review.md — re-read it, do not work from this summary). Remaining steps, in order:
§8.1 quality-gate tail (only when quality_gate.wanted; pass --auto-solve when quality_gate.auto_solve is true, --report-only when it is false, never neither) → §8.2 repo-green gate: full suite + full lint, fix-loop until green (only when repo_green_gate.wanted) → §8.3 push the branch with 'git push -u origin HEAD' (ALWAYS, no toggle) → record it as the Branch: clause on the plan's PR line$pr_step → print the batch-end package, closing with the review notification (review starts at $sha_display).
$remaining_line

Verify the batch-end [Reminder] tasks are still in your TaskList; if this compaction dropped them, re-seed the four from §2.2. The run is done only when phase reaches 'presented'; a 'halted' unit is waiting on the human and won't resume on its own.
EOF

fi

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
