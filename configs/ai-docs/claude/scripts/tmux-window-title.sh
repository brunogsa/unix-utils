#!/bin/bash
# tmux-window-title - Set the current tmux window's title to a given string.
#
# Claude Code calls this to label the window with a brief title of the current
# work, so the user can find the right window at a glance. It overwrites the
# title outright -- no prefixes, no stacking (that policy lives with the caller,
# not here).
#
# Usage:
#   tmux-window-title.sh <title>       # set the base title
#   tmux-window-title.sh --bump-counter  # +1 to the compaction counter
#   tmux-window-title.sh --reset-counter # drop the compaction counter
#   tmux-window-title.sh --help
#
# Compaction counter:
#   The title carries an optional trailing "[N]" -- the number of context
#   compactions this Claude session has survived, e.g. "auth-fix[3]". It gives
#   the user at-a-glance visibility into how churned a session's context is.
#   The count lives in the title itself (single source of truth), managed by
#   SessionStart hooks: --bump-counter on `compact`, --reset-counter on
#   `startup`/`clear`. Setting a base title PRESERVES an existing counter, so
#   Claude re-titling on a topic shift does not reset the count.
#
# Behavior:
#   - Outside tmux ($TMUX unset): no-op, exit 0. Lets the caller invoke it
#     unconditionally without guarding on the terminal.
#   - Empty/missing title (default mode): error to stderr, exit 1.
#   - Sets `automatic-rename off` first, because with it on (the user's default)
#     tmux re-derives the name from the running command and the title would not
#     stick.
#   - Renames the window that Claude runs in ($TMUX_PANE), not whatever window
#     is currently focused.
#   - Caps the whole title at 16 chars. The counter suffix is kept intact and
#     the base is truncated to fit, so the count stays readable even as the
#     base shrinks. The caller should already keep titles short.
#   - On the first rename for a pane (any mode), captures the pre-Claude window
#     name and automatic-rename flag into pane options ($TMUX_PANE-scoped
#     @claude_prev_window_name / @claude_prev_auto_rename) before overwriting
#     either -- first-set-wins, so later calls in the same session don't
#     clobber the captured original. A separate SessionEnd hook restores it.
#
# Examples:
#   tmux-window-title.sh "fix-auth-bug"   # spaces are converted to hyphens too
#   tmux-window-title.sh "tmux-titles"
#   tmux-window-title.sh --bump-counter   # "tmux-titles" -> "tmux-titles[1]"
#   tmux-window-title.sh --reset-counter  # "tmux-titles[1]" -> "tmux-titles"

set -euo pipefail

# Print the comment header (lines 2..first non-comment line) as help text,
# stripping the leading "# ". Stops at the first non-# line so it never leaks
# code below the header, regardless of where the header ends.
print_help() {
  awk 'NR==1 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
}

MAX_LEN=16

