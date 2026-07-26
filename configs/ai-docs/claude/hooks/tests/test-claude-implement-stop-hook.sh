#!/usr/bin/env bash
# Plain-bash test file for claude-implement-stop-hook.sh.
#
# Usage:
#   bash test-claude-implement-stop-hook.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency by design — three small scripts don't
# justify a new cross-platform test-runner dependency in
# install.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-implement-stop-hook.sh"

work_dir=$(mktemp -d)

# The hook reads a fixed /tmp path (no HOME involved),
# so tests write real /tmp state files.
#
# The trap removes every test-session file on exit.
# The rm below clears leftovers from an interrupted prior run.
trap 'rm -rf "$work_dir"; rm -f /tmp/implement_sess-*.json' EXIT
rm -f /tmp/implement_sess-*.json

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual, prints ok/not-ok.
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

# assert_true - inline assert helper: fails when condition is false, no expected/actual diff needed.
assert_true() {
  local description="$1" condition="$2"
  if [ "$condition" = "true" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  condition was false\n' "$description"
  fi
}

# write_state - writes the given JSON body as the plain-run state file for
# session_id, at the hook's fixed /tmp path.
write_state() {
  local session_id="$1" body="$2"
  printf '%s' "$body" > "/tmp/implement_$session_id.json"
}

# write_pr_state - writes the given JSON body as the state file for one PR
# unit of session_id (the _pr<N> naming a multi-PR run uses).
write_pr_state() {
  local session_id="$1" pr_suffix="$2" body="$3"
  printf '%s' "$body" > "/tmp/implement_${session_id}_${pr_suffix}.json"
}

# run_hook - invokes the hook with the given stdin JSON, capturing
# stdout/exit code into HOOK_OUT/HOOK_EXIT (stderr is discarded — no test here
# asserts on it). An optional second arg overrides PATH (used by the
# "jq unavailable" test).
bash_bin="$(command -v bash)"

run_hook() {
  local stdin_json="$1" path_override="${2:-$PATH}"
  # Invoke bash by absolute path so a restricted PATH (the "jq unavailable"
  # test) affects only commands the hook itself runs, not resolving bash.
  HOOK_OUT=$(printf '%s' "$stdin_json" | PATH="$path_override" "$bash_bin" "$SCRIPT" 2>/dev/null)
  HOOK_EXIT=$?
}

it_should_exit_silently_when_no_state_file_exists_for_the_session_id() {
  run_hook '{"session_id": "sess-no-file", "stop_hook_active": false}'
  assert_eq "should exit silently when no state file exists for the session id (exit code)" "0" "$HOOK_EXIT"
  assert_eq "should exit silently when no state file exists for the session id (no stdout)" "" "$HOOK_OUT"
}

it_should_block_with_a_reason_when_phase_is_tasks_gates_or_tails() {
  local phase
  for phase in tasks gates tails; do
    write_state "sess-$phase" "{\"phase\": \"$phase\"}"
    run_hook "{\"session_id\": \"sess-$phase\", \"stop_hook_active\": false}"
    local decision reason
    decision=$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')
    reason=$(printf '%s' "$HOOK_OUT" | jq -r '.reason // empty')
    assert_eq "should block with a reason when phase is $phase (decision)" "block" "$decision"
    assert_true "should block with a reason when phase is $phase (reason is non-empty)" \
      "$([ -n "$reason" ] && echo true || echo false)"
  done
}

it_should_allow_the_stop_when_phase_is_presented_or_halted() {
  local phase
  for phase in presented halted blocked; do
    write_state "sess-$phase" "{\"phase\": \"$phase\"}"
    run_hook "{\"session_id\": \"sess-$phase\", \"stop_hook_active\": false}"
    assert_eq "should allow the stop when phase is $phase (exit code)" "0" "$HOOK_EXIT"
    assert_eq "should allow the stop when phase is $phase (no stdout)" "" "$HOOK_OUT"
  done
}

it_should_allow_the_stop_when_every_unit_of_a_multi_pr_run_is_halted() {
  write_pr_state "sess-multi-halted" "pr1" '{"phase": "halted", "pr_label": "pr1"}'
  write_pr_state "sess-multi-halted" "pr2" '{"phase": "blocked", "pr_label": "pr2"}'
  run_hook '{"session_id": "sess-multi-halted", "stop_hook_active": false}'
  assert_eq "should allow the stop when every unit of a multi-PR run is halted (exit code)" "0" "$HOOK_EXIT"
  assert_eq "should allow the stop when every unit of a multi-PR run is halted (no stdout)" "" "$HOOK_OUT"
}

it_should_block_naming_the_second_pr_when_only_it_is_mid_flight() {
  write_pr_state "sess-pr-second" "pr1" '{"phase": "presented", "pr_label": "pr1"}'
  write_pr_state "sess-pr-second" "pr2" '{"phase": "gates", "pr_label": "pr2"}'
  run_hook '{"session_id": "sess-pr-second", "stop_hook_active": false}'
  local decision reason
  decision=$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')
  reason=$(printf '%s' "$HOOK_OUT" | jq -r '.reason // empty')
  assert_eq "should block when only the second PR unit is mid-flight (decision)" "block" "$decision"
  assert_true "should block when only the second PR unit is mid-flight (reason names pr2)" \
    "$(printf '%s' "$reason" | grep -q "pr2" && echo true || echo false)"
  assert_true "should block when only the second PR unit is mid-flight (reason does not name pr1)" \
    "$(printf '%s' "$reason" | grep -q "pr1" && echo false || echo true)"
}

it_should_skip_a_corrupt_unit_and_still_block_on_a_valid_mid_flight_unit() {
  write_pr_state "sess-pr-mixed" "pr1" "{not valid json"
  write_pr_state "sess-pr-mixed" "pr2" '{"phase": "tasks", "pr_label": "pr2"}'
  run_hook '{"session_id": "sess-pr-mixed", "stop_hook_active": false}'
  local decision
  decision=$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')
  assert_eq "should skip a corrupt unit and still block on a valid mid-flight unit (decision)" "block" "$decision"
}

it_should_exit_silently_when_the_state_file_is_corrupt_json() {
  write_state "sess-corrupt" "{not valid json"
  run_hook '{"session_id": "sess-corrupt", "stop_hook_active": false}'
  assert_eq "should exit silently when the state file is corrupt JSON (exit code)" "0" "$HOOK_EXIT"
  assert_eq "should exit silently when the state file is corrupt JSON (no stdout)" "" "$HOOK_OUT"
}

it_should_exit_silently_when_jq_is_unavailable() {
  write_state "sess-no-jq" '{"phase": "tasks"}'

  local fake_bin="$work_dir/fake-bin"
  mkdir -p "$fake_bin"
  ln -sf "$(command -v cat)" "$fake_bin/cat"

  run_hook '{"session_id": "sess-no-jq", "stop_hook_active": false}' "$fake_bin"
  assert_eq "should exit silently when jq is unavailable (exit code)" "0" "$HOOK_EXIT"
  assert_eq "should exit silently when jq is unavailable (no stdout)" "" "$HOOK_OUT"
}

it_should_exit_silently_when_stop_hook_active_is_true() {
  write_state "sess-active" '{"phase": "tasks"}'
  run_hook '{"session_id": "sess-active", "stop_hook_active": true}'
  assert_eq "should exit silently when stop_hook_active is true (exit code)" "0" "$HOOK_EXIT"
  assert_eq "should exit silently when stop_hook_active is true (no stdout)" "" "$HOOK_OUT"
}

it_should_exit_silently_when_no_state_file_exists_for_the_session_id
it_should_block_with_a_reason_when_phase_is_tasks_gates_or_tails
it_should_allow_the_stop_when_phase_is_presented_or_halted
it_should_allow_the_stop_when_every_unit_of_a_multi_pr_run_is_halted
it_should_block_naming_the_second_pr_when_only_it_is_mid_flight
it_should_skip_a_corrupt_unit_and_still_block_on_a_valid_mid_flight_unit
it_should_exit_silently_when_the_state_file_is_corrupt_json
it_should_exit_silently_when_jq_is_unavailable
it_should_exit_silently_when_stop_hook_active_is_true

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
