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
# Why this hook skips a subagent's SessionStart:
#   The directive below forbids a subagent from
#   calling tmux-window-title.sh -- handing it TO
#   a subagent breaks the very rule it states.
#
#   session_id can't discriminate the two: a
#   subagent inherits its parent's session_id, so
#   only agent_id (falling back to agent_type) tells
#   the orchestrator apart from the agents it spawned.
#   Same precedent as claude-tmux-title-compact-reminder.sh.
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

input=$(cat)

# Only the top-level session may be told to retitle the
# window -- see the header. A subagent's SessionStart
# carries agent_id (or agent_type as a fallback) on stdin.
agent=$(printf '%s' "$input" | jq -r '.agent_id // .agent_type // empty' 2>/dev/null || true)
[ -n "$agent" ] && exit 0

read -r -d '' DIRECTIVE <<'EOF' || true
You are running inside tmux. Keep the tmux window titled with the SHORTEST name that still conveys the current work. Rules: hyphen-separated (no spaces), no prefixes, at most 16 characters (the script truncates longer ones), and shorter is always better -- prefer "auth-fix" over "fix-the-auth-bug". Set or refresh it by running:
  ~/.claude/scripts/tmux-window-title.sh "<title>"
Set it now from the user's first request. Then overwrite it (the script replaces the title outright -- no stacking) on either of these triggers:
  1. You judge the conversation has shifted to a new topic -- do this proactively, on your own initiative, without waiting to be asked.
  2. The user explicitly asks to update the window/pane/tmux title.
Always pass ONLY the current work, never a composed title. Once this session has survived a compaction the script prefixes the title it froze beforehand, rendering "<root>/<current>[M+S]" inside a wider 24-character cap -- M is this session's own compactions, S is subagent compactions (S is dropped entirely when zero) -- so never type a "/" or a "[M+S]" yourself, and never try to restate the original title from memory. The script owns that composition; handing it "<root>/<current>" would nest a second root inside the first.
This applies only to you, the top-level session -- sub-agents spawned via the Agent/Task tool must never call tmux-window-title.sh or be told to, since their fragment would clobber the window's real title.
EOF

# SessionStart additionalContext: this text is added to Claude's context for the
# session. jq builds the JSON so the multi-line directive is escaped correctly.
jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
