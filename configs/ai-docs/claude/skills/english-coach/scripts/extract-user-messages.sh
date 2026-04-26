#!/usr/bin/env bash
# extract-user-messages.sh - Extract typed user messages from current session JSONL.
#
# Usage:
#   extract-user-messages.sh
#   extract-user-messages.sh > /tmp/english-coach-input.txt
#
# Examples:
#   bash ~/.claude/skills/english-coach/scripts/extract-user-messages.sh
#   bash ~/.claude/skills/english-coach/scripts/extract-user-messages.sh | wc -l
#
# Walks up parent directories from cwd to find the Claude project dir
# (~/.claude/projects/<encoded-cwd>/), picks the most-recently-modified
# .jsonl, and prints typed user messages separated by `===` lines.
# Excludes tool results, slash-command markers, system reminders, and
# local-command output — only the user's own typed text remains.
#
# Exit codes:
#   0 — success
#   1 — no Claude project dir or no session JSONL found

set -eo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

# Walk up parents until we find a Claude project dir for this cwd. Claude Code
# binds the session to its starting cwd; running this script from a subdir of
# the repo still needs the encoded path of the original starting dir.
session_file=""
current="$(pwd)"
while [ -n "$current" ] && [ "$current" != "/" ]; do
    encoded="${current//\//-}"
    candidate_dir="$HOME/.claude/projects/$encoded"
    if [ -d "$candidate_dir" ]; then
        # shellcheck disable=SC2012  # JSONL filenames are session UUIDs (no spaces); ls -t is the simplest mtime sort
        sf=$(ls -t "$candidate_dir"/*.jsonl 2>/dev/null | head -n 1)
        if [ -n "$sf" ]; then
            session_file="$sf"
            break
        fi
    fi
    current=$(dirname "$current")
done

if [ -z "$session_file" ]; then
    echo "ERROR: no Claude session JSONL found walking up from $(pwd)" >&2
    echo "(this cwd may not have been used with Claude Code yet)" >&2
    exit 1
fi

echo "# Source: $session_file" >&2
echo "# Extracted at: $(date)" >&2

# Each JSONL line is {type, message: {role, content}}. `content` may be a string
# or an array of {type: text|tool_result|...}. Keep only `text` parts and drop
# slash-command markers, system reminders, and local-command output. Each kept
# message is preceded by `===` so the analyzer can tell them apart.
jq -r '
    select(.type == "user")
    | .message
    | select(.role == "user")
    | .content
    | if type == "string" then [.] else map(select(.type == "text") | .text) end
    | .[]
    | select(. != null and . != "")
    | select(test("^<command-") | not)
    | select(test("<system-reminder>") | not)
    | select(test("^<local-command-") | not)
    | "===\n" + .
' "$session_file"
