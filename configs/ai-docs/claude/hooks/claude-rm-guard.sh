#!/bin/bash
# claude-rm-guard - Block rm -rf outside git repos, suggest trash
#
# Usage (Claude Code PreToolUse hook):
#   Reads JSON from stdin, exits 2 to block (non-git), 0 to allow (git)
#
# Rationale:
#   Inside git repos, deleted files are recoverable via git checkout/restore.
#   Outside git repos, rm -rf is truly destructive — use trash instead.
#
# Examples:
#   # In a git repo:
#   echo '{"tool_input":{"command":"rm -rf node_modules"}}' | bash claude-rm-guard.sh  # allowed
#   # Outside a git repo:
#   echo '{"tool_input":{"command":"rm -rf /tmp/data"}}' | bash claude-rm-guard.sh     # blocked

CMD=$(jq -r '.tool_input.command // empty')

if [ -z "$CMD" ]; then
  exit 0
fi

# Only guard rm -rf / rm -fr patterns
if ! echo "$CMD" | grep -qE '\brm\s+-(rf|fr)\b'; then
  exit 0
fi

# Allow inside git repos — files are recoverable
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

echo 'rm -rf is non-reversible outside a git repo. Use "trash" instead (npm install -g trash-cli). If you really need rm -rf, ask the user.' >&2
exit 2
