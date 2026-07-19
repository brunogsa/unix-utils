#!/bin/bash
# PreToolUse guard for the deep-reviewer subagent (referenced from its frontmatter).
#
# deep-reviewer is a read-only judge. Its write affordances are exactly two:
#   1. persisting its own verdict to a caller-assigned `verdict_*.md` file, and
#   2. scratch under /tmp — the review pipeline (auto-review) persists its wave
#      artifacts to a mktemp dir there, and /tmp is never repo source.
# This guard enforces that at the tool layer: a Write/Edit to `verdict_*.md` or to
# a path under /tmp is auto-approved (so an unattended background subagent needs
# no interactive prompt); every other Write/Edit is denied (so it can never touch
# repo source, even under a bypassPermissions parent).
#
# Why `verdict_` and not `report_`/`findings_`: the Claude Code harness itself
# intercepts any subagent Write whose basename starts with `report_` or
# `findings_`, before this hook ever runs, and silently substitutes "return
# findings as text" instead of performing the write. Confirmed empirically
# across path (/tmp and repo-relative) and subagent type (deep-reviewer and
# plain general-purpose) — the block is keyed purely on basename prefix.
# `verdict_` sidesteps that reserved prefix; every skill dispatching
# deep-reviewer for a persisted verdict must name its output `verdict_*.md`.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
BASENAME=${FILE_PATH##*/}

if [[ "$BASENAME" == verdict_*.md ]]; then
  # Auto-approve: bypasses the permission prompt the background subagent can't answer.
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"deep-reviewer may persist its verdict to its verdict file (%s)"}}\n' "$BASENAME"
  exit 0
fi

# Also auto-approve scratch writes under /tmp (the pipeline's wave-artifact dir,
# e.g. /tmp/auto-review.XXXXXX). Reject any path containing `..` first, so a
# traversal like /tmp/../<repo>/file can't escape /tmp back into repo source.
if [[ "$FILE_PATH" != *..* && ( "$FILE_PATH" == /tmp/* || "$FILE_PATH" == /private/tmp/* ) ]]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"deep-reviewer may write scratch under /tmp (%s)"}}\n' "$FILE_PATH"
  exit 0
fi

# Any other write target is a repo-source/artifact mutation — deny it outright.
echo "Blocked: deep-reviewer may write only verdict_*.md or scratch under /tmp (attempted: ${FILE_PATH:-<no path>})" >&2
exit 2
