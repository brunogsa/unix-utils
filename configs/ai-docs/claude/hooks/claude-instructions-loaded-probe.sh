#!/bin/bash
# claude-instructions-loaded-probe - TEMPORARY diagnostic for the compaction-level spike (task #52).
#
# Usage (Claude Code InstructionsLoaded hook):
#   Reads JSON from stdin, appends one line per instruction-file load, always exits 0.
#
# Answers the question the spike is blocked on, which the docs leave unstated:
# which CLAUDE.md files reload at load_reason=compact? The docs promise only
# that PROJECT-ROOT CLAUDE.md is re-read from disk after compaction, and say
# nested ones are not. User-scope (~/.claude/CLAUDE.md) is unstated -- yet the
# whole "# Compact instructions" lever depends on the file being re-read.
#
# A second question (are @imports re-expanded on that reload?) is moot: the
# global CLAUDE.md now bans @-imported auto-loaded files outright, so no design
# can depend on the answer.
#
# InstructionsLoaded is side-effects-only (exit code ignored, cannot alter or
# suppress instructions), so this cannot affect a session -- it only observes.
#
# Delete this hook and its settings.json entry once the log has answered it.

LOG=/tmp/claude-instructions-loaded-probe.log

INPUT=$(cat)

# Missing jq must not turn a diagnostic into a broken session.
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

load_reason=$(printf '%s' "$INPUT" | jq -r '.load_reason // "unknown"' 2>/dev/null)
file_path=$(printf '%s' "$INPUT" | jq -r '.instruction_file_path // "unknown"' 2>/dev/null)
content=$(printf '%s' "$INPUT" | jq -r '.instruction_content // ""' 2>/dev/null)

content_chars=${#content}

printf '%s\treason=%s\tchars=%s\tfile=%s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  "$load_reason" \
  "$content_chars" \
  "$file_path" >> "$LOG"

exit 0
