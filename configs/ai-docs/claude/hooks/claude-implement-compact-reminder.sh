#!/usr/bin/env bash
# claude-implement-compact-reminder - After a compaction, re-inject the §8
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
#   which can summarize the doc-resident §8 batch-end steps (quality-gate
#   tail, repo-green gate, push, PR, package) out of working memory — the
#   "orchestrator forgot the steps" failure. The batch-end [Reminder] task
#   (implement skill §2.2) keeps them in view each turn, and the Stop hook
#   (claude-implement-stop-hook.sh) blocks stopping while any unit is
#   mid-flight. This hook is the third guard: it fires at the compaction
#   boundary itself — the one moment working memory resets — and
#   re-injects the remaining §8 checklist for the FIRST mid-flight unit so
#   the batch never ends at the last task's commit.
#
#   The checklist is RECONSTRUCTED from the chosen unit's state file, not
#   echoed from a stored string: the PR step appears only when pr.wanted,
#   the notification line carries the run's real batch_base_sha, and the
#   unit is named by its pr_label when the run has one (a PR-label run).
#
#   The push step is NOT conditional — every batch end pushes, whether or
#   not a PR was wanted, so it is always in the re-injected list.
#
# Session scoping — identical to claude-implement-stop-hook.sh:
#   State file paths are keyed by session_id. No file matching this session
#   id → silent exit 0. A compaction keeps the same session_id, so the files
#   the run created are the ones this hook finds.
#
# Why a subagent's compaction is skipped (agent_id/agent_type guard):
#   session_id alone CANNOT tell the orchestrator apart from its subagents —
#   a subagent inherits the parent's session_id, so the glob below matches the
#   ORCHESTRATOR's state file during a SUBAGENT's compaction. Observed twice on
#   disk: a tdd-coder (agent a99fe40a2c619d271, session f02f2530) and a
#   general-purpose agent (a1d3da5f0f1c345be, session aa2eba71) each absorbed
#   this directive into their own compaction summary and read it as their own
#   mandate.
#
#   That is a real hazard, not just noise. This text orders a
#   'git push -u origin HEAD'. A task subagent is scoped to one task's commit
#   (see agents/tdd-coder.md) and cannot know what else the worktree holds —
#   a worktree shared with a concurrent session would have its unreviewed
#   commits pushed to the remote by an obedient subagent. Both observed
#   subagents happened to refuse, but relying on a subagent to talk itself out
#   of a system-reminder is not a guard; the state must not reach it.
#
#   So the discriminator is ownership of the state file, and agent_id (falling
#   back to agent_type) is what expresses it: non-empty means this compaction
#   belongs to a subagent, not to the session that created the file. Same
#   precedent as claude-tmux-compact-bump.py — which routes the very same
#   SessionStart:compact event — plus claude-explore-mandate-hook.sh and
#   claude-stopfailure-resume.sh.
#
#   Do NOT relax this back to a session_id-only check: the orchestrator still
#   needs the reminder (a batch really did nearly end at the last task's
#   commit), so the fix is scoping it, never dropping it.
#
# Safeguards (all silent no-ops — never break Claude on a tooling/state gap):
#   - jq missing → exit 0.
#   - No session_id, or no state files match it → exit 0.
#   - agent_id or agent_type non-empty (a subagent's compaction) → exit 0.
#   - A state file that is corrupt JSON is skipped (fail-open per-file).
#   - No unit's phase is tasks|gates|tails (e.g. all presented/halted/
#     blocked) → exit 0: nothing mid-flight to re-inject.

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null || true)
[ -z "$session_id" ] && exit 0

# Only the session that OWNS the state file may be reminded of §8 -- see the
# header. A subagent shares its parent's session_id, so this is the one field
# that separates the orchestrator from the agents it spawned.
agent=$(printf '%s' "$input" | jq -r '.agent_id // .agent_type // empty' 2>/dev/null || true)
[ -n "$agent" ] && exit 0

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
# Its "create only" wording matters — the pr-creator agent runs the
# create-pr skill, which pushes by default otherwise.
pr_step=""
[ "$pr_wanted" = "true" ] && pr_step=" → open the draft PR via the pr-creator agent (create only; step 3 already pushed)"

# Fall back to a literal placeholder if the sha somehow wasn't recorded.
sha_display="${base_sha:-<BATCH_BASE_SHA>}"

remaining_line=""
[ "$pending_after" -gt 0 ] && remaining_line="$pending_after more unit(s) remain after this one."

read -r -d '' DIRECTIVE <<EOF || true
A /implement batch for '$slug' has $unit_desc mid-flight (state phase: '$phase'). This compaction may have dropped the §8 batch-end steps from working memory — do NOT let the batch end at the last task's commit.

Resume the §8 batch-end procedure (implement skill §8, detail in references/batch-end-review.md — re-read it, do not work from this summary). Remaining steps, in order:
§8.1 quality-gate tail with --auto-solve (only when quality_gate.wanted) → §8.2 repo-green gate: full suite + full lint, fix-loop until green (only when repo_green_gate.wanted) → §8.3 push the branch with 'git push -u origin HEAD' (ALWAYS, no toggle) → record it as the Branch: clause on the plan's PR line$pr_step → print the batch-end package, closing with the review notification (review starts at $sha_display).
$remaining_line

Verify the batch-end [Reminder] tasks are still in your TaskList; if this compaction dropped them, re-seed the four from §2.2. The run is done only when phase reaches 'presented'; a 'halted' unit is waiting on the human and won't resume on its own.
EOF

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
