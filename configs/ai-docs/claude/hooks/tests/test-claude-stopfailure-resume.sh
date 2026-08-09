#!/usr/bin/env bash
# Plain-bash test file for claude-stopfailure-resume.sh.
#
# Usage:
#   bash test-claude-stopfailure-resume.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# Same no-bats rationale as the sibling test files.
#
# How the hook is exercised: it reaches the outside world only through `tmux`,
# so each case runs the REAL script with a stub `tmux` first on PATH. The stub
# logs every invocation and answers `display-message` from an env var, which
# makes both halves observable -- "did it schedule a resume, after how long?"
# and "did it type into the pane?" -- without a live tmux server.
#
# The script's state dir is a fixed /tmp path (no HOME involved), so the cases
# write real files there under a session-id prefix the trap cleans up.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESUME_HOOK="$hooks_dir/claude-stopfailure-resume.sh"

STATE_DIR=/tmp/claude-stopfailure-resume
SESSION_PREFIX=sess-resume

work_dir=$(mktemp -d)

trap 'rm -rf "$work_dir"; rm -f "$STATE_DIR/$SESSION_PREFIX"-*.count' EXIT
rm -f "$STATE_DIR/$SESSION_PREFIX"-*.count

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

# The stub stands in for the tmux binary. It records each invocation so a case
# can assert on what the hook asked tmux to do, and answers display-message
# with STUB_PANE_COMMAND so the "is Claude Code still running in that pane?"
# gate can be driven from a test.
stub_bin="$work_dir/bin"
mkdir -p "$stub_bin"
cat > "$stub_bin/tmux" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$TMUX_STUB_LOG"
if [ "$1" = "display-message" ]; then
  printf '%s\n' "${STUB_PANE_COMMAND:-2.1.226}"
fi
exit 0
STUB
chmod +x "$stub_bin/tmux"

# run_hook - runs the hook with the given stdin JSON, inside a fake tmux
# session, capturing every tmux invocation in TMUX_LOG. Extra args pass
# through, which is how the --reset and --send modes are exercised.
run_hook() {
  local stdin_json="$1"
  shift
  TMUX_LOG="$work_dir/tmux.log"
  : > "$TMUX_LOG"
  printf '%s' "$stdin_json" | \
    TMUX_STUB_LOG="$TMUX_LOG" \
    TMUX="/tmp/fake-tmux-socket,1,0" \
    TMUX_PANE="%9" \
    PATH="$stub_bin:$PATH" \
    bash "$RESUME_HOOK" "$@" 2>/dev/null
}

# scheduled_delay - the backoff the hook asked the tmux server to wait, or an
# empty string when it scheduled nothing.
scheduled_delay() {
  grep -o 'run-shell -b -d [0-9]*' "$TMUX_LOG" 2>/dev/null | awk '{print $NF}'
}

# state_file_for - the counter path the hook uses for a session id.
state_file_for() {
  printf '%s' "$STATE_DIR/$1.count"
}

# server_error_payload - a StopFailure event for the failure this hook exists
# for: the stream dropped after content had already been emitted.
server_error_payload() {
  local session_id="$1"
  printf '{"session_id":"%s","hook_event_name":"StopFailure","error_details":{"error":"server_error","message":"Server error mid-response"}}' "$session_id"
}

describe() {
  printf '\n# %s\n' "$1"
}

# --- happy path -------------------------------------------------------------

it_should_schedule_a_resume_when_a_transient_server_error_ends_the_turn() {
  local session_id="$SESSION_PREFIX-server-error"
  run_hook "$(server_error_payload "$session_id")"
  assert_eq "should schedule a resume when a transient server error ends the turn (scheduled after the first backoff)" \
    "15" "$(scheduled_delay)"
  assert_eq "should schedule a resume when a transient server error ends the turn (targets this session's own pane)" \
    "1" "$(grep -c -- "--send '%9'" "$TMUX_LOG")"
}

# The backoff has to grow, or a sustained outage becomes a re-prompt loop that
# burns the budget faster than the API recovers.
it_should_wait_longer_before_each_consecutive_resume() {
  local session_id="$SESSION_PREFIX-backoff"
  run_hook "$(server_error_payload "$session_id")"
  local first_delay
  first_delay=$(scheduled_delay)
  run_hook "$(server_error_payload "$session_id")"
  local second_delay
  second_delay=$(scheduled_delay)
  run_hook "$(server_error_payload "$session_id")"

  assert_eq "should wait longer before each consecutive resume (first attempt)" "15" "$first_delay"
  assert_eq "should wait longer before each consecutive resume (second attempt)" "60" "$second_delay"
  assert_eq "should wait longer before each consecutive resume (third attempt)" "180" "$(scheduled_delay)"
}

