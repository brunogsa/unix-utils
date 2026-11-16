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

# rg reads its config file from here, so each run starts
# without it and a test sets it only on purpose.
unset RIPGREP_CONFIG_PATH

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
    'xargs -0 git ci -m x' \
    'xargs -n1 git ci -m x' \
    'git log -3 | xargs -n1 git commit -m x' \
    'git log -3 | xargs -n 1 git commit -m x'; do
    run_hook "$cmd"
    assert_eq "should block a git alias run through a wrapper given its options: $cmd" "2" "$HOOK_EXIT"
  done
}

# xargs reads -n1 as -n 1, so the word after it is the command
# it runs, here no git at all.
it_should_allow_read_only_git_output_piped_into_xargs_n1_running_a_non_git_command() {
  local cmd
  for cmd in \
    'git status --short | xargs -n1 dirname' \
    'git log --format=%h -3 | xargs -n1 basename' \
    'git status --short | xargs -n 1 dirname' \
    'ls /tmp | xargs -n1 basename'; do
    run_hook "$cmd"
    assert_eq "should allow read-only git output piped into xargs -n1 running a non-git command: $cmd" "0" "$HOOK_EXIT"
  done
}

# An unknown option may take the next word as its value, so
# the command word cannot be told; the guard fails closed.
# The shell may split -n$X into more words, as -n1 git commit,
# so the word after it is not surely the command xargs runs.
it_should_block_an_xargs_whose_glued_option_value_the_shell_may_split() {
  run_hook 'git log -3 | xargs -n$X git status'
  assert_eq "should block an xargs whose glued option value the shell may split" "2" "$HOOK_EXIT"
}

# X='1 git commit -m x' splits -n $X into -n 1 git commit -m x,
# so the git status after it is not surely the command run.
it_should_block_a_wrapper_whose_separate_option_value_the_shell_may_split() {
  run_hook 'git log -3 | xargs -n $X git status'
  assert_eq "should block a wrapper whose separate option value the shell may split" "2" "$HOOK_EXIT"
}

it_should_block_a_wrapper_whose_options_it_cannot_read() {
  run_hook 'sudo -Z git status'
  assert_eq "should block a wrapper whose options it cannot read" "2" "$HOOK_EXIT"
}

it_should_block_a_git_alias_run_by_a_command_not_known_as_a_wrapper() {
  run_hook 'stdbuf -oL git ci -m x'
  assert_eq "should block a git alias run by a command not known as a wrapper" "2" "$HOOK_EXIT"
}

# xargs -I swaps each named word for a stdin line, so the
# status here may run as commit.
it_should_block_an_xargs_that_rewrites_its_git_words() {
  run_hook 'xargs -I status git status -m x'
  assert_eq "should block an xargs that rewrites its git words" "2" "$HOOK_EXIT"
}

it_should_block_a_git_alias_set_in_the_environment_or_run_by_an_expandable_word() {
  local cmd
  for cmd in \
    'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.zz GIT_CONFIG_VALUE_0=commit git zz -m x' \
    '$X git zz -m x'; do
    run_hook "$cmd"
    assert_eq "should block a git alias set in the environment or run by an expandable word: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_allow_a_later_git_word_read_as_data_by_a_command_that_runs_no_argument() {
  local cmd
  for cmd in 'grep git file' 'rg git configs'; do
    run_hook "$cmd"
    assert_eq "should allow a later git word read as data by a command that runs no argument: $cmd" "0" "$HOOK_EXIT"
  done
}

# A function or alias of the same name runs its arguments, so
# the git word after grep may then run as git.
it_should_block_a_later_git_word_after_grep_when_the_command_redefines_a_name() {
  local cmd
  for cmd in \
    'grep() { "$@"; }; grep git zz -m x' \
    'function grep { "$@"; }; grep git zz -m x' \
    'alias grep=sh; grep git zz'; do
    run_hook "$cmd"
    assert_eq "should block a later git word after grep when the command redefines a name: $cmd" "2" "$HOOK_EXIT"
  done
}

