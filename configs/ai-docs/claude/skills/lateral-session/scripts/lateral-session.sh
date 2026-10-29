#!/usr/bin/env bash
# Opens a new tmux window in <repo-dir> running claude with the
# contents of <prompt-file> as its first message.
#
# Usage: lateral-session.sh <repo-dir> <prompt-file>.
#
# Exits 2 with a `lateral-session: refused` stderr prefix when
# $TMUX is unset; no window opens.
#
# Fire-and-forget: no stdout, and tmux's exit code and stderr
# pass through on failure.

repo_dir="$1"
prompt_file="$2"

if [ -z "${TMUX:-}" ]; then
  echo "lateral-session: refused - not inside tmux" >&2
  exit 2
fi

# `--` keeps a prompt starting with `-` from being parsed as a
# claude option. The prompt travels by file path in the window
# environment, so its bytes never pass through tmux quoting.
exec tmux new-window -c "$repo_dir" \
  -e "LATERAL_PROMPT_FILE=$prompt_file" \
  'claude -- "$(cat "$LATERAL_PROMPT_FILE")"'
