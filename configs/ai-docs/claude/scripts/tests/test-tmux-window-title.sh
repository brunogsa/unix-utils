#!/usr/bin/env bash

# test-tmux-window-title.sh - plain-bash test file for
# tmux-window-title.sh, the window-titling script behind
# Claude Code's SessionStart title hooks.
#
# Covers the compaction counter, the frozen root anchor,
# and the two length caps.

# Usage:
#   bash test-tmux-window-title.sh

# No bats dependency by design — same precedent as these
# sibling suites under configs/ai-docs/claude/:
#
# - scripts/tests/test-statusline-tier.sh
# - hooks/tests/test-claude-git-guard.sh

# The script under test only acts inside tmux, so each test
# runs against a PRIVATE tmux server on its own socket
# ($TMUX/$TMUX_PANE point at it). The user's real tmux
# server, windows, and pane options are never touched.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../tmux-window-title.sh"

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

# start_server - boot a private tmux server and export the
# $TMUX/$TMUX_PANE pair the script reads, plus $SOCK for
# addressing that server from the test itself.
#
# Sets globals rather than echoing the socket, because the
# exports have to land in the CALLER's environment — a
# command substitution would strand them in a subshell.
#
# $TMUX's real format is "<socket>,<pid>,<session>"; the
# script only tests it for non-emptiness, while the tmux
# client parses the socket path out of it to find the
# server — so the pid/session fields can be stubbed.
start_server() {
  SOCK="tmux-title-test-$$-${RANDOM}"
  tmux -L "$SOCK" new-session -d -s t 2>/dev/null

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

# window_name - the current title of the pane under test.
window_name() {
  tmux -L "$SOCK" display-message -t "$TMUX_PANE" -p '#{window_name}'
}

title() {
  bash "$SCRIPT_UNDER_TEST" "$@"
}

it_should_set_a_plain_title_before_any_compaction() {
  start_server

  title "auth-fix"

  assert_eq \
    "TmuxWindowTitle > plain > should set the title verbatim when no counter exists" \
    "auth-fix" "$(window_name)"
  stop_server
}

it_should_hyphenate_whitespace_in_a_title() {
  start_server

  title "fix the auth bug"

  assert_eq \
    "TmuxWindowTitle > plain > should collapse whitespace runs into single hyphens" \
    "fix-the-auth-bug" "$(window_name)"
  stop_server
}

it_should_start_the_counter_at_one_on_the_first_compaction() {
  start_server

  title "auth-fix"
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > counter > should start the compaction counter at 1" \
    "auth-fix[1]" "$(window_name)"
  stop_server
}

it_should_increment_the_counter_on_later_compactions() {
  start_server

  title "auth-fix"
  title --bump-counter
  title --bump-counter
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > counter > should increment the counter on each later compaction" \
    "auth-fix[3]" "$(window_name)"
  stop_server
}

it_should_root_a_retitle_that_follows_a_compaction() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "db-store"

  assert_eq \
    "TmuxWindowTitle > root > should prefix a drifted title with the frozen root" \
    "auth-fix/db-store[1]" "$(window_name)"
  stop_server
}

it_should_freeze_the_root_at_the_last_pre_compaction_title() {
  start_server

  # Pre-compaction re-titles are refinements of the same
  # session identity, so the LAST one is what the user has
  # been reading when the first compaction lands.
  title "auth"
  title "auth-fix"
  title --bump-counter
  title "db-store"

  assert_eq \
    "TmuxWindowTitle > root > should freeze the last pre-compaction title, not the first" \
    "auth-fix/db-store[1]" "$(window_name)"
  stop_server
}

it_should_keep_the_root_stable_across_later_compactions() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "db-store"
  title --bump-counter
  title --bump-counter

  # Regression guard: the window name is a RENDERED title,
  # so re-reading it on each bump used to compose a second
  # root onto the first ("auth-fix/auth-fix[3]").
  assert_eq \
    "TmuxWindowTitle > root > should not re-root a title that already carries its root" \
    "auth-fix/db-store[3]" "$(window_name)"
  stop_server
}

it_should_keep_the_root_immutable_across_many_retitles() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "token-refresh"
  title --bump-counter
  title "db-store"

  assert_eq \
    "TmuxWindowTitle > root > should keep anchoring to the original root after several topic shifts" \
    "auth-fix/db-store[2]" "$(window_name)"
  stop_server
}

it_should_drop_root_words_from_the_current_work() {
  start_server

  title "tmux-titles"
  title --bump-counter
  title "tmux-titles-cap"

  # The root already spells "tmux-titles" out, so repeating
  # it would cost the cap the only new word.
  assert_eq \
    "TmuxWindowTitle > root > should drop from the current work every word the root already carries" \
    "tmux-titles/cap[1]" "$(window_name)"
  stop_server
}

