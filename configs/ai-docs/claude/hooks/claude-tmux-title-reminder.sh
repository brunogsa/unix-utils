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

# Headless/programmatic invocations (claude -p, SDK calls, eval harnesses like
# skill-creator's run_loop.py) inherit TMUX from the launching shell even
# though there's no real window to title. Worse, injecting the directive
# there forces an unwanted Bash tool call as the model's first action, which
# corrupts anything that inspects the first tool call (e.g. skill-trigger
# evals). CLAUDE_CODE_ENTRYPOINT is "cli" only for a genuine top-level
# interactive terminal launch; anything else (sdk-cli, remote, ...) is not.
# Unset means an older Claude Code version that predates this var -- fall
# back to firing rather than silently break existing tmux titling for them.
if [ -n "${CLAUDE_CODE_ENTRYPOINT:-}" ] && [ "${CLAUDE_CODE_ENTRYPOINT}" != "cli" ]; then
  exit 0
fi

read -r -d '' DIRECTIVE <<'EOF' || true
You are running inside tmux. Keep the tmux window titled with the SHORTEST name that still conveys the current work. Rules: hyphen-separated (no spaces), no prefixes, at most 16 characters (the script truncates longer ones), and shorter is always better -- prefer "auth-fix" over "fix-the-auth-bug". Set or refresh it by running:
  ~/.claude/scripts/tmux-window-title.sh "<title>"
Set it now from the user's first request. Then overwrite it (the script replaces the title outright -- no stacking) on either of these triggers:
  1. You judge the conversation has shifted to a new topic -- do this proactively, on your own initiative, without waiting to be asked.
  2. The user explicitly asks to update the window/pane/tmux title.
Always pass ONLY the current work, never a composed title. Once this session has survived a compaction the script prefixes the title it froze beforehand, rendering "<root>/<current>[N]" inside a wider 24-character cap -- so never type a "/" or a "[N]" yourself, and never try to restate the original title from memory. The script owns that composition; handing it "<root>/<current>" would nest a second root inside the first.
This applies only to you, the top-level session -- sub-agents spawned via the Agent/Task tool must never call tmux-window-title.sh or be told to, since their fragment would clobber the window's real title.
EOF

# SessionStart additionalContext: this text is added to Claude's context for the
# session. jq builds the JSON so the multi-line directive is escaped correctly.
jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
