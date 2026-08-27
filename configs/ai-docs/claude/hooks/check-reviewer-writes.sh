#!/bin/bash
# PreToolUse guard shared by every reviewer agent that references it from its
# frontmatter: code-reviewer, spec-reviewer, plan-reviewer, test-reviewer.
#
# Each is a read-only judge. Its write affordances are exactly two:
#   1. persisting a verdict to a caller-assigned verdict file, and
#   2. scratch under /tmp — the review pipeline (auto-review) persists its wave
#      artifacts to a mktemp dir there, and /tmp is never repo source.
#
# When code-reviewer runs auto-review's local mode (its own pin), Wave 2's
# findings JSON lands in that same mktemp dir under the second affordance, so an
# opus context running the whole pipeline still cannot reach repo source even
# under a bypassPermissions parent.
#
# Both `.md` and `.html` count as a verdict file: the html-artifacts router
# picks the extension per artifact type, and it routes a review report to an
# HTML artifact. A guard allowing only `.md` would deny that write at the tool
# layer and lose the whole review at its last step.
#
# This guard enforces that at the tool layer: a Write/Edit to a verdict file or
# to a path under /tmp is auto-approved (so an unattended background subagent needs
# no interactive prompt); every other Write/Edit is denied (so it can never touch
# repo source, even under a bypassPermissions parent).
#
# Why `verdict_` and not `report_`/`findings_`: the Claude Code harness itself
# intercepts a subagent Write whose basename matches a reserved stem, before
# this hook ever runs, and silently substitutes "return findings as text"
# instead of performing the write. `verdict_` sidesteps that reserved set.
#
# The full trigger (all four stems, the `.md`-only scope, case-insensitivity,
# start-anchoring) is documented once, in agent-standards' "Subagent
# dispatch" section — see that skill rather than re-deriving it here.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
BASENAME=${FILE_PATH##*/}

if [[ "$BASENAME" == verdict_*.md || "$BASENAME" == verdict_*.html ]]; then
  # Auto-approve: bypasses the permission prompt the background subagent can't answer.
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"this reviewer may persist its verdict to its verdict file (%s)"}}\n' "$BASENAME"
  exit 0
fi

# Also auto-approve scratch writes under /tmp (the pipeline's wave-artifact dir,
# e.g. /tmp/auto-review.XXXXXX). Reject any path containing `..` first, so a
# traversal like /tmp/../<repo>/file can't escape /tmp back into repo source.
if [[ "$FILE_PATH" != *..* && ( "$FILE_PATH" == /tmp/* || "$FILE_PATH" == /private/tmp/* ) ]]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"this reviewer may write scratch under /tmp (%s)"}}\n' "$FILE_PATH"
  exit 0
fi

# Any other write target is a repo-source/artifact mutation — deny it outright.
echo "Blocked: this reviewer may write only verdict_*.md, verdict_*.html, or scratch under /tmp (attempted: ${FILE_PATH:-<no path>})" >&2
exit 2
