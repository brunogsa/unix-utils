#!/bin/bash
# claude-bash-prose-aftercheck - run the prose format checker
# on every work-tree file a Bash command changed.
#
# Usage (Claude Code hooks):
#   PreToolUse  matcher Bash -> --mark stamps a marker
#   PostToolUse matcher Bash -> checks files newer than it
#
# claude-bash-write-guard.sh decides before the command runs,
# from its text and the disk as it is then. An earlier part
# of the same command can change the disk first, as in
# `mkdir d && cp a.md d`, so only what landed tells the truth.
#
# A changed file is a dirty or untracked, not git-ignored one
# whose mtime or ctime is newer than the marker: mv keeps the
# mtime, so only the ctime shows a move.
#
# The marker is keyed by tool_use_id, so parallel Bash calls
# never share one. Each file goes to
# claude-prose-format-posttool-hook.sh as a Write payload, so
# findings reach the model on stderr with exit 2 the same way.
#
# Known limits:
#
# - Writes into another repo are not checked: only the cwd's
#   work tree is listed.
#
# - A file inside a directory moved in whole keeps both its
#   stamps; the write guard blocks a directory copy it sees.
#
# - A command that exits non-zero fires PostToolUseFailure,
#   not PostToolUse, so its writes go unchecked.
#
# Fails open like the Edit/Write after-check: no marker, no
# work tree, or no git, jq or python3 all exit 0 silently.
#
# stdin: the hook payload JSON, read for tool_use_id
# exit: 2 when a changed file has findings, else 0

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROSE_HOOK="$script_dir/claude-prose-format-posttool-hook.sh"
MARKER_DIR="${TMPDIR:-/tmp}/claude-bash-prose-aftercheck"

# CHANGED_SINCE_MARKER_PY reads git's NUL-separated paths and
# prints, NUL-separated and absolute, those whose mtime or
# ctime is newer than the marker's. A listed path that no
# longer exists, such as a deleted tracked file, is skipped.
CHANGED_SINCE_MARKER_PY='
import os, sys
marker_ns = os.stat(sys.argv[1]).st_mtime_ns
seen = set()
for path in sys.stdin.buffer.read().split(b"\0"):
    if not path or path in seen:
        continue
    seen.add(path)
    try:
        stat = os.stat(path)
    except OSError:
        continue
    if max(stat.st_mtime_ns, stat.st_ctime_ns) > marker_ns:
        sys.stdout.buffer.write(os.path.abspath(path) + b"\0")
'

input=$(cat)
tool_use_id=$(printf '%s' "$input" | jq -r '.tool_use_id // empty' 2>/dev/null)

# why: the id becomes a file name, so a "/" or ".." in it
# could reach outside the marker directory.
case "$tool_use_id" in
  "" | *[!A-Za-z0-9_-]*) exit 0 ;;
esac
marker="$MARKER_DIR/$tool_use_id"

if [ "${1:-}" = "--mark" ]; then
  mkdir -p "$MARKER_DIR" 2>/dev/null || exit 0
  : > "$marker" 2>/dev/null
  exit 0
fi

[ -f "$marker" ] || exit 0

# why: this is the hook's one git call, so it is also the
# work-tree check; ":/" lists the whole tree from a subdir.
status=0
while IFS= read -r -d '' changed_path; do
  jq -n --arg path "$changed_path" '{tool_name: "Write", tool_input: {file_path: $path}}' \
    | bash "$PROSE_HOOK" || status=2
done < <(git ls-files -m -o --exclude-standard -z -- ':/' 2>/dev/null \
  | python3 -c "$CHANGED_SINCE_MARKER_PY" "$marker" 2>/dev/null)

rm -f "$marker"
exit "$status"
