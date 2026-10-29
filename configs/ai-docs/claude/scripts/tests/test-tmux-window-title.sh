#!/usr/bin/env bash

# test-tmux-window-title.sh - plain-bash test file for
# tmux-window-title.sh, the window-titling script behind
# Claude Code's SessionStart title hooks.
#
# Covers the compaction counter, the frozen root anchor,
# and the two length caps.

# Usage:
#   bash test-tmux-window-title.sh

# No bats dependency by design - same precedent as these
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
# exports have to land in the CALLER's environment - a
# command substitution would strand them in a subshell.
#
# $TMUX's real format is "<socket>,<pid>,<session>"; the
# script only tests it for non-emptiness, while the tmux
# client parses the socket path out of it to find the
# server - so the pid/session fields can be stubbed.
start_server() {
  SOCK="tmux-title-test-$$-${RANDOM}"

  # -f /dev/null skips ~/.tmux.conf, whose plugins slow each
  # boot from ~40 ms to ~800 ms; cat keeps the session alive
  # without starting the user's login shell.
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

# window_name - the current title of the pane under test.
window_name() {
  tmux -L "$SOCK" display-message -t "$TMUX_PANE" -p '#{window_name}'
}

# set_last_title - record `name` as the name the script itself
# last wrote, the way apply_title does, so a name injected with
# rename-window reads as the script's own and never as a hand
# rename.
set_last_title() {
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_last_title" "$1"
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

  # Also the "no compact-focus label set yet" case: nothing was
  # retitled since the freeze, so the root renders alone with no
  # trailing "/" -- the label field never appears until Claude
  # calls title() again.
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

it_should_render_a_subagent_bump_alone_as_zero_plus_one() {
  start_server

  title "auth-fix"
  title --bump-subagent-counter

  assert_eq \
    "TmuxWindowTitle > counter > should render a subagent bump alone as [0+1] when no main compaction happened yet" \
    "auth-fix[0+1]" "$(window_name)"
  stop_server
}

it_should_render_main_then_subagent_bumps_as_one_plus_one() {
  start_server

  title "auth-fix"
  title --bump-counter
  title --bump-subagent-counter

  assert_eq \
    "TmuxWindowTitle > counter > should render [1+1] after a main compaction followed by a subagent compaction" \
    "auth-fix[1+1]" "$(window_name)"
  stop_server
}

it_should_render_subagent_then_main_bumps_as_one_plus_one() {
  start_server

  title "auth-fix"
  title --bump-subagent-counter
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > counter > should render [1+1] after a subagent compaction followed by a main compaction" \
    "auth-fix[1+1]" "$(window_name)"
  stop_server
}

it_should_render_two_subagent_bumps_as_zero_plus_two() {
  start_server

  title "auth-fix"
  title --bump-subagent-counter
  title --bump-subagent-counter

  assert_eq \
    "TmuxWindowTitle > counter > should render [0+2] after two subagent compactions with no main compaction" \
    "auth-fix[0+2]" "$(window_name)"
  stop_server
}

it_should_preserve_a_split_counter_across_a_retitle() {
  start_server

  title --bump-subagent-counter
  title "db-store"

  # No main bump ever landed, so no root is frozen -- this
  # isolates counter preservation from the rooting behavior
  # covered separately below.
  assert_eq \
    "TmuxWindowTitle > counter > should preserve an existing [M+S] counter when the title is reset to a new base" \
    "db-store[0+1]" "$(window_name)"
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

  # A session sets one title before its first compaction (a
  # re-title is refused), so that title is what the user has
  # been reading when the first compaction lands.
  title "auth-fix"
  title --bump-counter
  title "db-store"

  assert_eq \
    "TmuxWindowTitle > root > should freeze the one pre-compaction title as root" \
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

it_should_not_drop_root_words_from_the_compact_focus_label() {
  start_server

  title "tmux-titles"
  title --bump-counter
  title "tmux-titles-cap"

  # Word-dedup was removed: the compact-focus label renders
  # as-is (subject to its own 16-char tail room), even though
  # it repeats "tmux-titles" from the root.
  assert_eq \
    "TmuxWindowTitle > root > should not drop a compact-focus word that repeats one already in the root" \
    "tmux-titles/tmux-titles[1]" "$(window_name)"
  stop_server
}

it_should_not_render_bare_when_the_compact_focus_label_merely_contains_root_words() {
  start_server

  title "auth-fix"
  title --bump-counter
  title "auth"

  # "auth" is not IDENTICAL to the root "auth-fix" (only a
  # substring of it), so the bare fallback -- reserved for an
  # exact string match -- must not fire; the label renders.
  assert_eq \
    "TmuxWindowTitle > root > should render the compact-focus label when it is a substring of the root, not just equal to it" \
    "auth-fix/auth[1]" "$(window_name)"
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
  title "a/b"

  # The script owns the composition, so a caller passing a
  # slash must not nest a second root separator in another --
  # "a/b" folds to "a-b", a single hyphenated word.
  assert_eq \
    "TmuxWindowTitle > root > should fold a caller-supplied slash into a hyphen" \
    "auth-fix/a-b[1]" "$(window_name)"
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

it_should_freeze_the_root_at_the_title_current_when_the_main_bump_lands() {
  start_server

  title --bump-subagent-counter
  title "db-store"

  # A subagent bump never freezes a root, so the title above
  # lands on a still-rootless pane and just carries the counter.
  assert_eq \
    "TmuxWindowTitle > root > should freeze no root from a subagent bump alone" \
    "db-store[0+1]" "$(window_name)"

  title --bump-counter

  # The main bump freezes whatever title is current AT THIS
  # MOMENT ("db-store") -- a bare render is only possible
  # when the root equals "db-store" exactly.
  assert_eq \
    "TmuxWindowTitle > root > should freeze the root at the title current when the main bump lands" \
    "db-store[1+1]" "$(window_name)"
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

it_should_cap_a_rooted_title_at_thirtytwo_chars_including_the_counter() {
  start_server

  title "verylongrootname"
  title --bump-counter
  title "verylongcurrentwork"

  local actual; actual=$(window_name)
  assert_eq \
    "TmuxWindowTitle > cap > should cap a rooted title at 32 chars, counter included" \
    "verylongrootname/verylongcurr[1]" "$actual"
  assert_eq \
    "TmuxWindowTitle > cap > should render a rooted title exactly 32 chars wide" \
    "32" "${#actual}"
  stop_server
}

it_should_not_reallocate_a_short_root_s_unused_room_to_the_compact_focus_label() {
  start_server

  title "ab"
  title --bump-counter
  title "verylongcurrentwork"

  # Reallocation was removed: the compact-focus label still gets
  # only its fixed 16-char tail room (13 chars once "/" and the
  # [1] suffix are accounted for) even though the 2-char root
  # leaves 14 chars of its own room unused.
  assert_eq \
    "TmuxWindowTitle > cap > should not hand a short root's unused room to the compact-focus label" \
    "ab/verylongcurr[1]" "$(window_name)"
  stop_server
}

it_should_keep_the_counter_whole_when_truncating() {
  start_server

  title "verylongrootname"
  title --bump-counter
  title "verylongcurrentwork"

  # Drive the counter to two digits: the suffix must stay
  # intact and the current-work half absorbs the extra
  # character, since the root keeps its fixed 16-char
  # entitlement.
  for _ in 1 2 3 4 5 6 7 8 9; do title --bump-counter; done

  local actual; actual=$(window_name)
  assert_eq \
    "TmuxWindowTitle > cap > should keep a two-digit counter whole and shrink only the label" \
    "verylongrootname/verylongcur[10]" "$actual"
  stop_server
}

it_should_drop_a_trailing_hyphen_left_by_truncating_the_label() {
  start_server

  # The label lands exactly on a hyphen at its 16-char tail room
  # (13 chars once "/" and the [1] suffix are accounted for):
  # "/bbbbbbbbbbb-cc" cuts to "/bbbbbbbbbbb-" and the trailing
  # "-" is then stripped.
  title "auth-fix"
  title --bump-counter
  title "bbbbbbbbbbb-cc"

  assert_eq \
    "TmuxWindowTitle > cap > should drop a trailing hyphen the label truncation cut leaves" \
    "auth-fix/bbbbbbbbbbb[1]" "$(window_name)"
  stop_server
}

it_should_drop_a_trailing_hyphen_left_by_truncating_the_root() {
  start_server

  # A 17-char injected counter steals 1 char from the head room
  # (16 -> 15), landing the cut exactly on a hyphen:
  # "aaaaaaaaaaaaaa-z" cuts to "aaaaaaaaaaaaaa-" and the
  # trailing "-" is then stripped.
  #
  # The label room (16 - 17 < 0, clamped) drops to 0, so no
  # label field renders at all.
  title "aaaaaaaaaaaaaa-z"
  title --bump-counter
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "aaaaaaaaaaaaaa-z[123456789012345]"
  set_last_title "aaaaaaaaaaaaaa-z[123456789012345]"
  title "aaaaaaaaaaaaaa-z"

  assert_eq \
    "TmuxWindowTitle > cap > should drop a trailing hyphen the root truncation cut leaves" \
    "aaaaaaaaaaaaaa[123456789012345]" "$(window_name)"
  stop_server
}

it_should_keep_a_split_counter_suffix_whole_when_truncating() {
  start_server

  title "verylongrootname"
  title --bump-counter
  title "verylongcurrentwork"
  title --bump-counter
  title --bump-counter
  title --bump-subagent-counter
  title --bump-subagent-counter

  # The [3+2] suffix is two chars wider than a plain [1], but
  # the root keeps its fixed 16-char entitlement -- only the
  # label gives up the extra room, and the suffix itself stays
  # whole either way.
  local actual; actual=$(window_name)
  assert_eq \
    "TmuxWindowTitle > cap > should shrink only the label to keep a two-half [M+S] suffix whole" \
    "verylongrootname/verylongcu[3+2]" "$actual"
  assert_eq \
    "TmuxWindowTitle > cap > should render a split-counter title exactly 32 chars wide" \
    "32" "${#actual}"
  stop_server
}

it_should_keep_the_root_at_sixteen_chars_for_every_counter_width_up_to_sixteen() {
  start_server

  # Deliberately no 3:2-style steal on the root anymore.
  #
  # For every counter width from the minimal [1] (W=3) up to
  # the 16-char boundary (W=16, a 14-digit body), the root keeps
  # its full fixed 16-char room and only the label's tail room
  # shrinks.
  #
  # A 16-char root and a long label make any root cut visible
  # immediately.
  title "aaaaaaaaaaaaaaaa"
  title --bump-counter
  title "bbbbbbbbbbbbbbbbbbbb"

  for digit_count in 1 2 3 4 5 6 7 8 9 10 11 12 13 14; do
    local digits; digits=$(printf '1%.0s' $(seq 1 "$digit_count"))
    tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "aaaaaaaaaaaaaaaa[${digits}]"
    set_last_title "aaaaaaaaaaaaaaaa[${digits}]"
    title "bbbbbbbbbbbbbbbbbbbb"

    # Read the first 16 chars directly rather than splitting on
    # "/" -- at wide counters the label's own room drops below 2
    # and the "/label" field disappears entirely.
    #
    # See the dedicated boundary tests below; a split-based
    # check would silently stop proving anything past that
    # point.
    local actual; actual=$(window_name)
    local root_segment=${actual:0:16}
    assert_eq \
      "TmuxWindowTitle > cap > should keep the root at 16 chars for a $((digit_count + 2))-char counter width" \
      "aaaaaaaaaaaaaaaa" "$root_segment"
  done
  stop_server
}

it_should_cut_the_base_to_sixteen_before_appending_the_counter_when_unrooted() {
  start_server

  # No root ever frozen (no --bump-counter).
  #
  # Injecting a [3+2] counter directly onto the unrooted pane,
  # then a 20-char base: the base still cuts to its full 16-char
  # room, unaffected by the counter's width, and the counter is
  # appended whole.
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "seed[3+2]"
  title "abcdefghijklmnopqrst"

  assert_eq \
    "TmuxWindowTitle > cap > should cut an unrooted base to 16 chars before appending the counter" \
    "abcdefghijklmnop[3+2]" "$(window_name)"
  stop_server
}

it_should_survive_an_absurdly_wide_counter_that_alone_exceeds_the_cap() {
  start_server

  title "aaaa-bbbb-cccc-d"
  title --bump-counter
  local absurd="123456789012345678901234567890"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "aaaa-bbbb-cccc-d[${absurd}]"
  set_last_title "aaaa-bbbb-cccc-d[${absurd}]"

  local status=0
  title "eeee-ffff-gggg-h" >/dev/null 2>&1 || status=$?

  assert_eq \
    "TmuxWindowTitle > cap > should not crash when the counter suffix alone already exceeds the cap" \
    "0" "$status"

  assert_eq \
    "TmuxWindowTitle > cap > should drop the text entirely rather than mangle it when the counter alone overflows the cap" \
    "[${absurd}]" "$(window_name)"
  stop_server
}

# No --bump-counter here on purpose: an unrooted title has no
# head/tail split to fall back on, so this pins down the single
# `head_room` clamp render_title applies to every path alike.
it_should_survive_an_absurdly_wide_counter_with_no_root_frozen() {
  start_server

  local absurd="123456789012345678901234567890"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "seed[${absurd}]"

  local stderr_out
  stderr_out=$(title "newbase" 2>&1 >/dev/null)

  assert_eq \
    "TmuxWindowTitle > cap > should not print a bash substring error when an unrooted counter alone overflows the cap" \
    "" "$stderr_out"

  assert_eq \
    "TmuxWindowTitle > cap > should drop the text entirely rather than mangle it when there is no root to fall back on" \
    "[${absurd}]" "$(window_name)"
  stop_server
}

it_should_render_a_single_label_char_at_a_fourteen_char_counter_width() {
  start_server

  # W=14 (a 12-digit injected body) leaves label_room at exactly
  # 2 -- "/" plus one label char, the narrowest width that still
  # renders a label field at all.
  title "aaaaaaaaaaaaaaaa"
  title --bump-counter
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "aaaaaaaaaaaaaaaa[123456789012]"
  set_last_title "aaaaaaaaaaaaaaaa[123456789012]"
  title "bbbbbbbbbbbbbbbb"

  assert_eq \
    "TmuxWindowTitle > cap > should render a single label char at a 14-char counter width" \
    "aaaaaaaaaaaaaaaa/b[123456789012]" "$(window_name)"
  stop_server
}

it_should_drop_the_label_entirely_at_a_fifteen_char_counter_width() {
  start_server

  # W=15 (a 13-digit injected body) drops label_room to 1 --
  # below the 2-char floor -- so the label field is dropped
  # entirely rather than rendering a dangling "/".
  title "aaaaaaaaaaaaaaaa"
  title --bump-counter
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "aaaaaaaaaaaaaaaa[1234567890123]"
  set_last_title "aaaaaaaaaaaaaaaa[1234567890123]"
  title "bbbbbbbbbbbbbbbb"

  assert_eq \
    "TmuxWindowTitle > cap > should drop the label entirely at a 15-char counter width" \
    "aaaaaaaaaaaaaaaa[1234567890123]" "$(window_name)"
  stop_server
}

it_should_clamp_the_head_room_to_zero_without_negative_width_at_a_wide_counter() {
  start_server

  title "aaaaaaaaaaaaaaaa"
  title --bump-counter

  # A 20-digit main count (W=22) steals 6 chars from the head's
  # 16-char room (16 - (22-16) = 10), while the label_room clamp
  # (16 - 22, floored at 0) drops the label entirely.
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "aaaaaaaaaaaaaaaa[12345678901234567890]"
  set_last_title "aaaaaaaaaaaaaaaa[12345678901234567890]"
  title "bbbbbbbbbbbbbbbb"

  assert_eq \
    "TmuxWindowTitle > cap > should clamp the head room without going negative at a wide counter" \
    "aaaaaaaaaa[12345678901234567890]" "$(window_name)"
  stop_server
}

# seed_rooted_window - put the pane in the state the script
# itself leaves after a main compaction: `root` frozen, and
# `last_name` both shown by the window and recorded as the last
# title the script wrote.
seed_rooted_window() {
  local root=$1 last_name=$2
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "$last_name"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_prev_window_name" "zsh"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_root_title" "$root"
  set_last_title "$last_name"
}

# root_option - the frozen root stored on the pane under test.
root_option() {
  tmux -L "$SOCK" show-options -p -t "$TMUX_PANE" -v "@claude_root_title" 2>/dev/null
}

it_should_render_ebs_report_27_plus_2_when_a_main_bump_lands_on_a_pre_rollout_counter() {
  start_server

  # A window opened before rollout: the name carries the
  # counter and no last title was ever recorded.
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "ebs-report[26+2]"
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should render ebs-report[27+2] when a main bump lands on a pre-rollout ebs-report[26+2]" \
    "ebs-report[27+2]" "$(window_name)"
  stop_server
}

it_should_render_dot_payments_3_when_a_main_bump_follows_a_hand_rename_of_a_rooted_window() {
  start_server
  seed_rooted_window ".billing" ".billing/retry-fix[2]"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".payments"

  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should render .payments[3] when a main bump follows a hand rename of a rooted window to .payments" \
    ".payments[3]" "$(window_name)"
  stop_server
}

it_should_render_dot_payments_2_plus_1_when_a_subagent_bump_follows_the_hand_rename() {
  start_server
  seed_rooted_window ".billing" ".billing/retry-fix[2]"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".payments"

  title --bump-subagent-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should render .payments[2+1] when a subagent bump follows the hand rename to .payments" \
    ".payments[2+1]" "$(window_name)"
  stop_server
}

it_should_render_dot_payments_ledger_fix_when_claude_sets_a_tail_after_the_hand_rename() {
  start_server
  seed_rooted_window ".billing" ".billing/retry-fix[2]"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".payments"

  title "ledger-fix"

  assert_eq \
    "TmuxWindowTitle > stored state > should render .payments/ledger-fix[2] when Claude sets a tail after the hand rename to .payments" \
    ".payments/ledger-fix[2]" "$(window_name)"
  stop_server
}

it_should_render_payments_ledger_fix_when_the_hand_rename_drops_the_dot() {
  start_server
  seed_rooted_window ".billing" ".billing/retry-fix[2]"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "payments"

  title "ledger-fix"

  assert_eq \
    "TmuxWindowTitle > stored state > should render payments/ledger-fix[2] when the hand rename drops the dot" \
    "payments/ledger-fix[2]" "$(window_name)"
  stop_server
}

it_should_fold_a_slash_and_cap_the_root_at_sixteen_chars_counting_a_leading_dot() {
  start_server

  # Claude titles the window first, so the script holds a last
  # title; the hand rename then differs from it.
  title "retry-fix"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "billing/payments-v2-migration"
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should fold a slash and cap the root at 16 chars for a hand-set name without a leading dot" \
    "billing-payments" "$(root_option)"
  stop_server

  start_server
  title "retry-fix"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".billing/payments-v2-migration"
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should fold a slash and cap the root at 16 chars counting the leading dot" \
    ".billing-payment" "$(root_option)"
  stop_server
}

it_should_keep_a_sixteen_char_root_whole_and_cut_a_seventeen_char_root_to_sixteen() {
  start_server
  title "retry-fix"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "billing-payments"
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should keep a 16-char hand-set root whole" \
    "billing-payments" "$(root_option)"
  stop_server

  start_server
  title "retry-fix"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "billing-payments2"
  title --bump-counter

  assert_eq \
    "TmuxWindowTitle > stored state > should cut a 17-char hand-set root to 16" \
    "billing-payments" "$(root_option)"
  stop_server
}

it_should_take_a_whole_hand_set_name_with_a_slash_as_root_after_a_main_compaction() {
  start_server
  seed_rooted_window "billing" "billing/retry-fix[2]"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "billing/payments"

  title "ledger"

  assert_eq \
    "TmuxWindowTitle > stored state > should take a whole hand-set name with a slash as root after a main compaction" \
    "billing-payments/ledger[2]" "$(window_name)"
  stop_server
}

it_should_keep_deps_7_as_root_and_render_the_counter_after_the_tail() {
  start_server
  seed_rooted_window "billing" "billing/retry-fix[2]"
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "deps[7]"

  title "ledger"

  assert_eq \
    "TmuxWindowTitle > stored state > should keep deps[7] as the stored root, since the last title and not the live name holds the count" \
    "deps[7]" "$(root_option)"

  assert_eq \
    "TmuxWindowTitle > stored state > should render the counter after the tail as deps[7]/ledger[2]" \
    "deps[7]/ledger[2]" "$(window_name)"
  stop_server
}

it_should_freeze_city_code_as_root_at_the_first_main_compaction() {
  start_server
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".city-code"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_prev_window_name" "zsh"
  set_last_title ".city-code"

  title --bump-counter
  title "retry-fix"

  assert_eq \
    "TmuxWindowTitle > stored state > should freeze .city-code as root at the first main compaction (window name)" \
    ".city-code/retry-fix[1]" "$(window_name)"
  assert_eq \
    "TmuxWindowTitle > stored state > should freeze .city-code as root at the first main compaction (stored root)" \
    ".city-code" "$(root_option)"
  stop_server
}

it_should_freeze_a_dotted_pre_claude_name_as_root_despite_the_pre_claude_name_guard() {
  start_server

  # The pre-Claude name IS the dotted label, the exact case the
  # guard against rooting to "zsh/" would otherwise swallow.
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".city-code"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_prev_window_name" ".city-code"
  set_last_title ".city-code"

  title --bump-counter
  title "retry-fix"

  assert_eq \
    "TmuxWindowTitle > stored state > should freeze a dotted pre-Claude name as root despite the pre-Claude-name guard" \
    ".city-code/retry-fix[1]" "$(window_name)"
  stop_server
}

it_should_freeze_a_lone_dot_as_root_and_render_dot_slash_retry_fix() {
  start_server
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "."
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_prev_window_name" "."
  set_last_title "."

  title --bump-counter
  title "retry-fix"

  assert_eq \
    "TmuxWindowTitle > stored state > should freeze a lone dot as root and render ./retry-fix[1] (window name)" \
    "./retry-fix[1]" "$(window_name)"
  assert_eq \
    "TmuxWindowTitle > stored state > should freeze a lone dot as root and render ./retry-fix[1] (stored root)" \
    "." "$(root_option)"
  stop_server
}

it_should_set_the_tail_on_every_call_after_a_main_compaction_with_no_refusal_note() {
  start_server
  seed_rooted_window "billing" "billing/retry-fix[1]"

  local first_err second_err
  first_err=$(title "ledger-fix" 2>&1 >/dev/null)
  assert_eq \
    "TmuxWindowTitle > stored state > should set the first new tail after a main compaction" \
    "billing/ledger-fix[1]" "$(window_name)"
  second_err=$(title "audit" 2>&1 >/dev/null)
  assert_eq \
    "TmuxWindowTitle > stored state > should set the second new tail after a main compaction" \
    "billing/audit[1]" "$(window_name)"
  assert_eq \
    "TmuxWindowTitle > stored state > should write no refusal note on either tail after a main compaction" \
    "" "${first_err}${second_err}"
  stop_server
}

it_should_freeze_the_first_title_after_a_rootless_first_main_compaction_as_root() {
  start_server

  # The window still shows its pre-Claude name at the bump, so
  # the bump freezes nothing.
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "zsh"
  title --bump-counter

  title "billing"
  title "retry-fix"

  assert_eq \
    "TmuxWindowTitle > stored state > should freeze the first title after a rootless first main compaction as root (stored root)" \
    "billing" "$(root_option)"
  assert_eq \
    "TmuxWindowTitle > stored state > should freeze the first title after a rootless first main compaction as root (window name)" \
    "billing/retry-fix[1]" "$(window_name)"
  stop_server
}

it_should_print_the_session_goal_first_note_on_stdout_when_a_main_bump_freezes_no_root() {
  start_server
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "zsh"

  local out
  out=$(title --bump-counter 2>/dev/null)

  local mentions_goal=no
  case "$out" in *"session goal"*) mentions_goal=yes ;; esac
  assert_eq \
    "TmuxWindowTitle > bump note > should tell Claude to pass the session goal first when no root froze" \
    "yes" "$mentions_goal"
  stop_server
}

it_should_print_no_note_when_the_main_bump_freezes_a_root_or_finds_one_already_frozen() {
  start_server
  title "billing"
  local out
  out=$(title --bump-counter 2>/dev/null)
  assert_eq \
    "TmuxWindowTitle > bump note > should print no note when the bump freezes a root" \
    "" "$out"
  stop_server

  start_server
  title "billing"
  tmux -L "$SOCK" set-option -p -t "$TMUX_PANE" "@claude_root_title" "billing"
  out=$(title --bump-counter 2>/dev/null)
  assert_eq \
    "TmuxWindowTitle > bump note > should print no note when a root is already frozen" \
    "" "$out"
  stop_server
}

it_should_strip_every_leading_dot_when_claude_passes_a_dotted_title() {
  local dotted
  for dotted in ".billing" "..billing" ".-billing" " .billing" "/.billing"; do
    start_server
    tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "zsh"

    title "$dotted"

    assert_eq \
      "TmuxWindowTitle > stored state > should strip every leading dot when Claude passes '$dotted'" \
      "billing" "$(window_name)"
    stop_server
  done
}

it_should_exit_1_and_leave_zsh_when_claude_passes_a_lone_dot() {
  start_server
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" "zsh"

  local status=0
  title "." >/dev/null 2>&1 || status=$?

  assert_eq \
    "TmuxWindowTitle > stored state > should exit 1 when Claude passes a lone dot" \
    "1" "$status"
  assert_eq \
    "TmuxWindowTitle > stored state > should leave zsh when Claude passes a lone dot" \
    "zsh" "$(window_name)"
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

it_should_shed_a_split_counter_and_release_the_root_on_reset() {
  start_server

  title "auth-fix"
  title --bump-counter
  title --bump-subagent-counter
  title "db-store"
  title --reset-counter

  assert_eq \
    "TmuxWindowTitle > reset > should shed both halves of a split [M+S] counter on reset" \
    "db-store" "$(window_name)"

  title --bump-counter
  title "api-cache"

  # The released root must not still be "auth-fix" -- the
  # post-reset base ("db-store", untruncated since it fits the
  # tail's 16-char room) becomes the next root instead.
  assert_eq \
    "TmuxWindowTitle > reset > should release the frozen root so the post-reset base becomes the next root" \
    "db-store/api-cache[1]" "$(window_name)"
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

  # The new root is "db-store" (the post-reset base, untruncated
  # since it fits the tail's 16-char room), the title the pane
  # carried when the reset landed - not the released "auth-fix".
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
  # early - the root must already have been released.
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

# first_title_flag - the pane option marking that this session's
# first title was spent; empty when unset.
first_title_flag() {
  tmux -L "$SOCK" show-options -p -t "$TMUX_PANE" -v "@claude_first_title_used" 2>/dev/null
}

it_should_set_the_first_title_with_no_refusal_note_when_the_window_shows_its_pre_claude_name() {
  start_server

  local err status=0
  err=$(title "city-code" 2>&1 >/dev/null) || status=$?

  assert_eq \
    "TmuxWindowTitle > first title > should set the first title with no refusal note when the window shows its pre-Claude name" \
    "city-code|0||1" "$(window_name)|$status|$err|$([ -n "$(first_title_flag)" ] && echo 1)"
  stop_server
}

it_should_refuse_a_second_title_before_the_first_main_compaction_with_exit_0_and_the_note() {
  start_server

  title "city-code"
  local err status=0
  err=$(title "retry-fix" 2>&1 >/dev/null) || status=$?

  local has_note=no
  case "$err" in *"expected"*"Do not retry"*) has_note=yes ;; esac

  assert_eq \
    "TmuxWindowTitle > first title > should refuse a second title before the first main compaction with exit 0 and the note" \
    "city-code|0|yes" "$(window_name)|$status|$has_note"
  stop_server
}

it_should_leave_a_dotted_window_unchanged_and_exit_0_with_the_expected_refusal_note() {
  start_server
  tmux -L "$SOCK" rename-window -t "$TMUX_PANE" ".city-code"

  local err status=0
  err=$(title "retry-fix" 2>&1 >/dev/null) || status=$?

  local has_note=no
  case "$err" in *"expected"*"Do not retry"*) has_note=yes ;; esac

  assert_eq \
    "TmuxWindowTitle > dotted window > should leave .city-code unchanged and exit 0 with the expected-refusal note" \
    ".city-code|0|yes" "$(window_name)|$status|$has_note"
  stop_server
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
  echo "tmux not installed - cannot exercise tmux-window-title.sh" >&2
  exit 1
fi

it_should_set_a_plain_title_before_any_compaction
it_should_hyphenate_whitespace_in_a_title
it_should_start_the_counter_at_one_on_the_first_compaction
it_should_increment_the_counter_on_later_compactions
it_should_render_a_subagent_bump_alone_as_zero_plus_one
it_should_render_main_then_subagent_bumps_as_one_plus_one
it_should_render_subagent_then_main_bumps_as_one_plus_one
it_should_render_two_subagent_bumps_as_zero_plus_two
it_should_preserve_a_split_counter_across_a_retitle
it_should_root_a_retitle_that_follows_a_compaction
it_should_freeze_the_root_at_the_last_pre_compaction_title
it_should_keep_the_root_stable_across_later_compactions
it_should_keep_the_root_immutable_across_many_retitles
it_should_not_drop_root_words_from_the_compact_focus_label
it_should_not_render_bare_when_the_compact_focus_label_merely_contains_root_words
it_should_render_bare_when_the_title_matches_the_root
it_should_fold_a_caller_supplied_separator_into_a_hyphen
it_should_not_root_a_pane_claude_never_titled
it_should_freeze_the_root_at_the_title_current_when_the_main_bump_lands
it_should_cap_a_plain_title_at_sixteen_chars
it_should_cap_a_rooted_title_at_thirtytwo_chars_including_the_counter
it_should_not_reallocate_a_short_root_s_unused_room_to_the_compact_focus_label
it_should_keep_the_counter_whole_when_truncating
it_should_drop_a_trailing_hyphen_left_by_truncating_the_label
it_should_drop_a_trailing_hyphen_left_by_truncating_the_root
it_should_keep_a_split_counter_suffix_whole_when_truncating
it_should_keep_the_root_at_sixteen_chars_for_every_counter_width_up_to_sixteen
it_should_cut_the_base_to_sixteen_before_appending_the_counter_when_unrooted
it_should_survive_an_absurdly_wide_counter_that_alone_exceeds_the_cap
it_should_survive_an_absurdly_wide_counter_with_no_root_frozen
it_should_render_a_single_label_char_at_a_fourteen_char_counter_width
it_should_drop_the_label_entirely_at_a_fifteen_char_counter_width
it_should_clamp_the_head_room_to_zero_without_negative_width_at_a_wide_counter
it_should_render_ebs_report_27_plus_2_when_a_main_bump_lands_on_a_pre_rollout_counter
it_should_render_dot_payments_3_when_a_main_bump_follows_a_hand_rename_of_a_rooted_window
it_should_render_dot_payments_2_plus_1_when_a_subagent_bump_follows_the_hand_rename
it_should_render_dot_payments_ledger_fix_when_claude_sets_a_tail_after_the_hand_rename
it_should_render_payments_ledger_fix_when_the_hand_rename_drops_the_dot
it_should_fold_a_slash_and_cap_the_root_at_sixteen_chars_counting_a_leading_dot
it_should_keep_a_sixteen_char_root_whole_and_cut_a_seventeen_char_root_to_sixteen
it_should_take_a_whole_hand_set_name_with_a_slash_as_root_after_a_main_compaction
it_should_keep_deps_7_as_root_and_render_the_counter_after_the_tail
it_should_freeze_city_code_as_root_at_the_first_main_compaction
it_should_freeze_a_dotted_pre_claude_name_as_root_despite_the_pre_claude_name_guard
it_should_freeze_a_lone_dot_as_root_and_render_dot_slash_retry_fix
it_should_set_the_tail_on_every_call_after_a_main_compaction_with_no_refusal_note
it_should_freeze_the_first_title_after_a_rootless_first_main_compaction_as_root
it_should_print_the_session_goal_first_note_on_stdout_when_a_main_bump_freezes_no_root
it_should_print_no_note_when_the_main_bump_freezes_a_root_or_finds_one_already_frozen
it_should_strip_every_leading_dot_when_claude_passes_a_dotted_title
it_should_exit_1_and_leave_zsh_when_claude_passes_a_lone_dot
it_should_drop_the_counter_and_the_root_on_reset
it_should_shed_a_split_counter_and_release_the_root_on_reset
it_should_let_a_new_root_be_frozen_after_a_reset
it_should_release_the_root_even_when_no_counter_is_present
it_should_leave_an_untitled_window_alone_on_reset
it_should_reject_a_title_that_sanitizes_to_nothing
it_should_reject_a_missing_title
it_should_no_op_outside_tmux
it_should_print_help_to_stdout
it_should_set_the_first_title_with_no_refusal_note_when_the_window_shows_its_pre_claude_name
it_should_refuse_a_second_title_before_the_first_main_compaction_with_exit_0_and_the_note
it_should_leave_a_dotted_window_unchanged_and_exit_0_with_the_expected_refusal_note

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
