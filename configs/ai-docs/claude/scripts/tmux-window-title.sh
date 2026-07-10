#!/bin/bash
# tmux-window-title - Set the current tmux window's title to a given string.
#
# Claude Code calls this to label the window with a brief title of the current
# work, so the user can find the right window at a glance. It overwrites the
# title outright -- no prefixes, no stacking (that policy lives with the caller,
# not here).
#
# Usage:
#   tmux-window-title.sh <title>
#   tmux-window-title.sh --help
#
# Behavior:
#   - Outside tmux ($TMUX unset): no-op, exit 0. Lets the caller invoke it
#     unconditionally without guarding on the terminal.
#   - Empty/missing title: error to stderr, exit 1.
#   - Sets `automatic-rename off` first, because with it on (the user's default)
#     tmux re-derives the name from the running command and the title would not
#     stick.
#   - Renames the window that Claude runs in ($TMUX_PANE), not whatever window
#     is currently focused.
#   - Caps the title at 16 chars (truncates) so several titled tabs fit
#     comfortably side by side. The caller should already keep titles short.
#   - On the first call for a pane, captures the pre-Claude window name and
#     automatic-rename flag into pane options ($TMUX_PANE-scoped
#     @claude_prev_window_name / @claude_prev_auto_rename) before overwriting
#     either -- first-set-wins, so later calls in the same session don't
#     clobber the captured original. A separate SessionEnd hook restores it.
#
# Examples:
#   tmux-window-title.sh "fix-auth-bug"   # spaces are converted to hyphens too
#   tmux-window-title.sh "tmux-titles"

set -euo pipefail

# Print the comment header (lines 2..first non-comment line) as help text,
# stripping the leading "# ". Stops at the first non-# line so it never leaks
# code below the header, regardless of where the header ends.
print_help() {
  awk 'NR==1 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
}

case "${1:-}" in
  -h|--help)
    print_help
    exit 0
    ;;
esac

TITLE="${1:-}"

if [ -z "$TITLE" ]; then
  echo "tmux-window-title: missing <title> (try --help)" >&2
  exit 1
fi

# Outside tmux there is no window to title -- succeed silently so the caller
# never has to check.
if [ -z "${TMUX:-}" ] || [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

# Drop control chars (a raw newline corrupts the tmux status line), turn any
# whitespace run into a single "-" (hyphens read cleaner than spaces in a tab
# bar), collapse repeated hyphens, and trim leading/trailing hyphens.
CLEAN_TITLE=$(printf '%s' "$TITLE" | tr -d '\000-\037' | sed -E 's/[[:space:]]+/-/g; s/-+/-/g; s/^-+//; s/-+$//')

if [ -z "$CLEAN_TITLE" ]; then
  echo "tmux-window-title: <title> is empty after sanitizing" >&2
  exit 1
fi

# Cap length so several titled tabs stay readable side by side. This is a
# safety net -- the caller is asked to keep titles short -- so it truncates
# silently rather than erroring.
MAX_LEN=16
if [ "${#CLEAN_TITLE}" -gt "$MAX_LEN" ]; then
  CLEAN_TITLE="${CLEAN_TITLE:0:MAX_LEN}"
  CLEAN_TITLE="${CLEAN_TITLE%-}"  # drop a trailing hyphen the cut may leave
fi

# First-set-wins capture of the window's pre-Claude name and automatic-rename
# flag, into pane options (not window options) so the "original" ties to this
# specific Claude pane/session -- relevant if the window ever holds more than
# one pane. A SessionEnd hook (separate script) reads these back to restore
# the window once Claude's session ends. `show-options -v` on an option that
# was never set exits non-zero with nothing on stdout, and exits 0 with the
# value once it has been -- that's the "already captured?" check below.
if ! tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" >/dev/null 2>&1; then
  PREV_WINDOW_NAME=$(tmux display-message -t "$TMUX_PANE" -p '#{window_name}')

  # automatic-rename is a window option; an unset local value means the
  # window inherits the global default, so fall back to that -- the restore
  # hook needs a literal "on"/"off" captured here, never an empty string.
  PREV_AUTO_RENAME=$(tmux show-options -w -t "$TMUX_PANE" -v automatic-rename)
  if [ -z "$PREV_AUTO_RENAME" ]; then
    PREV_AUTO_RENAME=$(tmux show-options -g -v automatic-rename)
  fi

  tmux set-option -p -t "$TMUX_PANE" -- "@claude_prev_window_name" "$PREV_WINDOW_NAME"
  tmux set-option -p -t "$TMUX_PANE" "@claude_prev_auto_rename" "$PREV_AUTO_RENAME"
fi

# Disable auto-rename for this window so the manual name persists, then set it.
# `--` ends option parsing so a title starting with `-` is not read as a flag.
tmux set-window-option -t "$TMUX_PANE" automatic-rename off
tmux rename-window -t "$TMUX_PANE" -- "$CLEAN_TITLE"
