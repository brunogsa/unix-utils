#!/usr/bin/env bash
# open-in-tmux
#
# Run any shell command in a new tmux pane, split, or window.
# Common use cases:
#   Review a file:    open-in-tmux vertical "nvim +42 src/auth.ts"
#   Stream output:    open-in-tmux horizontal "tail -f /tmp/build.log"
#   Watch a process:  open-in-tmux window "watch -n2 kubectl get pods"
#
# Usage:
#   open-in-tmux <mode> <command>
#
# Modes:
#   vertical          Side-by-side split of the current pane.
#   horizontal        Stacked split of the current pane.
#   window            New tmux window — leaves the current layout untouched.
#   pane:<N>          Send the command to pane N via send-keys (types it into
#                     the existing shell; preserves pane history and state).
#
# Examples:
#   open-in-tmux vertical "nvim +42 src/auth.ts"
#   open-in-tmux horizontal "tail -f /tmp/build.log"
#   open-in-tmux window "watch -n2 kubectl get pods"
#   open-in-tmux pane:2 "tail -f /tmp/output.txt"
#
# Exit codes:
#   0  success
#   1  invalid usage or mode
#   2  not inside a tmux session (fallback command printed on stdout)
#
# Env:
#   TMUX_DRY_RUN=1   print the dispatched tmux command instead of executing it.

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
shift
command_str="$*"

[[ -n "$command_str" ]] || die "Missing <command>."

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

if [[ -z "${TMUX:-}" ]]; then
  echo "Warning: not inside a tmux session — cannot open a pane." >&2
  echo "$command_str"
  exit 2
fi

tmux_argv=()

case "$mode" in
  vertical)
    tmux_argv=(tmux split-window -h -c "$PWD" "$command_str")
    ;;
  horizontal)
    tmux_argv=(tmux split-window -v -c "$PWD" "$command_str")
    ;;
  window)
    tmux_argv=(tmux new-window -c "$PWD" "$command_str")
    ;;
  pane:*)
    tmux_argv=(tmux send-keys -t "$pane_n" "$command_str" Enter)
    ;;
esac

if [[ "${TMUX_DRY_RUN:-}" == "1" ]]; then
  echo "${tmux_argv[*]}"
else
  "${tmux_argv[@]}"
fi

echo "Pane opened. Wait for the user's next message before any further action. If they signal they edited the file, re-read it and diff-summarize the changes."
