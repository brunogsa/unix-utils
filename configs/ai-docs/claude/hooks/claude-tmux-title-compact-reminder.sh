#!/bin/bash
# claude-tmux-title-compact-reminder - After a compaction, tell Claude to
#     re-assess and regenerate the tmux window's BASE title, not just rely on
#     the mechanical counter bump.
#
# Usage (Claude Code SessionStart hook, matcher: compact):
#   claude-tmux-title-compact-reminder.sh
#
# Rationale:
#   On `compact`, a companion hook (`tmux-window-title.sh --bump-counter`)
#   mechanically increments the "[N]" compaction counter on whatever base
#   title the window already has -- it never re-derives the base itself,
#   because a plain shell script can't summarize the conversation. Left at
#   that, a long-lived session keeps an arbitrarily stale base title forever:
#   the counter climbs ("pic-crm-billing[4]") while the actual work has moved
#   on to something the title no longer describes.
#
#   claude-tmux-title-reminder.sh (wired on startup|clear|compact too) only
#   tells Claude to retitle on a topic shift IT judges, or on explicit user
#   ask -- neither is guaranteed to fire around a compaction, since the
#   compaction itself doesn't read as "a topic shift" even when several
#   compactions' worth of scope drift have accumulated. This hook adds a
#   third, compaction-specific push: re-assess the base right now, in this
#   turn, because the counter having moved already proves scope may have too.
#
#   The directive insists on the CURRENT work alone because tmux-window-title.sh
#   keeps the session's root anchor itself (see its `--help`): the title from
#   before the first compaction is frozen in a pane option and re-attached on
#   every render. Asking Claude to preserve it instead would ask it to recall
#   the one thing a compaction reliably erases -- the session's first turn.
#
#   Kept as its own hook (not folded into claude-tmux-title-reminder.sh) to
#   match the sibling compact-only hooks (claude-implement-compact-reminder.sh,
#   claude-compact-skill-reload.sh): one concern per script.
#
# Safeguards:
#   - Outside tmux, or a headless/programmatic invocation (same guard as
#     claude-tmux-title-reminder.sh) -- silent no-op, no directive.
#
# Examples:
#   bash claude-tmux-title-compact-reminder.sh   # emits the directive in tmux

set -euo pipefail

# Outside tmux there is no window to title -- stay silent (no directive).
if [ -z "${TMUX:-}" ]; then
  exit 0
fi

# Same headless-safety guard as claude-tmux-title-reminder.sh -- see that
# script's comment for the full rationale (skill-trigger evals, SDK calls).
if [ -n "${CLAUDE_CODE_ENTRYPOINT:-}" ] && [ "${CLAUDE_CODE_ENTRYPOINT}" != "cli" ]; then
  exit 0
fi

read -r -d '' DIRECTIVE <<'EOF' || true
A compaction just happened. The tmux window's compaction counter was already bumped mechanically (a companion hook does that unconditionally), but its BASE title was NOT re-derived -- that needs your judgment, not a shell script. Re-assess right now whether the base still reflects current work: scope can drift across many compacted turns even without an obvious topic switch. Refresh it via:
  ~/.claude/scripts/tmux-window-title.sh "<title>"
Pass ONLY the current work, in at most 16 characters. Nothing is lost by narrowing it that way: on the first compaction the script froze the then-current title as this session's ROOT and re-attaches it on every later render, as "<root>/<current>[M+S]" -- M is this session's own compactions, S is subagent compactions (dropped entirely when zero). So never type the root, the "/", or the "[M+S]" yourself -- the root is exactly what a compaction erases from your context, which is why the script keeps it instead of you. If the base still fits, no action needed, but make that a deliberate check, not a default assumption.
EOF

jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
