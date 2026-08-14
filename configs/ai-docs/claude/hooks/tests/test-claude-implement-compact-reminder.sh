#!/usr/bin/env bash
# test-claude-implement-compact-reminder.sh - plain-bash
# test file for claude-implement-compact-reminder.sh's
# scoping of the §8 batch-end directive: it must reach the
# orchestrator that owns the state file, and only once that
# unit's task loop has drained.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency by design — a handful of small
# scripts don't justify a new cross-platform test-runner
# dependency in install.sh.
#
# Why the subagent cases carry the weight here:
#   A subagent inherits its parent's session_id, and the
#   hook globs its state files by session_id, so before
#   the agent_id/agent_type guard a SUBAGENT's compaction
#   was handed the ORCHESTRATOR's batch-end directive —
#   including its 'git push -u origin HEAD' step. In a
#   worktree shared with a concurrent session, an obedient
#   subagent would push that other session's unreviewed
#   commits. Observed on two subagents before the fix.
#
#   The orchestrator case is here for the opposite reason:
#   it pins that the scoping did not simply silence the
#   reminder, which a real batch needs.
#
# Why the task-state cases carry the rest of the weight:
#   Phase 'tasks' covers the whole task loop, so keying the
#   directive on phase alone told an orchestrator with five
#   tasks left to run the batch-end procedure and push.
#
#   So each task-state case asserts both halves: the right
#   directive appears, and the wrong one's push, gates and
#   package steps are absent. Asserting only the first
#   would pass a hook that emitted both.
#
# Fixtures live at /tmp/implement_<id>.json because the
# hook hardcodes that directory (the real /implement run
# writes there, and TMPDIR on macOS points elsewhere).
# Every fixture id is namespaced by this suite's name and
# PID, so a run can never read or clobber a live run's
# state file.
#
# Fixture ids must also stay non-overlapping: the hook
# globs '<session_id>*.json', so an id that is a prefix of
# another test's id would pull in that test's state file.
#
# Usage:
#   bash test-claude-implement-compact-reminder.sh

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SCRIPT="$script_dir/claude-implement-compact-reminder.sh"

fixture_prefix="test-compact-reminder-$$"
trap 'rm -f "/tmp/implement_${fixture_prefix}"*.json' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# says - "yes"/"no" for whether the last emitted directive
# contains the given text, so assert_eq reports a readable
# value instead of a wall of injected prose on failure.
says() {
  case "$LAST_DIRECTIVE" in
    *"$1"*) printf 'yes' ;;
    *)      printf 'no' ;;
  esac
}

# write_drained_task_loop_state - lays down one state file
# for the given fixture id, in the shape the implement
# skill writes for a run whose every task has landed.
# Echoes the session id, for inlining into a payload.
#
# This is the state the §8 batch-end directive is FOR:
# phase 'tasks' keeps the unit in scope for the hook, and
# an all-done tasks[] is what leaves the batch with nothing
# but its batch-end steps to run.
#
# slug and pr.wanted are read straight into that directive.
write_drained_task_loop_state() {
  local session_id="${fixture_prefix}-$1"
  cat > "/tmp/implement_${session_id}.json" <<JSON
{
  "slug": "shared-worktree-guard",
  "phase": "tasks",
  "batch_base_sha": "3f9a1c4d5e6b7a8c9d0e1f2a3b4c5d6e7f8a9b0c",
  "tasks": [
    { "id": "7", "status": "done" },
    { "id": "8", "status": "done" }
  ],
  "pr": { "wanted": true },
  "quality_gate": { "wanted": true },
  "repo_green_gate": { "wanted": true }
}
JSON
  printf '%s' "$session_id"
}

