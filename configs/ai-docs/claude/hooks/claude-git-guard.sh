#!/bin/bash
# claude-git-guard.sh - Hand the hook payload to the python
# git guard beside this file.
#
# Usage (Claude Code PreToolUse hook, Bash matcher):
#   bash claude-git-guard.sh
#
# stdin: the PreToolUse JSON payload, passed through as is
# stdout/stderr/exit: claude-git-guard.py's own (0 allows,
#   2 blocks)
#
# Delete after 2026-12-01, once no session started before the
# cut-over is still running: such a session still names this
# .sh in its loaded settings.

exec python3 "$(dirname "$0")/claude-git-guard.py"
