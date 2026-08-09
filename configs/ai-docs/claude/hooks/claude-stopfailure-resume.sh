#!/usr/bin/env bash
# claude-stopfailure-resume - Re-prompt the session after a transient API error
#                             kills a turn, so an unattended loop keeps running.
#
# Usage (Claude Code hooks):
#   StopFailure: bash claude-stopfailure-resume.sh
#   Stop:        bash claude-stopfailure-resume.sh --reset
#
# Usage (internal, invoked by tmux after the backoff delay):
#   bash claude-stopfailure-resume.sh --send <pane-id> <attempt>
#
# Examples:
#   echo '{"session_id":"abc","transcript_path":"/x.jsonl"}' | bash claude-stopfailure-resume.sh
#   echo '{"session_id":"abc"}' | bash claude-stopfailure-resume.sh --reset
#
# Why this exists:
#   When the API drops the stream AFTER Claude has already emitted content,
#   Claude Code deliberately does NOT retry -- it finalizes the partial turn
#   ("API Error: Server error mid-response. The response above may be
#   incomplete."). Emitted tokens can't be un-emitted, so a request-level
#   retry would duplicate them. Verified in the 2.1.226 binary: the mid-stream
#   handler retries only while nothing but thinking blocks have been yielded,
#   and otherwise logs "Mid-stream server error after N block(s) yielded --
#   finalizing partial response". No retry env var reaches that path.
#
#   That leaves the turn dead and any /loop or long batch stopped. The only
#   harness surface for it is the StopFailure hook -- but its "output and exit
#   code are ignored", so it cannot return {decision:"block"} the way Stop can.
#   It can only act through side effects. Under tmux the side effect that
#   restarts a turn is typing into the session's own pane.
#
# Why NOT rate limits:
#   Resuming into a session/weekly limit cannot succeed -- it just burns the
#   budget and spams the pane. Same for "Prompt is too long", where another
#   turn makes the offending context bigger, not smaller. Only the transient
#   server-side class is worth re-prompting, and unrecognized errors are
#   treated as not-worth-it rather than resumed on a guess.
#
# Why subagent failures are skipped:
#   StopFailure also fires for a subagent, with agent_id set. There the main
#   turn is still alive and receives the failure as a tool result, so it
#   recovers on its own -- observed in session 9f787938, where a subagent died
#   with server_error at 18:05:51 and the parent retried the task at 18:06:31.
#   Typing into the pane there would inject a prompt mid-turn instead.
#
# Safeguards (never make a bad situation worse):
#   - Capped at MAX_RESUMES consecutive attempts, with a growing backoff, so a
#     real outage can't turn into an infinite re-prompt loop.
#   - The counter resets on any clean Stop (--reset), so "consecutive" means
#     consecutive failures, not failures per session.
#   - Never types into a pane running a shell -- if Claude Code has exited, the
#     resume text would otherwise be executed as a shell command.
#   - Missing jq, no tmux, or an unreadable transcript all exit 0 silently.

set -uo pipefail

