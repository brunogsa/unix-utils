#!/bin/bash
# claude-instructions-loaded-probe - TEMPORARY diagnostic for the compaction-level spike (task #52).
#
# Usage (Claude Code InstructionsLoaded hook):
#   Reads JSON from stdin, appends one line per instruction load, always exits 0.
#
# Answers the question the spike is blocked on, which the docs leave unstated:
# which CLAUDE.md files reload at load_reason=compact? The docs promise only
# that PROJECT-ROOT CLAUDE.md is re-read from disk after compaction, and say
# nested ones are not. User-scope (~/.claude/CLAUDE.md) is unstated -- yet the
# whole "# Compact instructions" lever depends on the file being re-read.
#
# Every named field logged here was read off a real firing. An earlier version
# read .instruction_file_path and .instruction_content straight from the docs
# and logged "unknown" on every real firing, because the live payload carries
# neither -- the schema has to be observed, not assumed. There is no content
# field at all, so this can report WHICH files reload but never their text.
#
# InstructionsLoaded is side-effects-only (exit code ignored, cannot alter or
# suppress instructions), so this cannot affect a session -- it only observes.
#
# Delete this hook and its settings.json entry once the log has answered it.

LOG=/tmp/claude-instructions-loaded-probe.log

INPUT=$(cat)

raw_bytes=${#INPUT}

# One load must stay one grep-able line, so newlines and tabs become spaces.
flat=$(printf '%s' "$INPUT" | tr '\n\t' '  ')

# The three fields below were read off a real firing, not off the docs, which
# name neither memory_type nor file_path. keys= stays so a schema change shows
# up as a new path rather than as silently-empty values.
# Missing jq must not turn a diagnostic into a broken session.
keys=""
reason=""
scope=""
file=""
if command -v jq >/dev/null 2>&1; then
  keys=$(printf '%s' "$INPUT" | jq -rc '[paths(scalars) | join(".")] | unique | join(",")' 2>/dev/null)
  reason=$(printf '%s' "$INPUT" | jq -rc '.load_reason // ""' 2>/dev/null)
  scope=$(printf '%s' "$INPUT" | jq -rc '.memory_type // ""' 2>/dev/null)
  file=$(printf '%s' "$INPUT" | jq -rc '.file_path // ""' 2>/dev/null)
fi
[ -z "$keys" ] && keys="unparsed"

# raw is truncated because an instruction payload may carry a whole CLAUDE.md.
printf '%s\treason=%s\tscope=%s\tfile=%s\tbytes=%s\tkeys=%s\traw=%.200s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  "$reason" \
  "$scope" \
  "$file" \
  "$raw_bytes" \
  "$keys" \
  "$flat" >> "$LOG"

exit 0
