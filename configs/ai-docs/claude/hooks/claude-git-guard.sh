#!/bin/bash
# claude-git-guard.sh - Hand the hook payload to the python
# git guard beside this file.
#
# Usage (Claude Code PreToolUse hook, Bash matcher):
#   bash claude-git-guard.sh
#
# stdin: the PreToolUse JSON payload, passed through as is
# stdout/stderr: claude-git-guard.py's own
# exit: 0 when the guard allows, else 2 (blocks, crash
#   included)
#
# Delete after 2026-12-01, once no session started before the
# cut-over is still running: such a session still names this
# .sh in its loaded settings.

# Claude Code blocks only on exit 2, so a guard crash (python
# exits 1) must still block the call.
python3 "$(dirname "$0")/claude-git-guard.py" || exit 2
