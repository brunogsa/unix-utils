#!/usr/bin/env bash
# Plain-bash test file for
# claude-explore-mandate-hook.sh.
#
# Usage:
#   bash test-claude-explore-mandate-hook.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design - the sibling
# hook tests set that precedent.
#
# TMPDIR is redirected to a scratch dir so a run never
# reads or clobbers a live session's counter.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-explore-mandate-hook.sh"

# Mirrors SEARCH_LIMIT in the hook. A test that derived
# it from the script would pass against any limit,
# including a broken one.
SEARCH_LIMIT=6

pass_count=0
fail_count=0

TMPDIR=$(mktemp -d)
export TMPDIR
trap 'rm -rf "$TMPDIR"' EXIT

STATE_DIR="$TMPDIR/claude-explore-mandate"

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

bash_bin="$(command -v bash)"

# run_search - one PreToolUse Grep call for the given
# session. Captures the exit code into HOOK_EXIT
# (0 = allowed, 2 = denied).
run_search() {
  local session_id="$1" stdin_json
  stdin_json=$(jq -n --arg s "$session_id" \
    '{session_id: $s, tool_name: "Grep", hook_event_name: "PreToolUse"}')
  printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  HOOK_EXIT=$?
}

# run_subagent_search - the same call as it arrives from
# inside a subagent, which carries agent_id/agent_type.
run_subagent_search() {
  local session_id="$1" stdin_json
  stdin_json=$(jq -n --arg s "$session_id" \
    '{session_id: $s, tool_name: "Grep", agent_id: "ag_1", agent_type: "Explore"}')
  printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  HOOK_EXIT=$?
}

run_reset() {
  local session_id="$1" stdin_json
  stdin_json=$(jq -n --arg s "$session_id" \
    '{session_id: $s, tool_name: "Agent", hook_event_name: "PostToolUse"}')
  printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" --reset >/dev/null 2>&1
  HOOK_EXIT=$?
}

# fill_to_limit - burns exactly SEARCH_LIMIT allowed
# searches, so the next one is the denial under test.
fill_to_limit() {
  local session_id="$1" i
  for ((i = 0; i < SEARCH_LIMIT; i++)); do
    run_search "$session_id"
  done
}

it_should_allow_the_first_search() {
  run_search "first-search"
  assert_eq "should allow the first search of a session" "0" "$HOOK_EXIT"
}

it_should_allow_every_search_up_to_the_limit() {
  local i worst=0
  for ((i = 0; i < SEARCH_LIMIT; i++)); do
    run_search "up-to-limit"
    [ "$HOOK_EXIT" -gt "$worst" ] && worst=$HOOK_EXIT
  done
  assert_eq "should allow every search up to the limit" "0" "$worst"
}

it_should_deny_the_search_past_the_limit() {
  fill_to_limit "past-limit"
  run_search "past-limit"
  assert_eq "should deny the search past the limit" "2" "$HOOK_EXIT"
}

it_should_clear_the_counter_on_the_denial() {
  fill_to_limit "deny-clears"
  run_search "deny-clears"
  run_search "deny-clears"
  assert_eq "should allow the next search after a denial cleared the counter" "0" "$HOOK_EXIT"
}

it_should_clear_the_counter_on_an_agent_dispatch() {
  fill_to_limit "agent-resets"
  run_reset "agent-resets"
  run_search "agent-resets"
  assert_eq "should allow a search again once an Agent dispatch reset the counter" "0" "$HOOK_EXIT"
}

it_should_exempt_a_search_coming_from_a_subagent() {
  local i worst=0
  for ((i = 0; i < SEARCH_LIMIT * 2; i++)); do
    run_subagent_search "subagent-exempt"
    [ "$HOOK_EXIT" -gt "$worst" ] && worst=$HOOK_EXIT
  done
  assert_eq "should never deny a search dispatched from inside a subagent" "0" "$worst"
}

it_should_allow_a_call_with_no_session_id() {
  local i worst=0 exit_code
  for ((i = 0; i < SEARCH_LIMIT * 2; i++)); do
    printf '{"tool_name":"Grep"}' | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
    exit_code=$?
    [ "$exit_code" -gt "$worst" ] && worst=$exit_code
  done
  assert_eq "should allow every search when the payload names no session" "0" "$worst"
}

it_should_count_each_session_separately() {
  fill_to_limit "session-a"
  run_search "session-b"
  assert_eq "should not spend one session's budget on another's searches" "0" "$HOOK_EXIT"
}

it_should_drop_stamps_older_than_the_window() {
  local session_id="stale-stamps" old i
  old=$(( $(date +%s) - 7200 ))
  mkdir -p "$STATE_DIR"
  : > "$STATE_DIR/$session_id.log"
  for ((i = 0; i <= SEARCH_LIMIT; i++)); do
    printf '%s\n' "$old" >> "$STATE_DIR/$session_id.log"
  done
  run_search "$session_id"
  assert_eq "should allow a search when every earlier stamp fell out of the window" "0" "$HOOK_EXIT"
}

it_should_reject_a_session_id_that_escapes_the_state_dir() {
  run_search "../../escape"
  assert_eq "should still allow the call when a traversal session id is sanitized" "0" "$HOOK_EXIT"
  assert_eq "should keep every state file inside the state dir" \
    "0" "$(find "$TMPDIR" -name '*escape*' -not -path "$STATE_DIR/*" | wc -l | tr -d ' ')"
}

it_should_allow_the_first_search
it_should_allow_every_search_up_to_the_limit
it_should_deny_the_search_past_the_limit
it_should_clear_the_counter_on_the_denial
it_should_clear_the_counter_on_an_agent_dispatch
it_should_exempt_a_search_coming_from_a_subagent
it_should_allow_a_call_with_no_session_id
it_should_count_each_session_separately
it_should_drop_stamps_older_than_the_window
it_should_reject_a_session_id_that_escapes_the_state_dir

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