# write_unfinished_task_loop_state - the same unit one step
# earlier: task 7 has landed, tasks 31 and 42 have not.
# Takes task 42's status from the caller so a test can pick
# which non-done status it is proving.
#
# Two-digit ids keep the assertion honest: the rendered
# list '31, 42' cannot occur by chance inside the
# batch_base_sha above, where a bare '3' would.
write_unfinished_task_loop_state() {
  local session_id="${fixture_prefix}-$1"
  cat > "/tmp/implement_${session_id}.json" <<JSON
{
  "slug": "shared-worktree-guard",
  "phase": "tasks",
  "batch_base_sha": "3f9a1c4d5e6b7a8c9d0e1f2a3b4c5d6e7f8a9b0c",
  "tasks": [
    { "id": "7", "status": "done" },
    { "id": "31", "status": "in_progress" },
    { "id": "42", "status": "$2" }
  ],
  "pr": { "wanted": true },
  "quality_gate": { "wanted": true },
  "repo_green_gate": { "wanted": true }
}
JSON
  printf '%s' "$session_id"
}

# run_hook - pipes the given stdin JSON into the hook under
# test. Sets HOOK_EXIT, plus LAST_DIRECTIVE: the §8 text
# the hook would add to the compacting session's context,
# empty when it stayed silent.
#
# Reading additionalContext back out of the JSON envelope,
# rather than grepping raw stdout, is what proves the
# payload would actually be injected.
run_hook() {
  local stdout
  stdout=$(printf '%s' "$1" | bash "$HOOK_SCRIPT" 2>/dev/null)
  HOOK_EXIT=$?
  LAST_DIRECTIVE=$(printf '%s' "$stdout" \
    | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null)
}

# --- the orchestrator still gets its reminder ---

it_should_remind_the_session_that_owns_the_state_file_to_finish_the_batch_end_steps() {
  local session_id
  session_id=$(write_drained_task_loop_state "owner")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should exit 0 for the session that owns the state file" "0" "$HOOK_EXIT"
  assert_eq "should tell the owning session not to end the batch at the last task's commit" \
    "yes" "$(says "do NOT let the batch end at the last task")"
  assert_eq "should name the owning run's slug so the reminder is about its own batch" \
    "yes" "$(says "shared-worktree-guard")"
}

# --- a subagent must never receive it ---

it_should_stay_silent_when_a_subagent_of_the_owning_session_compacts() {
  local session_id
  session_id=$(write_drained_task_loop_state "subagent-by-id")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\",\"agent_id\":\"a99fe40a2c619d271\"}"

  assert_eq "should exit 0 when a subagent compacts" "0" "$HOOK_EXIT"
  assert_eq "should hand a compacting subagent no batch-end directive, since it shares its parent's session id but not the parent's authority to push" \
    "" "$LAST_DIRECTIVE"
}

it_should_stay_silent_when_a_compacting_subagent_is_identified_only_by_agent_type() {
  local session_id
  session_id=$(write_drained_task_loop_state "subagent-by-type")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\",\"agent_type\":\"tdd-coder\"}"

  assert_eq "should hand a compacting subagent no batch-end directive when it carries agent_type but no agent_id" \
    "" "$LAST_DIRECTIVE"
}

# --- the batch-end directive waits for the task loop ---

it_should_keep_the_owner_in_the_task_loop_while_a_task_is_unfinished() {
  local session_id
  session_id=$(write_unfinished_task_loop_state "loop-running" "pending")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should exit 0 while the owning unit still has tasks to run" "0" "$HOOK_EXIT"
  assert_eq "should send the owner back to the task loop while a task is unfinished" \
    "yes" "$(says "Keep working the task loop")"
  assert_eq "should name every task the loop has not finished, so the owner can resume without re-reading the state file" \
    "yes" "$(says "not yet done: 31, 42")"
  assert_eq "should not order a push while tasks remain, the step that would send a concurrent session's unreviewed commits to the remote" \
    "no" "$(says "git push")"
  assert_eq "should not cite the batch-end section while tasks remain, since a cited step gets run" \
    "no" "$(says "§8")"
  assert_eq "should not order the repo-green gate while tasks remain" \
    "no" "$(says "repo-green gate")"
  assert_eq "should not order the plan's Branch: clause while tasks remain" \
    "no" "$(says "Branch:")"
  assert_eq "should not order the batch-end package to be printed while tasks remain" \
    "no" "$(says "batch-end package")"
}

it_should_keep_the_owner_in_the_task_loop_when_the_only_unfinished_task_is_blocked() {
  local session_id
  session_id=$(write_unfinished_task_loop_state "loop-blocked" "blocked")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should treat a blocked task as unfinished, since the loop reaches its gates only once every task is done" \
    "yes" "$(says "Keep working the task loop")"
  assert_eq "should withhold the push while a task is blocked rather than guessing the batch is over" \
    "no" "$(says "git push")"
}

