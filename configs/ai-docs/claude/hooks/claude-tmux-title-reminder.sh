#!/bin/bash
# claude-tmux-title-reminder - Tell Claude to title the tmux window for this session.
#
# Usage (Claude Code SessionStart hook):
#   claude-tmux-title-reminder.sh
#
# Rationale:
#   A descriptive window title ("fix auth bug") beats the auto-generated command
#   name when the user is hunting for the right Claude window. Generating a
#   *brief, good* title needs the model -- a plain shell hook can only read the
#   raw prompt, not summarize it -- so this hook does not set the title itself.
#   Instead it injects a directive (SessionStart additionalContext) telling
#   Claude to set the title via tmux-window-title.sh, and to keep it current.
#
#   Wired on SessionStart sources startup|clear|compact, so the directive is
#   (re)injected exactly when the session boundary resets context: a fresh start,
#   after /clear, and after compaction (which can summarize the directive away).
#
#   Skipped entirely outside tmux -- no window to title, so no point nagging.
#
# Examples:
#   bash claude-tmux-title-reminder.sh   # emits the directive when in tmux

set -euo pipefail

# Outside tmux there is no window to title -- stay silent (no directive).
if [ -z "${TMUX:-}" ]; then
  exit 0
fi

read -r -d '' DIRECTIVE <<'EOF' || true
You are running inside tmux. Keep the tmux window titled with the SHORTEST name that still conveys the current work. Rules: hyphen-separated (no spaces), no prefixes, at most 16 characters (the script truncates longer ones), and shorter is always better -- prefer "auth-fix" over "fix-the-auth-bug". Set or refresh it by running:
  ~/.claude/scripts/tmux-window-title.sh "<title>"
Set it now from the user's first request. Then overwrite it (the script replaces the title outright -- no stacking) on either of these triggers:
  1. You judge the conversation has shifted to a new topic -- do this proactively, on your own initiative, without waiting to be asked.
  2. The user explicitly asks to update the window/pane/tmux title.
EOF

# SessionStart additionalContext: this text is added to Claude's context for the
# session. jq builds the JSON so the multi-line directive is escaped correctly.
jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