it_should_type_the_resume_prompt_into_the_pane_once_the_backoff_elapses() {
  run_hook '' --send '%9' 1
  assert_eq "should type the resume prompt into the pane once the backoff elapses (sends the prompt text)" \
    "1" "$(grep -c 'send-keys -t %9 -l \[auto-resume 1/3\]' "$TMUX_LOG")"
  assert_eq "should type the resume prompt into the pane once the backoff elapses (submits it)" \
    "1" "$(grep -c 'send-keys -t %9 Enter' "$TMUX_LOG")"
}

# --- failures worth skipping ------------------------------------------------

# Resuming into a session or weekly limit cannot succeed -- the next turn hits
# the same wall, so it only spams the pane and burns the budget.
it_should_not_resume_when_the_turn_ended_on_a_rate_limit() {
  local session_id="$SESSION_PREFIX-rate-limit"
  run_hook "{\"session_id\":\"$session_id\",\"error_details\":{\"error\":\"rate_limit\",\"message\":\"Claude usage limit reached\"}}"
  assert_eq "should not resume when the turn ended on a rate limit (nothing scheduled)" "" "$(scheduled_delay)"
}

# The event payload carries last_assistant_message too, so the words the model
# happened to write are in the same haystack as the error kind. A turn that
# discussed mid-response errors and then hit a limit must still not resume --
# the unrecoverable kind has to win over any resume-looking text beside it.
it_should_not_resume_when_a_rate_limited_turn_also_mentions_a_mid_response_error() {
  local session_id="$SESSION_PREFIX-mixed-markers"
  run_hook "{\"session_id\":\"$session_id\",\"error_details\":{\"error\":\"rate_limit\"},\"last_assistant_message\":\"I was explaining the mid-response server_error handler when this turn ended.\"}"
  assert_eq "should not resume when a rate-limited turn also mentions a mid-response error (nothing scheduled)" \
    "" "$(scheduled_delay)"
}

# Another turn makes the over-long prompt bigger, not smaller.
it_should_not_resume_when_the_turn_ended_on_an_over_long_prompt() {
  local session_id="$SESSION_PREFIX-too-long"
  run_hook "{\"session_id\":\"$session_id\",\"error_details\":{\"error\":\"invalid_request\",\"message\":\"Prompt is too long\"}}"
  assert_eq "should not resume when the turn ended on an over-long prompt (nothing scheduled)" "" "$(scheduled_delay)"
}

# A subagent's death leaves the main turn alive, holding the failure as a tool
# result it can retry. Typing into the pane there would inject a prompt into a
# turn that is still running.
it_should_not_resume_when_the_failure_came_from_a_subagent() {
  local session_id="$SESSION_PREFIX-subagent"
  run_hook "{\"session_id\":\"$session_id\",\"agent_id\":\"agent-a3d57f1063a3d\",\"agent_type\":\"general-purpose\",\"error_details\":{\"error\":\"server_error\"}}"
  assert_eq "should not resume when the failure came from a subagent (nothing scheduled)" "" "$(scheduled_delay)"
}

# Typing into a pane is the only lever the hook has, so without one there is
# nothing to do -- and no state worth writing either.
it_should_not_resume_when_the_session_is_not_running_under_tmux() {
  local session_id="$SESSION_PREFIX-no-tmux"
  TMUX_LOG="$work_dir/tmux.log"
  : > "$TMUX_LOG"
  printf '%s' "$(server_error_payload "$session_id")" | \
    TMUX_STUB_LOG="$TMUX_LOG" TMUX="" TMUX_PANE="" PATH="$stub_bin:$PATH" \
    bash "$RESUME_HOOK" 2>/dev/null
  assert_eq "should not resume when the session is not running under tmux (nothing scheduled)" "" "$(scheduled_delay)"
}

# Unknown errors resume nothing rather than resuming on a guess: a new error
# class is likelier to be another unrecoverable one than another transient one.
it_should_not_resume_when_the_error_kind_is_unrecognized() {
  local session_id="$SESSION_PREFIX-unknown"
  run_hook "{\"session_id\":\"$session_id\",\"error_details\":{\"error\":\"some_new_error_class\"}}"
  assert_eq "should not resume when the error kind is unrecognized (nothing scheduled)" "" "$(scheduled_delay)"
}

# --- the budget -------------------------------------------------------------

it_should_stop_resuming_after_the_third_consecutive_attempt() {
  local session_id="$SESSION_PREFIX-budget"
  run_hook "$(server_error_payload "$session_id")"
  run_hook "$(server_error_payload "$session_id")"
  run_hook "$(server_error_payload "$session_id")"
  run_hook "$(server_error_payload "$session_id")"
  assert_eq "should stop resuming after the third consecutive attempt (fourth failure schedules nothing)" \
    "" "$(scheduled_delay)"
}