# Parse a trailing compaction counter "[N]" from a title. Echoes N when
# present, nothing otherwise. Strict -- only digits inside brackets at the very
# end count, so a base title never picks up a stray "[x]" as a counter.
parse_counter() {
  if [[ "$1" =~ \[([0-9]+)\]$ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  fi
}

# Echo the base title with a trailing numeric "[N]" removed (unchanged if none).
strip_counter() {
  if [[ "$1" =~ ^(.*)\[[0-9]+\]$ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  else
    printf '%s' "$1"
  fi
}

# Render "<base>[N]" capped at MAX_LEN. The counter is kept whole and the base
# is truncated to make room, so the count stays visible even as the base
# shrinks. An empty count renders the bare base.
render_title() {
  local base=$1 count=$2 suffix=""
  [ -n "$count" ] && suffix="[$count]"

  local max=$(( MAX_LEN - ${#suffix} ))
  if [ "${#base}" -gt "$max" ]; then
    base="${base:0:max}"
    base="${base%-}"  # drop a trailing hyphen the cut may leave
  fi
  printf '%s%s' "$base" "$suffix"
}

# Read the name of the window Claude runs in ($TMUX_PANE), not whatever window
# is currently focused.
current_title() {
  tmux display-message -t "$TMUX_PANE" -p '#{window_name}'
}

# First-set-wins capture of the window's pre-Claude name and automatic-rename
# flag, into pane options (not window options) so the "original" ties to this
# specific Claude pane/session -- relevant if the window ever holds more than
# one pane. A SessionEnd hook (separate script) reads these back to restore
# the window once Claude's session ends. `show-options -v` on an option that
# was never set exits non-zero with nothing on stdout, and exits 0 with the
# value once it has been -- that's the "already captured?" check below.
capture_prev_state() {
  if tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" >/dev/null 2>&1; then
    return 0  # already captured earlier in this session
  fi

  local prev_name prev_auto
  prev_name=$(current_title)

  # automatic-rename is a window option; an unset local value means the
  # window inherits the global default, so fall back to that -- the restore
  # hook needs a literal "on"/"off" captured here, never an empty string.
  prev_auto=$(tmux show-options -w -t "$TMUX_PANE" -v automatic-rename)
  if [ -z "$prev_auto" ]; then
    prev_auto=$(tmux show-options -g -v automatic-rename)
  fi

  tmux set-option -p -t "$TMUX_PANE" -- "@claude_prev_window_name" "$prev_name"
  tmux set-option -p -t "$TMUX_PANE" "@claude_prev_auto_rename" "$prev_auto"
}

# Disable auto-rename for this window so the manual name persists, then set it.
# `--` ends option parsing so a title starting with `-` is not read as a flag.
apply_title() {
  tmux set-window-option -t "$TMUX_PANE" automatic-rename off
  tmux rename-window -t "$TMUX_PANE" -- "$1"
}

MODE="${1:-}"

case "$MODE" in
  -h|--help)
    print_help
    exit 0
    ;;
esac

# A missing arg is caller misuse in every mode (the subcommands are non-empty
# strings and a real title is non-empty too) -- flag it even outside tmux.
if [ -z "$MODE" ]; then
  echo "tmux-window-title: missing <title> (try --help)" >&2
  exit 1
fi

# Outside tmux there is no window to title -- succeed silently so the caller
# never has to check. Covers every mode below.
if [ -z "${TMUX:-}" ] || [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

case "$MODE" in
  --bump-counter)
    # A compaction happened: increment the counter (absent -> starts at 1).
    current=$(current_title)
    base=$(strip_counter "$current")
    count=$(parse_counter "$current")
    next=$(( ${count:-0} + 1 ))
    capture_prev_state
    apply_title "$(render_title "$base" "$next")"
    ;;

  --reset-counter)
    # /clear or a fresh start: drop the counter. With no counter present, leave
    # the window name alone -- it's the user's shell title, not one of ours.
    current=$(current_title)
    if [ -z "$(parse_counter "$current")" ]; then
      exit 0
    fi
    base=$(strip_counter "$current")
    capture_prev_state
    apply_title "$(render_title "$base" "")"
    ;;

  *)
    # Default mode: set the base title, preserving any counter already on the
    # window so a mid-session re-title (topic shift) keeps the count.
    #
    # Drop control chars (a raw newline corrupts the tmux status line), turn
    # any whitespace run into a single "-" (hyphens read cleaner than spaces
    # in a tab bar), collapse repeated hyphens, and trim leading/trailing.
    clean=$(printf '%s' "$MODE" | tr -d '\000-\037' | sed -E 's/[[:space:]]+/-/g; s/-+/-/g; s/^-+//; s/-+$//')

    if [ -z "$clean" ]; then
      echo "tmux-window-title: <title> is empty after sanitizing" >&2
      exit 1
    fi

    existing=$(parse_counter "$(current_title)")
    capture_prev_state
    apply_title "$(render_title "$clean" "$existing")"
    ;;
esac
