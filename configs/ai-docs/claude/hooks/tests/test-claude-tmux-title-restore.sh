#!/usr/bin/env bash

# test-claude-tmux-title-restore.sh - plain-bash test file for
# claude-tmux-title-restore.sh, the SessionEnd hook that puts
# the pre-Claude tmux window name back.
#
# Usage:
#   bash test-claude-tmux-title-restore.sh
#
# The hook only acts inside tmux, so each test runs against a
# PRIVATE tmux server on its own socket ($TMUX/$TMUX_PANE point
# at it). The user's real tmux server is never touched.
# Same server setup as scripts/tests/test-tmux-window-title.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_UNDER_TEST="$script_dir/../claude-tmux-title-restore.sh"

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

# start_server - boot a private tmux server and export the
# $TMUX/$TMUX_PANE pair the hook reads; $SOCK addresses it.
start_server() {
  SOCK="tmux-restore-test-$$-${RANDOM}"
  tmux -f /dev/null -L "$SOCK" new-session -d -s t cat 2>/dev/null

  local socket_path
  socket_path=$(tmux -L "$SOCK" display-message -p '#{socket_path}')
  TMUX_PANE=$(tmux -L "$SOCK" display-message -p '#{pane_id}')
  TMUX="$socket_path,0,0"
  export TMUX TMUX_PANE
}

stop_server() {
  tmux -L "$SOCK" kill-server 2>/dev/null
  unset TMUX TMUX_PANE
}

window_name() {
  tmux -L "$SOCK" display-message -t "$TMUX_PANE" -p '#{window_name}'
}

auto_rename() {
  tmux -L "$SOCK" show-window-options -t "$TMUX_PANE" -v automatic-rename 2>/dev/null || true
}

pane_option() {
  tmux -L "$SOCK" show-options -p -t "$TMUX_PANE" -v "$1" 2>/dev/null || true
}

# claude_titled_window - leave the window the way the title
# script does: the pre-Claude name and flag captured into pane
# options, automatic-rename off, and Claude's title showing.
claude_titled_window() {
  local prev_name="$1" prev_auto="$2" shown="$3"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_prev_window_name" "$prev_name"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_prev_auto_rename" "$prev_auto"
  tmux -L "$SOCK" set-window-option -t "$TMUX_PANE" automatic-rename off
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" -- "$shown"
}

session_end() {
  printf '{"reason":"%s"}' "$1" | bash "$HOOK_UNDER_TEST"
}

it_should_restore_zsh_over_dot_city_code_retry_fix_1_on_reason_other() {
  start_server
  claude_titled_window "zsh" "off" ".city-code/retry-fix[1]"
  session_end other
  assert_eq "window shows zsh over the dotted title on exit" "zsh" "$(window_name)"
  stop_server
}

it_should_restore_zsh_over_dot_city_code_retry_fix_1_on_reason_other

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
