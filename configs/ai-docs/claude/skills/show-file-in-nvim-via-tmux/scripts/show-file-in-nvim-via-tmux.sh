#!/usr/bin/env bash
# show-file-in-nvim-via-tmux
#
# Open a file at a specific line inside the user's tmux session.
#
# Usage:
#   show-file-in-nvim-via-tmux <mode> <file> <line> [col]
#
# Modes:
#   vertical          Side-by-side split of the current pane.
#   horizontal        Stacked split of the current pane.
#   window            New tmux window.
#   pane:<N>          Replace tmux pane N (smart-detects nvim — preserves jump
#                     list via :edit if nvim is running there, otherwise
#                     respawns the pane with a fresh nvim).
#
# Examples:
#   show-file-in-nvim-via-tmux vertical src/auth.rb 42
#   show-file-in-nvim-via-tmux horizontal "src/long name.rb" 10
#   show-file-in-nvim-via-tmux window src/main.rb 1
#   show-file-in-nvim-via-tmux pane:2 src/repo.rb 88
#
# Exit codes:
#   0  success
#   1  invalid usage, mode, file, or pane number
#   2  not inside a tmux session (fallback nvim command printed on stdout)
#
# Env:
#   TMUX_DRY_RUN=1            print the dispatched tmux command instead of
#                             executing it (used by tests).

set -euo pipefail

usage() {
  awk 'NR==1 && /^#!/ {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
}

die() {
  echo "Error: $*" >&2
  echo "Try --help for usage." >&2
  exit 1
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  '')
    die "Missing <mode>."
    ;;
esac

mode="$1"
file="${2:-}"
line="${3:-}"

[[ -n "$file" ]] || die "Missing <file>."
[[ -n "$line" ]] || die "Missing <line>."
[[ "$line" =~ ^[0-9]+$ ]] || die "Line must be a positive integer; got '$line'."

case "$mode" in
  vertical|horizontal|window)
    ;;
  pane:*)
    pane_n="${mode#pane:}"
    [[ "$pane_n" =~ ^[0-9]+$ ]] || die "Invalid pane number in '$mode'. Expected pane:<digit>."
    ;;
  *)
    die "Invalid mode: '$mode'. Expected vertical | horizontal | window | pane:<N>."
    ;;
esac

[[ -e "$file" ]] || die "File not found: $file"

if [[ -z "${TMUX:-}" ]]; then
  echo "Warning: not inside a tmux session — cannot open a pane." >&2
  echo "nvim +${line} \"${file}\""
  exit 2
fi

nvim_cmd="nvim +$line $file"
tmux_argv=()

case "$mode" in
  vertical)
    tmux_argv=(tmux split-window -h -c "$PWD" "$nvim_cmd")
    ;;
  horizontal)
    tmux_argv=(tmux split-window -v -c "$PWD" "$nvim_cmd")
    ;;
  window)
    tmux_argv=(tmux new-window -c "$PWD" "$nvim_cmd")
    ;;
  pane:*)
    die "Mode 'pane:<N>' not yet implemented (plan task 3)."
    ;;
esac

if [[ "${TMUX_DRY_RUN:-}" == "1" ]]; then
  echo "${tmux_argv[*]}"
  exit 0
fi

"${tmux_argv[@]}"
