#!/usr/bin/env bash
# Plain-bash tests for how claude-git-guard.sh screens a git
# command run through a wrapper such as sudo, xargs or timeout.
#
# Usage:
#   bash test-claude-git-guard-wrappers.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-git-guard.sh"
bash_bin="$(command -v bash)"

pass_count=0
fail_count=0

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

# run_hook - feeds the command to the hook as a PreToolUse
# payload; HOOK_EXIT is 0 when allowed, 2 when blocked.
run_hook() {
  local stdin_json
  stdin_json=$(jq -n --arg c "$1" '{tool_input: {command: $c}}')
  printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  HOOK_EXIT=$?
}

# The wrapper runs the word after it, so git ci there may
# still be a git alias for commit.
it_should_block_a_git_alias_run_through_a_bare_wrapper() {
  local cmd
  for cmd in \
    'xargs git ci -m x' \
    'sudo git ci -m x' \
    'nohup git ci -m x' \
    'time git ci -m x'; do
    run_hook "$cmd"
    assert_eq "should block a git alias run through a bare wrapper: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_block_a_git_alias_run_through_a_wrapper_given_its_options() {
  local cmd
  for cmd in \
    'sudo -u root git ci -m x' \
    'timeout 5 git ci -m x' \
    'nice -n 5 git ci -m x' \
    'xargs -0 git ci -m x'; do
    run_hook "$cmd"
    assert_eq "should block a git alias run through a wrapper given its options: $cmd" "2" "$HOOK_EXIT"
  done
}

# An unknown option may take the next word as its value, so
# the command word cannot be told; the guard fails closed.
it_should_block_a_wrapper_whose_options_it_cannot_read() {
  run_hook 'sudo -Z git status'
  assert_eq "should block a wrapper whose options it cannot read" "2" "$HOOK_EXIT"
}

it_should_block_a_git_alias_run_through_a_bare_wrapper
it_should_block_a_git_alias_run_through_a_wrapper_given_its_options
it_should_block_a_wrapper_whose_options_it_cannot_read

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