# A turn that ended normally proves the API recovered, so "consecutive" has to
# mean consecutive failures -- otherwise a long session exhausts its three
# resumes on unrelated outages hours apart.
it_should_start_the_resume_budget_over_after_a_turn_ends_normally() {
  local session_id="$SESSION_PREFIX-reset"
  run_hook "$(server_error_payload "$session_id")"
  run_hook "$(server_error_payload "$session_id")"
  run_hook "{\"session_id\":\"$session_id\"}" --reset

  assert_eq "should start the resume budget over after a turn ends normally (counter cleared)" \
    "0" "$([ -e "$(state_file_for "$session_id")" ] && printf 1 || printf 0)"

  run_hook "$(server_error_payload "$session_id")"
  assert_eq "should start the resume budget over after a turn ends normally (next failure waits the first backoff again)" \
    "15" "$(scheduled_delay)"
}

# --- guarding the keystrokes ------------------------------------------------

# If Claude Code has exited, the pane is back at a shell prompt and the resume
# text would be run as a command instead of read as a prompt.
it_should_not_type_into_the_pane_when_claude_code_has_exited() {
  TMUX_LOG="$work_dir/tmux.log"
  : > "$TMUX_LOG"
  STUB_PANE_COMMAND=zsh TMUX_STUB_LOG="$TMUX_LOG" PATH="$stub_bin:$PATH" \
    bash "$RESUME_HOOK" --send '%9' 1 2>/dev/null
  assert_eq "should not type into the pane when Claude Code has exited (nothing sent)" \
    "0" "$(grep -c 'send-keys' "$TMUX_LOG")"
}

# --- classifying from the transcript ----------------------------------------

# error_details has no documented shape, so the transcript's `"error":"<kind>"`
# field is the fallback the classification can always fall back on.
it_should_classify_the_failure_from_the_transcript_when_the_event_omits_the_error_kind() {
  local session_id="$SESSION_PREFIX-transcript"
  local transcript="$work_dir/transcript-server-error.jsonl"
  {
    printf '%s\n' '{"type":"user","message":{"role":"user","content":"keep going"}}'
    printf '%s\n' '{"type":"assistant","isApiErrorMessage":true,"error":"server_error","message":{"content":[{"type":"text","text":"API Error: Server error mid-response."}]}}'
  } > "$transcript"

  run_hook "{\"session_id\":\"$session_id\",\"transcript_path\":\"$transcript\"}"
  assert_eq "should classify the failure from the transcript when the event omits the error kind (resume scheduled)" \
    "15" "$(scheduled_delay)"
}

# A long session accumulates old failures it already recovered from. Reading
# anything but the newest one would resume on a server_error from an hour ago
# while the turn that just died hit a rate limit.
it_should_classify_from_the_most_recent_failure_when_the_transcript_holds_older_ones() {
  local session_id="$SESSION_PREFIX-transcript-latest"
  local transcript="$work_dir/transcript-mixed.jsonl"
  {
    printf '%s\n' '{"type":"assistant","isApiErrorMessage":true,"error":"server_error","message":{"content":[{"type":"text","text":"API Error: Server error mid-response."}]}}'
    printf '%s\n' '{"type":"user","message":{"role":"user","content":"keep going"}}'
    printf '%s\n' '{"type":"assistant","isApiErrorMessage":true,"error":"rate_limit","message":{"content":[{"type":"text","text":"Claude usage limit reached."}]}}'
  } > "$transcript"

  run_hook "{\"session_id\":\"$session_id\",\"transcript_path\":\"$transcript\"}"
  assert_eq "should classify from the most recent failure when the transcript holds older ones (nothing scheduled)" \
    "" "$(scheduled_delay)"
}

describe "happy path"
it_should_schedule_a_resume_when_a_transient_server_error_ends_the_turn
it_should_wait_longer_before_each_consecutive_resume
it_should_type_the_resume_prompt_into_the_pane_once_the_backoff_elapses

describe "failures worth skipping"
it_should_not_resume_when_the_turn_ended_on_a_rate_limit
it_should_not_resume_when_a_rate_limited_turn_also_mentions_a_mid_response_error
it_should_not_resume_when_the_turn_ended_on_an_over_long_prompt
it_should_not_resume_when_the_failure_came_from_a_subagent
it_should_not_resume_when_the_session_is_not_running_under_tmux
it_should_not_resume_when_the_error_kind_is_unrecognized

describe "the resume budget"
it_should_stop_resuming_after_the_third_consecutive_attempt
it_should_start_the_resume_budget_over_after_a_turn_ends_normally

describe "guarding the keystrokes"
it_should_not_type_into_the_pane_when_claude_code_has_exited

describe "classifying from the transcript"
it_should_classify_the_failure_from_the_transcript_when_the_event_omits_the_error_kind
it_should_classify_from_the_most_recent_failure_when_the_transcript_holds_older_ones

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