it_should_drop_only_whole_words_of_the_root() {
  start_server

  title "auth"
  title --bump-counter
  title "authz-fix"

  # "authz" merely starts with the root — dropping it would
  # lose the word the current work is actually about.
  assert_eq \
    "TmuxWindowTitle > root > should keep a current-work word that only starts with a root word" \
    "auth/authz-fix[1]" "$(window_name)"
  stop_server
}

it_should_render_bare_when_the_root_covers_every_word() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "auth"

  assert_eq \
    "TmuxWindowTitle > root > should render bare when the root already covers every word of the current work" \
    "auth-fix[1]" "$(window_name)"
  stop_server
}

it_should_render_bare_when_the_title_matches_the_root() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "token-refresh"
  title "auth-fix"

  assert_eq \
    "TmuxWindowTitle > root > should render bare when the current work returns to the root" \
    "auth-fix[1]" "$(window_name)"
  stop_server
}

it_should_fold_a_caller_supplied_separator_into_a_hyphen() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "auth-fix/token-refresh"

  # The script owns the composition, so a caller passing an
  # already-rooted string must not nest one root in another.
  assert_eq \
    "TmuxWindowTitle > root > should fold a caller-supplied slash into a hyphen" \
    "auth-fix/token-refres[1]" "$(window_name)"
  stop_server
}

it_should_not_root_a_pane_claude_never_titled() {
  start_server

  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "zsh"
  title --bump-counter
  title "auth-fix"

  # Freezing here would anchor every later title to the
  # user's own shell name ("zsh/auth-fix").
  assert_eq \
    "TmuxWindowTitle > root > should not freeze a root from the user's pre-Claude window name" \
    "auth-fix[1]" "$(window_name)"
  stop_server
}

it_should_cap_a_plain_title_at_sixteen_chars() {
  start_server

  title "abcdefghijklmnopqrstuvwxyz"

  assert_eq \
    "TmuxWindowTitle > cap > should cap a counter-less title at 16 chars" \
    "abcdefghijklmnop" "$(window_name)"
  stop_server
}

it_should_cap_a_rooted_title_at_twentyfour_chars_including_the_counter() {
  start_server

  title "verylongrootname"
  title --bump-counter
  title "verylongcurrentwork"

  local actual; actual=$(window_name)
  assert_eq \
    "TmuxWindowTitle > cap > should cap a rooted title at 24 chars, counter included" \
    "verylongro/verylongcu[1]" "$actual"
  assert_eq \
    "TmuxWindowTitle > cap > should render a rooted title exactly 24 chars wide" \
    "24" "${#actual}"
  stop_server
}

it_should_give_a_short_root_s_slack_to_the_current_work() {
  start_server

  title "ab"
  title --bump-counter
  title "verylongcurrentwork"

  # Half of the 20-char text budget is 10; the 2-char root
  # hands its unspent 8 to the current work, which keeps 18.
  assert_eq \
    "TmuxWindowTitle > cap > should hand a short root's unused room to the current work" \
    "ab/verylongcurrentwor[1]" "$(window_name)"
  stop_server
}

it_should_give_a_short_current_work_s_slack_to_the_root() {
  start_server

  title "verylongrootname"
  title --bump-counter
  title "abcdef"

  # The mirror case: the 6-char current work hands its
  # unspent 4 to the root, which keeps 14 instead of 10.
  assert_eq \
    "TmuxWindowTitle > cap > should hand short current work's unused room back to the root" \
    "verylongrootna/abcdef[1]" "$(window_name)"
  stop_server
}

it_should_keep_the_counter_whole_when_truncating() {
  start_server

  title "verylongrootname"
  title --bump-counter
  title "verylongcurrentwork"

  # Drive the counter to two digits: the suffix must stay
  # intact and the text absorb the extra character.
  for _ in 1 2 3 4 5 6 7 8 9; do title --bump-counter; done

  local actual; actual=$(window_name)
  assert_eq \
    "TmuxWindowTitle > cap > should keep a two-digit counter whole and shrink the text instead" \
    "verylongr/verylongcu[10]" "$actual"
  stop_server
}

it_should_drop_a_trailing_hyphen_left_by_truncation() {
  start_server

  title "aaaa-bbbb-cccc-dddd"
  title --bump-counter
  title "xxxxxxxxxxxxxxxxxxx"

  assert_eq \
    "TmuxWindowTitle > cap > should drop a trailing hyphen the truncation cut leaves" \
    "aaaa-bbbb/xxxxxxxxxx[1]" "$(window_name)"
  stop_server
}