it_should_hand_over_the_batch_end_directive_once_every_task_is_done() {
  local session_id
  session_id=$(write_drained_task_loop_state "loop-drained")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should resume the batch-end procedure once the task loop has drained" \
    "yes" "$(says "Resume the §8 batch-end procedure")"
  assert_eq "should still order the push once the task loop has drained, the step a batch really did nearly drop" \
    "yes" "$(says "git push -u origin HEAD")"
}

# --- corner cases ---

it_should_hand_over_the_batch_end_directive_when_the_unit_records_no_tasks() {
  local session_id="${fixture_prefix}-taskless"
  printf '%s' '{"slug":"post-loop","phase":"gates","pr":{"wanted":false}}' \
    > "/tmp/implement_${session_id}.json"
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should read a unit with no tasks[] as having none unfinished, which is what phase gates means" \
    "yes" "$(says "git push -u origin HEAD")"
}

it_should_still_remind_the_owner_when_the_payload_carries_an_empty_agent_id() {
  local session_id
  session_id=$(write_drained_task_loop_state "blank-agent-field")
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\",\"agent_id\":\"\"}"

  assert_eq "should treat an empty agent_id as the owning session rather than over-scoping the reminder away" \
    "yes" "$(says "do NOT let the batch end at the last task")"
}

it_should_stay_silent_when_the_owning_session_has_no_state_file() {
  run_hook "{\"session_id\":\"${fixture_prefix}-never-started\",\"source\":\"compact\"}"

  assert_eq "should exit 0 when no run is in flight for this session" "0" "$HOOK_EXIT"
  assert_eq "should emit no directive when this session never started a batch" \
    "" "$LAST_DIRECTIVE"
}

it_should_stay_silent_when_the_owning_run_has_already_been_presented() {
  local session_id="${fixture_prefix}-finished"
  printf '%s' '{"slug":"already-done","phase":"presented","pr":{"wanted":false}}' \
    > "/tmp/implement_${session_id}.json"
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should emit no directive once the batch has reached its presented phase" \
    "" "$LAST_DIRECTIVE"
}

# --- failure scenarios ---

it_should_stay_silent_when_stdin_is_malformed_json() {
  run_hook '{not-valid-json'

  assert_eq "should exit 0 when stdin is malformed JSON" "0" "$HOOK_EXIT"
  assert_eq "should emit no directive when stdin is malformed JSON" "" "$LAST_DIRECTIVE"
}

it_should_stay_silent_when_the_owning_run_left_a_corrupt_state_file() {
  local session_id="${fixture_prefix}-truncated"
  printf '%s' '{"slug":"partial-write"' > "/tmp/implement_${session_id}.json"
  run_hook "{\"session_id\":\"$session_id\",\"source\":\"compact\"}"

  assert_eq "should exit 0 when the only state file is corrupt JSON" "0" "$HOOK_EXIT"
  assert_eq "should emit no directive when the only state file is corrupt JSON" \
    "" "$LAST_DIRECTIVE"
}

it_should_remind_the_session_that_owns_the_state_file_to_finish_the_batch_end_steps
it_should_stay_silent_when_a_subagent_of_the_owning_session_compacts
it_should_stay_silent_when_a_compacting_subagent_is_identified_only_by_agent_type
it_should_keep_the_owner_in_the_task_loop_while_a_task_is_unfinished
it_should_keep_the_owner_in_the_task_loop_when_the_only_unfinished_task_is_blocked
it_should_hand_over_the_batch_end_directive_once_every_task_is_done
it_should_hand_over_the_batch_end_directive_when_the_unit_records_no_tasks
it_should_still_remind_the_owner_when_the_payload_carries_an_empty_agent_id
it_should_stay_silent_when_the_owning_session_has_no_state_file
it_should_stay_silent_when_the_owning_run_has_already_been_presented
it_should_stay_silent_when_stdin_is_malformed_json
it_should_stay_silent_when_the_owning_run_left_a_corrupt_state_file

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
