#!/usr/bin/env bash
# claude-compact-skill-reload - After a compaction, remind Claude to RELOAD any
#     still-needed skills it loaded earlier this session.
#
# Usage (Claude Code SessionStart hook, matcher: compact):
#   stdin:  hook event JSON ({ session_id, transcript_path, source, ... })
#   stdout: optional JSON ({ hookSpecificOutput: { additionalContext } })
#
# Rationale:
#   A compaction summarizes earlier turns out of the model's working memory. A
#   skill loaded before the boundary (implement, brainstorm, ...) then silently
#   drops out, and the model keeps working without the procedure that was
#   governing it -- the "orchestrator forgot what it was doing" failure.
#
#   The session transcript is append-only across compaction, so every Skill
#   tool call this session made is still on disk even once summarized out of
#   context. This hook greps the transcript for those loads, dedups them, and
#   re-injects the list with a directive to reload the still-necessary ones
#   FIRST -- before continuing the task -- so the procedure is re-established at
#   the one moment working memory resets.
#
#   Necessity is the model's call, not the hook's: the hook only surfaces WHAT
#   was loaded. Procedural/orchestrator skills (brainstorm, implement) carry
#   multi-step state and are the usual casualties, so they get the emphasis;
#   *-standards skills are stateless guidance and stay lazy (reload when their
#   trigger next fires), per CLAUDE.md.
#
#   Complements claude-implement-compact-reminder.sh: that hook reconstructs
#   /implement's exact remaining finalize steps from its state file; this one
#   is the general net for every other skill.
#
# Why this hook skips a subagent's compaction:
#   The directive reloads skills the MAIN
#   session loaded before this compaction --
#   a subagent's own transcript never had them.
#
#   agent_id (falling back to agent_type) scopes
#   the reminder to the owning session only. Same
#   precedent as claude-explore-mandate-hook.sh and
#   claude-stopfailure-resume.sh.
#
# Safeguards (all silent no-ops -- never break Claude on a tooling/state gap):
#   - jq missing -> exit 0.
#   - agent_id or agent_type non-empty (a subagent's
#     compaction) -> exit 0.
#   - No transcript_path, or the file is missing -> exit 0.
#   - No Skill loads found in the transcript -> exit 0 (no noise).

set -eo pipefail

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

# Only the session that loaded the skills may be reminded to
# reload them -- see the header. A subagent's compaction
# carries agent_id (or agent_type as a fallback) on stdin.
agent=$(printf '%s' "$input" | jq -r '.agent_id // .agent_type // empty' 2>/dev/null || true)
[ -n "$agent" ] && exit 0

transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -z "$transcript_path" ] && exit 0
[ -f "$transcript_path" ] || exit 0

# A Skill tool call logs as one JSONL line carrying both `"name":"Skill"` and
# `"input":{"skill":"<name>"}`. Filter to those lines FIRST so a Bash command
# or tool result that merely mentions the `"skill":"..."` pattern (e.g. this
# session's own greps) can't masquerade as a real load. Then pull the names,
# dedup, and join as ", " for a readable list.
skills=$(grep '"name":"Skill"' "$transcript_path" 2>/dev/null \
  | grep -oE '"skill":"[^"]+"' \
  | sed -E 's/^"skill":"//; s/"$//' \
  | sort -u \
  | paste -sd, - \
  | sed 's/,/, /g' || true)

[ -z "$skills" ] && exit 0

read -r -d '' DIRECTIVE <<EOF || true
This compaction may have dropped skills you loaded earlier out of working memory. Skills loaded this session (from the transcript): $skills.

BEFORE continuing the task, RELOAD -- as your FIRST action -- any of these that still govern what you are doing. Procedural/orchestrator skills (especially 'brainstorm' and 'implement') carry multi-step state that compaction drops, so re-establish those first, then re-ground from any /tmp scratchpad and your TaskList.

'*-standards' skills can stay lazy -- reload each when its trigger next fires. Reload only what is still necessary; you decide which.
EOF

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