# The backoff ladder, in seconds -- one rung per allowed resume, so its length
# IS the budget. The first retry is quick because most of these clear
# immediately; the later ones back off so a sustained outage is waited out
# rather than hammered. Add or drop a rung to change how many resumes a session
# gets; deriving the cap keeps the two from drifting into an unbound index.
BACKOFF_SECONDS=(15 60 180)
MAX_RESUMES=${#BACKOFF_SECONDS[@]}

STATE_DIR=/tmp/claude-stopfailure-resume

# Error markers, matched against the event payload and the transcript's last
# API-error entry. Skip is checked first, so an unrecognized error resumes
# nothing. Strings are the ones Claude Code actually writes -- taken from the
# `error` field and message text of isApiErrorMessage entries in ~/.claude.
SKIP_MARKERS='rate_limit|invalid_request|authentication_failed'
RESUME_MARKERS='server_error|"error":"timeout"|mid-response|mid-stream|Overloaded|Internal server error'

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/$(basename "${BASH_SOURCE[0]:-$0}")"

# resume_message - the prompt typed back into the pane. Self-describing on
# purpose: the session that reads it has no memory of why it stopped, and the
# transcript shows only a truncated turn.
#
# It must not start with "/" or "!" -- those are a slash command and a bash
# command in the Claude Code TUI, not a prompt.
resume_message() {
  local attempt="$1"
  printf '%s' "[auto-resume ${attempt}/${MAX_RESUMES}] The previous turn was cut off mid-response by a transient API error, not by me. Re-ground from your /tmp scratchpad and the TaskList, then continue exactly where you left off."
}

# ---------------------------------------------------------------------------
# --send: the delayed half, run by the tmux server after the backoff elapses.
# Detached from the hook process on purpose -- see the dispatch call below.
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--send" ]; then
  pane="${2:-}"
  attempt="${3:-1}"
  [ -n "$pane" ] || exit 0

  pane_command=$(tmux display-message -t "$pane" -p '#{pane_current_command}' 2>/dev/null) || exit 0

  # Claude Code's binary is named after its version (e.g. "2.1.226"), so there
  # is no stable name to allow-list. Deny the shells instead: if Claude Code
  # has exited, the pane is back at a prompt and typing there would run the
  # resume text as a command.
  case "$pane_command" in
    bash|zsh|sh|fish|dash|ksh) exit 0 ;;
  esac

  tmux send-keys -t "$pane" -l "$(resume_message "$attempt")" 2>/dev/null || exit 0

  # The TUI needs the text to land before the submit key; sending both in one
  # burst was observed to drop the newline into the composer as a literal.
  sleep 0.3
  tmux send-keys -t "$pane" Enter 2>/dev/null || true
  exit 0
fi

command -v jq >/dev/null 2>&1 || exit 0

payload=""
if [ ! -t 0 ]; then
  payload=$(cat)
fi

session_id=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
[ -n "$session_id" ] || exit 0

# Strip anything that isn't filename-safe: session_id comes from the harness,
# but it composes a /tmp path, so a hostile value must not escape the dir.
state_file="$STATE_DIR/${session_id//[^A-Za-z0-9_-]/_}.count"

# ---------------------------------------------------------------------------
# --reset: wired to Stop. A turn that ended normally proves the API recovered,
# so the next failure starts its budget over.
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--reset" ]; then
  rm -f "$state_file"
  exit 0
fi

# Typing into a pane is the only lever here, so a session outside tmux has none.
if [ -z "${TMUX:-}" ] || [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

# A subagent's failure leaves the main turn running -- see the header.
agent_id=$(printf '%s' "$payload" | jq -r '.agent_id // empty' 2>/dev/null)
if [ -n "$agent_id" ]; then
  exit 0
fi

# Classify from the event payload plus the transcript's last API-error entry.
# Both are consulted because the payload's error_details shape is unspecified,
# while the transcript's `"error":"<kind>"` field is stable and observable.
haystack="$payload"
transcript_path=$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null)
if [ -n "$transcript_path" ] && [ -r "$transcript_path" ]; then
  last_api_error=$(grep -F '"isApiErrorMessage":true' "$transcript_path" 2>/dev/null | tail -1)
  haystack="$haystack
$last_api_error"
fi

if printf '%s' "$haystack" | grep -Eq "$SKIP_MARKERS"; then
  exit 0
fi

if ! printf '%s' "$haystack" | grep -Eq "$RESUME_MARKERS"; then
  exit 0
fi

mkdir -p "$STATE_DIR" 2>/dev/null || exit 0

# Sessions that end while still failing never reach --reset, so their counter
# would linger. Sweep yesterday's leftovers on the way past.
find "$STATE_DIR" -name '*.count' -mtime +1 -delete 2>/dev/null || true

previous_attempts=$(cat "$state_file" 2>/dev/null)
case "$previous_attempts" in
  ''|*[!0-9]*) previous_attempts=0 ;;
esac

attempt=$((previous_attempts + 1))
if [ "$attempt" -gt "$MAX_RESUMES" ]; then
  exit 0
fi
printf '%s' "$attempt" > "$state_file"

delay="${BACKOFF_SECONDS[$((attempt - 1))]}"

# Dispatch through the tmux server rather than a background child of this hook:
# hooks are reaped on their timeout, which would kill a plain `sleep &` before
# the longest backoff elapses. `run-shell -b -d` is owned by the server, which
# outlives the hook.
tmux run-shell -b -d "$delay" "bash '$SCRIPT_PATH' --send '$TMUX_PANE' '$attempt'" 2>/dev/null || true

exit 0
