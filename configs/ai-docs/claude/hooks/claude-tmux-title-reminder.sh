#!/bin/bash
# claude-tmux-title-reminder - Tell Claude to title the tmux
# window for this session.
#
# Usage (Claude Code SessionStart hook):
#   claude-tmux-title-reminder.sh
#
# Rationale:
#   A descriptive window title ("fix auth bug") beats the
#   auto-generated command name when the user is hunting for
#   the right Claude window.
#
#   Generating a *brief, good* title needs the model -- a
#   plain shell hook can only read the raw prompt, not
#   summarize it -- so this hook does not set the title
#   itself.
#
#   Instead it injects a directive (SessionStart
#   additionalContext) telling Claude to set one goal-named
#   first title via tmux-window-title.sh and never re-title
#   before the first main compaction.
#
#   Wired on SessionStart sources startup|clear|resume|fork,
#   so the directive is injected when a session begins. The
#   compact source is excluded: the compact reminder and the
#   main compaction bump speak there instead.
#
#   Skipped entirely outside tmux -- no window to title, so no
#   point nagging.
#
# Why this hook skips a subagent's SessionStart:
#   The directive below forbids a subagent from
#   calling tmux-window-title.sh -- handing it TO
#   a subagent breaks the very rule it states.
#
#   session_id can't discriminate the two: a subagent
#   inherits its parent's session_id.
#
#   Only agent_id tells the orchestrator apart from the agents
#   it spawned, because agent_type is also set on a main
#   session started with --agent.
#
#   Same precedent as claude-tmux-title-compact-reminder.sh.
#
# Examples:
#   bash claude-tmux-title-reminder.sh
#   # emits the directive when in tmux

set -euo pipefail

# Outside tmux there is no window to title -- stay silent (no
# directive).
if [ -z "${TMUX:-}" ]; then
  exit 0
fi

# Headless/programmatic invocations (claude -p, SDK calls, eval
# harnesses like skill-creator's run_loop.py) inherit TMUX from
# the launching shell even though there's no real window to
# title.
#
# Worse, injecting the directive there forces an unwanted Bash
# tool call as the model's first action, which corrupts anything
# that inspects the first tool call (e.g. skill-trigger evals).
#
# CLAUDE_CODE_ENTRYPOINT is "cli" only for a genuine top-level
# interactive terminal launch; anything else (sdk-cli, remote,
# ...) is not.
#
# Unset means an older Claude Code version that predates this
# var -- fall back to firing rather than silently break existing
# tmux titling for them.
if [ -n "${CLAUDE_CODE_ENTRYPOINT:-}" ] && [ "${CLAUDE_CODE_ENTRYPOINT}" != "cli" ]; then
  exit 0
fi

input=$(cat)

# Only the top-level session may be told to retitle the
# window -- see the header. A subagent's SessionStart
# carries agent_id on stdin.
agent=$(printf '%s' "$input" | jq -r '.agent_id // empty' 2>/dev/null || true)
[ -n "$agent" ] && exit 0

read -r -d '' DIRECTIVE <<'EOF' || true
You are running inside tmux. Set the tmux window title ONCE, now, to the SHORTEST name that conveys the session's goal. Rules: hyphen-separated (no spaces), no prefixes, at most 16 characters (the script truncates longer ones), and shorter is always better -- prefer "auth-fix" over "fix-the-auth-bug". The title names the goal, never a skill name, a step name, or an issue-tracker ID. Set it by running:
  ~/.claude/scripts/tmux-window-title.sh "<title>"
Pick the goal from the first of these sources that exists, in this order:
  1. The open PR's title: run `gh pr view --json title` yourself. Drop ticket IDs and "feat(...)"-style prefixes from it. If the lookup fails or finds nothing, go to the next source.
  2. The git branch topic, with the ticket ID dropped: read the branch name yourself.
  3. The goal of the user's first real request.
Use this order whenever the first request is a bare skill call with no topic (for example "/implement").
Never re-title before the first main compaction, even when the conversation changes subject. The script refuses a second title and exits 0 with a note saying so; do not retry it.
A window name starting with "." is the user's own: it is never changed before the first main compaction and its root is never replaced after one. The script refuses it and exits 0 with a note; do not retry.
If the user asks for a new title before the first main compaction, do not call the script and never call "tmux rename-window" directly. Reply that they rename the window by hand with "prefix ," (tmux's rename-window key).
Pass ONLY the goal label, never a composed title. Once this session has survived a compaction the script prefixes the title it froze beforehand, rendering "<root>/<tail>[M+S]" inside a wider 32-character cap -- M is this session's own compactions, S is subagent compactions (S is dropped entirely when zero) -- so never type a "/" or a "[M+S]" yourself, and never try to restate the original title from memory. Post-root, the root keeps its own fixed 16 characters and your tail label shares a second 16-character tail with the leading "/" and the [M+S] counter -- so up to 12 characters with [1], 10 with [1+1], and fewer as the counter widens. The script owns that composition; handing it "<root>/<tail>" would nest a second root inside the first.
This applies only to you, the top-level session -- sub-agents spawned via the Agent/Task tool must never call tmux-window-title.sh or be told to, since their fragment would clobber the window's real title.
EOF

# SessionStart additionalContext: this text is added to Claude's
# context for the session. jq builds the JSON so the multi-line
# directive is escaped correctly.
jq -n --arg ctx "$DIRECTIVE" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
