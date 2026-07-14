#!/usr/bin/env bash
# extract-commentable-lines - list the new-file line numbers of `+` lines in a unified diff
#
# Usage:
#   extract-commentable-lines <diff-file>
#   gh pr diff 1234 --repo owner/repo | extract-commentable-lines -
#
# Output: one `path:line` per `+` line (the set of lines safe to anchor an inline comment on).
#
# Examples:
#   extract-commentable-lines /tmp/pr.diff                 # from file
#   gh pr diff 1 --repo o/r | extract-commentable-lines -  # from stdin
#   extract-commentable-lines /tmp/pr.diff | grep '^src/foo.ts:'

set -euo pipefail

if [[ $# -ne 1 || "$1" == "-h" || "$1" == "--help" ]]; then
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

src="$1"
if [[ "$src" == "-" ]]; then src=/dev/stdin; fi

awk '
  /^\+\+\+ b\// { path = substr($2, 3); next }
  /^\+\+\+ \/dev\/null/ { path = ""; next }
  /^@@/ {
    # @@ -a,b +c,d @@
    if (match($0, /\+[0-9]+/)) {
      new_line = substr($0, RSTART + 1, RLENGTH - 1) + 0
    }
    next
  }
  path == "" { next }
  /^\+\+\+ / { next }
  /^---/ { next }
  /^\+/ { print path ":" new_line; new_line++; next }
  /^-/  { next }              # deleted line — do not advance new-file counter
  /^\\/ { next }              # "\ No newline at end of file"
  /^ /  { new_line++; next }  # context line advances new-file counter
' "$src"
