#!/usr/bin/env bash
# extract-skipped-files - list binary and deleted files from a unified diff
#
# Usage:
#   extract-skipped-files <diff-file> <output-dir>
#   gh pr diff 1234 --repo owner/repo | extract-skipped-files - <output-dir>
#
# Output: writes two files into <output-dir>:
#   skipped-binary.txt   — one path per line, files the diff reports as binary
#   skipped-deleted.txt  — one path per line, files removed by the diff
#
# Examples:
#   extract-skipped-files /tmp/pr.diff /tmp/pr-review-42/
#   gh pr diff 1 --repo o/r | extract-skipped-files - /tmp/work/

set -euo pipefail

if [[ $# -ne 2 || "$1" == "-h" || "$1" == "--help" ]]; then
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

src="$1"
out_dir="$2"

if [[ "$src" == "-" ]]; then src=/dev/stdin; fi
mkdir -p "$out_dir"

grep -E '^Binary files ' "$src" \
  | sed 's/^Binary files a\/\(.*\) and.*$/\1/' \
  > "$out_dir/skipped-binary.txt" || true

awk '
  /^diff --git / { p = $3; sub("^a/", "", p) }
  /^\+\+\+ \/dev\/null/ { print p }
' "$src" > "$out_dir/skipped-deleted.txt" || true
