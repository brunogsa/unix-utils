#!/usr/bin/env bash
# test-claude-tmux-compact-bump.sh - plain-bash test file
# for claude-tmux-compact-bump.py's agent_id/agent_type
# routing between the main and subagent counter halves.
#
# Exits 0 when every assertion passes, non-zero
# otherwise.
#
# No bats dependency by design — a handful of small
# scripts don't justify a new cross-platform
# test-runner dependency in install.sh.
#
# Usage:
#   bash test-claude-tmux-compact-bump.sh

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SCRIPT="$script_dir/claude-tmux-compact-bump.py"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected
# vs actual, prints ok/not-ok.
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

# run_hook - pipes the given stdin JSON into a FRESH COPY
# of claude-tmux-compact-bump.py, placed under a throwaway
# work_dir that mirrors the real hooks/ + scripts/ sibling
# layout the hook resolves its title script against.
#
# The sibling scripts/tmux-window-title.sh is a stub that
# appends its argv to a capture file and exits with the
# given title_exit code (default 0), instead of driving
# real tmux — this suite must never touch the real window.
#
# HOME is also pointed at a fake, empty directory for the
# invocation, so even a wrongly-hardcoded ~/.claude/ path
# in the hook under test could never reach the real script.
#
# Sets HOOK_EXIT (the hook's own exit code) and HOOK_ARGV
# (the stub's captured argv, or empty if never invoked).
run_hook() {
  local json_input="$1" title_exit="${2:-0}"
  local work_dir capture_file
  work_dir=$(mktemp -d)
  mkdir -p "$work_dir/hooks" "$work_dir/scripts" "$work_dir/fake_home"
  cp "$HOOK_SCRIPT" "$work_dir/hooks/claude-tmux-compact-bump.py"

  capture_file="$work_dir/capture.txt"
  cat > "$work_dir/scripts/tmux-window-title.sh" <<STUB
#!/bin/bash
printf '%s' "\$*" >> "$capture_file"
exit $title_exit
STUB
  chmod +x "$work_dir/scripts/tmux-window-title.sh"

  HOOK_STDOUT=$(printf '%s' "$json_input" \
    | HOME="$work_dir/fake_home" python3 "$work_dir/hooks/claude-tmux-compact-bump.py" 2>/dev/null)
  HOOK_EXIT=$?

  if [ -f "$capture_file" ]; then
    HOOK_ARGV=$(cat "$capture_file")
  else
    HOOK_ARGV=""
  fi

  rm -rf "$work_dir"
}

# --- happy cases ---

it_should_bump_the_subagent_counter_when_agent_id_is_present() {
  run_hook '{"agent_id":"abc123"}'
  assert_eq "should exit 0 when agent_id is present" "0" "$HOOK_EXIT"
  assert_eq "should call the title script with --bump-subagent-counter when agent_id is present" \
    "--bump-subagent-counter" "$HOOK_ARGV"
}

it_should_bump_the_subagent_counter_when_agent_type_is_present_but_agent_id_is_absent() {
  run_hook '{"agent_type":"Explore"}'
  assert_eq "should call the title script with --bump-subagent-counter when agent_type is present and agent_id is absent" \
    "--bump-subagent-counter" "$HOOK_ARGV"
}

it_should_bump_the_main_counter_when_neither_agent_id_nor_agent_type_is_present() {
  run_hook '{"session_id":"main-session-1"}'
  assert_eq "should call the title script with --bump-counter when neither agent_id nor agent_type is present" \
    "--bump-counter" "$HOOK_ARGV"
}

# --- corner cases ---

it_should_bump_the_main_counter_when_agent_id_is_an_empty_string() {
  run_hook '{"agent_id":""}'
  assert_eq "should call the title script with --bump-counter when agent_id is an empty string and no agent_type is given" \
    "--bump-counter" "$HOOK_ARGV"
}

it_should_exit_0_even_when_the_title_script_itself_fails() {
  run_hook '{"session_id":"main-session-1"}' 1
  assert_eq "should exit 0 even when the title script exits non-zero" "0" "$HOOK_EXIT"
}

# --- failure scenarios ---

it_should_fall_back_to_the_main_counter_when_stdin_is_malformed_json() {
  run_hook '{not-valid-json'
  assert_eq "should exit 0 when stdin is malformed JSON" "0" "$HOOK_EXIT"
  assert_eq "should fall back to --bump-counter when stdin is malformed JSON" \
    "--bump-counter" "$HOOK_ARGV"
}

it_should_fall_back_to_the_main_counter_when_stdin_is_empty() {
  run_hook ''
  assert_eq "should exit 0 when stdin is empty" "0" "$HOOK_EXIT"
  assert_eq "should fall back to --bump-counter when stdin is empty" \
    "--bump-counter" "$HOOK_ARGV"
}

it_should_fall_back_to_the_main_counter_when_stdin_is_not_a_json_object() {
  run_hook '"just-a-string"'
  assert_eq "should fall back to --bump-counter when stdin parses to a JSON string rather than an object" \
    "--bump-counter" "$HOOK_ARGV"
}

it_should_print_nothing_on_stdout() {
  run_hook '{"session_id":"main-session-1"}'
  assert_eq "should leave stdout empty so the hook adds no context" "" "$HOOK_STDOUT"
}

it_should_bump_the_subagent_counter_when_agent_id_is_present
it_should_bump_the_subagent_counter_when_agent_type_is_present_but_agent_id_is_absent
it_should_bump_the_main_counter_when_neither_agent_id_nor_agent_type_is_present
it_should_bump_the_main_counter_when_agent_id_is_an_empty_string
it_should_exit_0_even_when_the_title_script_itself_fails
it_should_fall_back_to_the_main_counter_when_stdin_is_malformed_json
it_should_fall_back_to_the_main_counter_when_stdin_is_empty
it_should_fall_back_to_the_main_counter_when_stdin_is_not_a_json_object
it_should_print_nothing_on_stdout

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