# A new PATH may find another grep, and an rg config file may
# set --pre, the program rg runs on each file.
it_should_block_a_later_git_word_after_a_search_command_when_the_command_changes_its_lookup() {
  local cmd
  for cmd in \
    'RIPGREP_CONFIG_PATH=/tmp/c rg git zz' \
    'export RIPGREP_CONFIG_PATH=/tmp/c; rg git zz' \
    'PATH=/tmp/e:$PATH grep git zz -m x' \
    'export PATH=/tmp/e; grep git zz -m x'; do
    run_hook "$cmd"
    assert_eq "should block a later git word after a search command when the command changes its lookup: $cmd" "2" "$HOOK_EXIT"
  done
}

# Only a lone grep or rg is surely the search program: any
# other statement, assignment or wrapper may change what that
# name runs.
it_should_block_a_later_git_word_after_a_search_command_that_is_not_the_whole_command() {
  local cmd
  for cmd in \
    'hash -p /bin/sh grep; grep git zz -m x' \
    'source f; grep git zz' \
    'BASH_ENV=/tmp/x grep git zz' \
    'command grep git zz -m x'; do
    run_hook "$cmd"
    assert_eq "should block a later git word after a search command that is not the whole command: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_block_a_later_git_word_after_rg_when_the_environment_names_an_rg_config() {
  RIPGREP_CONFIG_PATH=/tmp/c run_hook 'rg git zz'
  assert_eq "should block a later git word after rg when the environment names an rg config" "2" "$HOOK_EXIT"
}

# The guard reads no git config: an earlier stage may write
# one, and sudo, find -exec or ssh may run git under another
# user, directory or host, so any name may be an alias there.
it_should_block_a_later_git_word_naming_no_git_builtin_after_a_command_that_may_run_it() {
  local cmd
  for cmd in \
    "printf '[alias]\\n ci2 = commit\\n' >> ~/.gitconfig; stdbuf git ci2 -m x" \
    'tee -a .git/config < f; stdbuf git zz -m x' \
    'sudo -u other stdbuf git zz -m x' \
    'find . -maxdepth 0 -exec git zz -m x ;' \
    'ssh host git zz -m x'; do
    run_hook "$cmd"
    assert_eq "should block a later git word naming no git builtin after a command that may run it: $cmd" "2" "$HOOK_EXIT"
  done
}

it_should_allow_a_wrapper_running_no_git_alias() {
  local cmd
  for cmd in \
    'sudo ls' \
    'time make' \
    'xargs grep foo' \
    'sudo git status'; do
    run_hook "$cmd"
    assert_eq "should allow a wrapper running no git alias: $cmd" "0" "$HOOK_EXIT"
  done
}

it_should_block_a_git_alias_run_through_a_bare_wrapper
it_should_block_a_git_alias_run_through_a_wrapper_given_its_options
it_should_allow_read_only_git_output_piped_into_xargs_n1_running_a_non_git_command
it_should_block_an_xargs_whose_glued_option_value_the_shell_may_split
it_should_block_a_wrapper_whose_separate_option_value_the_shell_may_split
it_should_block_a_wrapper_whose_options_it_cannot_read
it_should_block_a_git_alias_run_by_a_command_not_known_as_a_wrapper
it_should_block_an_xargs_that_rewrites_its_git_words
it_should_block_a_git_alias_set_in_the_environment_or_run_by_an_expandable_word
it_should_allow_a_later_git_word_read_as_data_by_a_command_that_runs_no_argument
it_should_block_a_later_git_word_after_grep_when_the_command_redefines_a_name
it_should_block_a_later_git_word_after_a_search_command_when_the_command_changes_its_lookup
it_should_block_a_later_git_word_after_a_search_command_that_is_not_the_whole_command
it_should_block_a_later_git_word_after_rg_when_the_environment_names_an_rg_config
it_should_block_a_later_git_word_naming_no_git_builtin_after_a_command_that_may_run_it
it_should_allow_a_wrapper_running_no_git_alias

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
