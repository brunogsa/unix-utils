#!/bin/bash
# PreToolUse guard for the deep-reviewer subagent (referenced from its frontmatter).
#
# deep-reviewer is a read-only judge. Its ONE write affordance is persisting its
# own verdict to a caller-assigned report file. This guard enforces that at the
# tool layer: a Write/Edit whose file_path basename matches `report_*.md` is
# auto-approved (so an unattended background subagent needs no interactive
# prompt); every other Write/Edit is denied (so it can never touch source, even
# under a bypassPermissions parent).

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
BASENAME=${FILE_PATH##*/}

if [[ "$BASENAME" == report_*.md ]]; then
  # Auto-approve: bypasses the permission prompt the background subagent can't answer.
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"deep-reviewer may persist its verdict to its report file (%s)"}}\n' "$BASENAME"
  exit 0
fi

# Any other write target is a source/artifact mutation — deny it outright.
echo "Blocked: deep-reviewer is read-only except for its report_*.md file (attempted: ${FILE_PATH:-<no path>})" >&2
exit 2
