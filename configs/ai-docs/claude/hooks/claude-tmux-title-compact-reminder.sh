#!/bin/bash
# claude-tmux-title-compact-reminder - After a compaction, tell
# Claude to re-assess and regenerate the tmux window's
# compact-focus label.
#
# Don't just rely on the mechanical counter bump.
#
# Usage (Claude Code SessionStart hook, matcher: compact):
#   claude-tmux-title-compact-reminder.sh
#
# Rationale:
#   On `compact`, a companion hook (`tmux-window-title.sh
#   --bump-counter`) mechanically increments the "[N]"
#   compaction counter.
#
#   That counter sits on whatever compact-focus label the window
#   already has.
#
#   It never re-derives that label itself, because a plain shell
#   script can't summarize the conversation.
#
#   Left at that, a long-lived session keeps an arbitrarily
#   stale compact-focus label forever: the counter climbs ("pic-
#   crm-billing/old-topic[4]") while the actual work has moved
#   on to something the label no longer describes.
#
#   claude-tmux-title-reminder.sh (wired on
#   startup|clear|resume|fork, never compact) only tells
#   Claude to retitle on a topic shift IT judges, or on
#   explicit user ask.
#
#   Neither is guaranteed to fire around a compaction, since the
#   compaction itself doesn't read as "a topic shift" even when
#   several compactions' worth of scope drift have accumulated.
#
#   This hook adds a third, compaction-specific push: re-assess
#   the compact-focus label right now, in this turn, because the
#   counter having moved already proves scope may have too.
#
#   The directive insists on the compact-focus label ALONE
#   because tmux-window-title.sh keeps the session's root anchor
#   itself (see its `--help`).
#
#   The title from before the first compaction is frozen in a
#   pane option and re-attached on every render.
#
#   Asking Claude to preserve it instead would ask it to recall
#   the one thing a compaction reliably erases -- the session's
#   first turn.
#
#   Kept as its own hook (not folded into
#   claude-tmux-title-reminder.sh) to match the sibling
#   compact-only hooks (claude-implement-compact-reminder.sh,
#   claude-compact-skill-reload.sh): one concern per script.
#
# Why this hook skips a subagent's compaction:
#   The directive below forbids a subagent from calling
#   tmux-window-title.sh -- handing it TO a subagent breaks
#   the very rule it states.
#
#   agent_id alone (agent_type is also set on a main session
#   started with --agent) scopes the directive
#   to the top-level session only.
#
#   Same precedent as claude-explore-mandate-hook.sh and
#   claude-stopfailure-resume.sh.
#
# Safeguards:
# - Outside tmux, or a headless/programmatic invocation (same
#   guard as claude-tmux-title-reminder.sh) -- silent no-op, no
#   directive.
#
# - agent_id non-empty (a subagent's compaction)
#   -- silent no-op, no directive.
#
# Examples:
#   bash claude-tmux-title-compact-reminder.sh
#     Emits the directive in tmux.

set -euo pipefail

# Outside tmux there is no window to title -- stay silent (no
# directive).
if [ -z "${TMUX:-}" ]; then
  exit 0
fi

# Same headless-safety guard as claude-tmux-title-reminder.sh --
# see that script's comment for the full rationale
# (skill-trigger evals, SDK calls).
if [ -n "${CLAUDE_CODE_ENTRYPOINT:-}" ] && [ "${CLAUDE_CODE_ENTRYPOINT}" != "cli" ]; then
  exit 0
fi

input=$(cat)

# Only the top-level session may be told to retitle the
# window -- see the header. A subagent's compaction carries
# agent_id on stdin.
agent=$(printf '%s' "$input" | jq -r '.agent_id // empty' 2>/dev/null || true)
[ -n "$agent" ] && exit 0

read -r -d '' DIRECTIVE <<'EOF' || true
A compaction just happened. The tmux window's compaction counter was already bumped mechanically (a companion hook does that unconditionally), but the tail of the title was NOT re-derived -- that needs your judgment, not a shell script. Set the tail to the current sub-goal, phrased as a goal. Re-assess right now whether it still names what you are working toward: scope can drift across many compacted turns even without an obvious topic switch. Refresh it via:
  ~/.claude/scripts/tmux-window-title.sh '<tail>'
Pass ONLY the tail (the current sub-goal), never the root. The tail holds only lowercase letters, digits and hyphens ([a-z0-9-]), so a quote, "$", backtick or ";" never reaches the command. The script composes "<root>/<tail>[M+S]" itself -- M is this session's own compactions, S is subagent compactions (dropped entirely when zero). So never type the root, the "/", or the "[M+S]" yourself -- the root is exactly what a compaction erases from your context, which is why the script keeps it instead of you. Your tail shares a 16-character segment with the "/" and the [M+S] counter -- up to 12 characters with [1], 10 with [1+1], and fewer as the counter widens -- so keep it short. If the tail still names the current sub-goal and fits, no action needed, but make that a deliberate check, not a default assumption.
EOF

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