it_should_drop_the_counter_and_the_root_on_reset() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "db-store"
  title --reset-counter

  assert_eq \
    "TmuxWindowTitle > reset > should shed both the counter and the root prefix" \
    "db-store" "$(window_name)"
  stop_server
}

it_should_let_a_new_root_be_frozen_after_a_reset() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "db-store"
  title --reset-counter
  title --bump-counter
  title "api-cache"

  # The new root is "db-store", the title the pane carried
  # when the reset landed — not the released "auth-fix".
  assert_eq \
    "TmuxWindowTitle > reset > should anchor the next session to its own first title" \
    "db-store/api-cache[1]" "$(window_name)"
  stop_server
}

it_should_release_the_root_even_when_no_counter_is_present() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "db-store"
  title --reset-counter

  # Second reset: no counter to strip, so the mode returns
  # early — the root must already have been released.
  title --reset-counter
  title --bump-counter
  title "api-cache"

  assert_eq \
    "TmuxWindowTitle > reset > should release the root before the no-counter early return" \
    "db-store/api-cache[1]" "$(window_name)"
  stop_server
}

it_should_leave_an_untitled_window_alone_on_reset() {
  start_server

  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "zsh"
  title --reset-counter

  assert_eq \
    "TmuxWindowTitle > reset > should leave a window Claude never titled untouched" \
    "zsh" "$(window_name)"
  stop_server
}

it_should_reject_a_title_that_sanitizes_to_nothing() {
  start_server

  local status=0
  title "///" >/dev/null 2>&1 || status=$?

  assert_eq \
    "TmuxWindowTitle > misuse > should exit 1 on a title that is empty after sanitizing" \
    "1" "$status"
  stop_server
}

it_should_reject_a_missing_title() {
  local status=0
  bash "$SCRIPT_UNDER_TEST" >/dev/null 2>&1 || status=$?

  assert_eq \
    "TmuxWindowTitle > misuse > should exit 1 when no title argument is given" \
    "1" "$status"
}

it_should_no_op_outside_tmux() {
  local status=0
  env -u TMUX -u TMUX_PANE bash "$SCRIPT_UNDER_TEST" "auth-fix" >/dev/null 2>&1 || status=$?

  assert_eq \
    "TmuxWindowTitle > misuse > should exit 0 silently when there is no tmux to title" \
    "0" "$status"
}

it_should_print_help_to_stdout() {
  local out status=0
  out=$(env -u TMUX -u TMUX_PANE bash "$SCRIPT_UNDER_TEST" --help 2>/dev/null) || status=$?

  assert_eq \
    "TmuxWindowTitle > help > should exit 0 on --help" \
    "0" "$status"

  # A case block cannot live inside "$( )": its pattern's
  # closing paren ends the substitution early.
  local documents_root=no
  case "$out" in *"Root anchor:"*) documents_root=yes ;; esac

  assert_eq \
    "TmuxWindowTitle > help > should describe the root anchor in --help" \
    "yes" "$documents_root"
}

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not installed — cannot exercise tmux-window-title.sh" >&2
  exit 1
fi

it_should_set_a_plain_title_before_any_compaction
it_should_hyphenate_whitespace_in_a_title
it_should_start_the_counter_at_one_on_the_first_compaction
it_should_increment_the_counter_on_later_compactions
it_should_root_a_retitle_that_follows_a_compaction
it_should_freeze_the_root_at_the_last_pre_compaction_title
it_should_keep_the_root_stable_across_later_compactions
it_should_keep_the_root_immutable_across_many_retitles
it_should_drop_root_words_from_the_current_work
it_should_drop_only_whole_words_of_the_root
it_should_render_bare_when_the_root_covers_every_word
it_should_render_bare_when_the_title_matches_the_root
it_should_fold_a_caller_supplied_separator_into_a_hyphen
it_should_not_root_a_pane_claude_never_titled
it_should_cap_a_plain_title_at_sixteen_chars
it_should_cap_a_rooted_title_at_twentyfour_chars_including_the_counter
it_should_give_a_short_root_s_slack_to_the_current_work
it_should_give_a_short_current_work_s_slack_to_the_root
it_should_keep_the_counter_whole_when_truncating
it_should_drop_a_trailing_hyphen_left_by_truncation
it_should_drop_the_counter_and_the_root_on_reset
it_should_let_a_new_root_be_frozen_after_a_reset
it_should_release_the_root_even_when_no_counter_is_present
it_should_leave_an_untitled_window_alone_on_reset
it_should_reject_a_title_that_sanitizes_to_nothing
it_should_reject_a_missing_title
it_should_no_op_outside_tmux
it_should_print_help_to_stdout

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
