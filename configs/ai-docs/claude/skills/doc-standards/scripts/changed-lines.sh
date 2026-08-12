#!/usr/bin/env bash
# changed-lines.sh - Print changed line numbers vs HEAD
# to enable --changed-only scoping in doc-standards checkers.
#
# Usage:
#   changed-lines.sh <file>
#
# Output: one changed line number per line, ascending, unique,
# to stdout.
#
# Exit codes:
#   0  ran cleanly - empty output on an unmodified tracked file is a
#      normal result, not an error.
#
#   2  usage error, not inside a git work tree, file missing, or the file
#      sits outside the work tree.
#
# Rules:
# - Untracked (new, never `git add`ed) -> every line is
#   "changed".
#
# - Tracked and different from HEAD -> only the lines `git diff
#   -U0
#     HEAD` reports as added.
#
# - Tracked and identical to HEAD -> empty output, exit 0.
#
#   A file that is staged but never committed still differs from HEAD, so
#   it falls into the second case and its whole content comes back as
#   changed - same result as the untracked case, with no separate branch
#   needed for it.
#
# This is the one hunk-parser every doc-standards script and
# stop hook needs.
#
# Before this helper existed, ~/.claude/hooks/claude-{markdown-
# standards,comment-format}-stop-hook.sh each carried a
# byte-identical copy of the awk below.

set -eo pipefail

usage() {
  echo "usage: changed-lines.sh <file>" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
file=$1

command -v git >/dev/null 2>&1 || {
  echo "changed-lines.sh: git not found" >&2
  exit 2
}

[ -f "$file" ] || {
  echo "changed-lines.sh: no such file: $file" >&2
  exit 2
}

# Resolve against the FILE's own directory, never the invoker's
# cwd - a caller `cd`'d into one repo while pointing at a file
# that lives in a different one must still see that other repo's
# git state, not its own.
file_dir=$(cd "$(dirname "$file")" && pwd -P)
abs_file="$file_dir/$(basename "$file")"

git -C "$file_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "changed-lines.sh: not inside a git work tree" >&2
  exit 2
}

repo_root=$(git -C "$file_dir" rev-parse --show-toplevel)

rel_file=${abs_file#"$repo_root"/}
if [ "$rel_file" = "$abs_file" ]; then
  echo "changed-lines.sh: $file is outside the git work tree" >&2
  exit 2
fi

cd "$repo_root"

untracked=$(git ls-files --others --exclude-standard -- "$rel_file" 2>/dev/null || true)
if [ -n "$untracked" ]; then
  awk '{ print NR }' "$rel_file"
  exit 0
fi

git diff -U0 HEAD -- "$rel_file" 2>/dev/null | awk '
    /^@@ / {
      plus = $3; sub(/^\+/, "", plus);
      n = split(plus, a, ",");
      start = a[1] + 0; cnt = (n > 1 ? a[2] + 0 : 1);
      for (i = 0; i < cnt; i++) print start + i;
    }' | sort -un
