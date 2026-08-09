#!/bin/bash
# claude-explore-mandate-hook - make the Explore mandate
# a mechanism instead of a rule.
#
# Usage (Claude Code hooks):
#   PreToolUse  matcher Grep|Glob  -> count, maybe deny
#   PostToolUse matcher Agent      -> --reset clears it
#
# CLAUDE.md mandates delegating a broad search to an
# Explore subagent, and telemetry says the rule barely
# fires: 10 Explore runs against 36 general-purpose ones
# over 2026-08-02..08-08.
#
# A run of searches is the discriminator this uses: one
# lookup is targeted, seven inside ten minutes is a hunt
# whose every intermediate match lands in the main
# session's context.
#
# Denying only the call past the limit and then clearing
# the count is deliberate: a permanent deny would
# deadlock a session whose harness forbids spawning
# agents at all.
#
# That trade still buys a hard interrupt mid-hunt, which
# an end-of-turn nudge cannot deliver.
#
# A call carrying agent_id or agent_type is exempt: that
# IS the delegated search the mandate asks for.
#
# Examples:
#   echo '{"session_id":"s","tool_name":"Grep"}' \
#     | bash claude-explore-mandate-hook.sh
#
#   echo '{"session_id":"s"}' \
#     | bash claude-explore-mandate-hook.sh --reset

set -uo pipefail

SEARCH_LIMIT=6
WINDOW_SECONDS=600
STATE_DIR="${TMPDIR:-/tmp}/claude-explore-mandate"

INPUT=$(cat)

SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)

# Strip every character a path separator could hide in,
# so a hostile session_id cannot escape STATE_DIR.
SESSION_KEY=$(printf '%s' "$SESSION_ID" | tr -cd 'A-Za-z0-9._-')

# An unidentifiable session has no counter to carry, and
# a shared fallback file would blend concurrent sessions.
if [ -z "$SESSION_KEY" ]; then
  exit 0
fi

STATE_FILE="$STATE_DIR/$SESSION_KEY.log"

if [ "${1:-}" = "--reset" ]; then
  rm -f "$STATE_FILE"
  exit 0
fi

AGENT=$(printf '%s' "$INPUT" | jq -r '.agent_id // .agent_type // empty' 2>/dev/null)
if [ -n "$AGENT" ]; then
  exit 0
fi

# A hook that cannot write its state must not block the
# tool: failing open costs a nudge, failing closed costs
# the session every search it needed.
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0

NOW=$(date +%s)
CUTOFF=$((NOW - WINDOW_SECONDS))

# Rewriting the file to the surviving stamps is what
# bounds it: a hunt is bursty, so searches spread over an
# afternoon must never accumulate into a false deny.
RECENT=$(awk -v cutoff="$CUTOFF" '$1 + 0 >= cutoff' "$STATE_FILE" 2>/dev/null)
{
  [ -n "$RECENT" ] && printf '%s\n' "$RECENT"
  printf '%s\n' "$NOW"
} > "$STATE_FILE" 2>/dev/null || exit 0

COUNT=$(grep -c . "$STATE_FILE" 2>/dev/null) || COUNT=0

if [ "$COUNT" -le "$SEARCH_LIMIT" ]; then
  exit 0
fi

rm -f "$STATE_FILE"

cat >&2 <<EOF
Explore mandate: $COUNT Grep/Glob calls in this main session inside
$WINDOW_SECONDS seconds, with no Agent dispatch between them.

A run that long is a search hunt, not a lookup, and CLAUDE.md mandates
delegating those:

  agent(subAgent=Explore, title=<what you are hunting for>)

Explore reads the files and returns only the conclusion, keeping every
intermediate match out of this session's context - the budget compactions
are rationed by.

If this genuinely is one targeted lookup, re-run it: the counter cleared
on this denial, so the next $SEARCH_LIMIT searches go through.
EOF
exit 2
