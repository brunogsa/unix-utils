#!/usr/bin/env bash
# get-changed-lines.sh - Print changed line numbers vs HEAD
# to enable --changed-only scoping in doc-standards checkers.
#
# Usage:
#   get-changed-lines.sh <file>
#
# Output: one changed line number per line, ascending, unique,
# to stdout.
#
# Exit codes:
#   0  ran cleanly - empty output on an unmodified tracked
#      file is a normal result, not an error.
#
#   2  usage error: not inside a git work tree, file is
#      missing, or file sits outside the work tree.
#
# Rules:
# - Untracked (new, never `git add`ed) -> every line is
#   "changed".
#
# - Tracked and different from HEAD -> only the lines
#   `git diff -U0 HEAD` reports as added.
#
# - Tracked and identical to HEAD -> empty output, exit 0.
#
# - Renamed vs HEAD (`git mv`, staged or not) -> only the lines
#   that differ from the rename source, so a pure rename
#   reports nothing.
#
#   A file that is staged but never committed still differs
#   from HEAD, so it falls into the second case. Its whole
#   content comes back as changed - same result as the
#   untracked case, with no separate branch needed.
#
# - During a merge (MERGE_HEAD present) -> only the lines new
#   against HEAD and against every merged commit, so a line one
#   parent already holds is not the committer's.
#
# This is the one hunk-parser every doc-standards script and
# stop hook needs.
#
# Before this helper existed, ~/.claude/hooks/claude-{markdown-
# standards,comment-format}-stop-hook.sh each carried a
# byte-identical copy of the awk below.

set -eo pipefail

usage() {
  echo "usage: get-changed-lines.sh <file>" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
file=$1

command -v git >/dev/null 2>&1 || {
  echo "get-changed-lines.sh: git not found" >&2
  exit 2
}

[ -f "$file" ] || {
  echo "get-changed-lines.sh: no such file: $file" >&2
  exit 2
}

# Resolve against the FILE's own directory, never the invoker's
# cwd - a caller `cd`'d into one repo while pointing at a file
# that lives in a different one must still see that other repo's
# git state, not its own.
file_dir=$(cd "$(dirname -- "$file")" && pwd -P)
abs_file="$file_dir/$(basename -- "$file")"

git -C "$file_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "get-changed-lines.sh: not inside a git work tree" >&2
  exit 2
}

repo_root=$(git -C "$file_dir" rev-parse --show-toplevel)

rel_file=${abs_file#"$repo_root"/}
if [ "$rel_file" = "$abs_file" ]; then
  echo "get-changed-lines.sh: $file is outside the git work tree" >&2
  exit 2
fi

cd "$repo_root"

untracked=$(git ls-files --others --exclude-standard -- "$rel_file" 2>/dev/null || true)
if [ -n "$untracked" ]; then
  # `./` prefix, not `--`, guards a dash-leading rel_file - BSD
  # awk (macOS) reads `--` itself as a filename, failing there.
  awk '{ print NR }' "./$rel_file"
  exit 0
fi

# rename_source - prints the HEAD path rel_file was renamed
# from, or nothing when rel_file is not a rename.
#
# Without it, a renamed file is absent at HEAD, so every line
# reads as changed and a pure rename of a legacy file gets
# blocked over violations it never touched.
#
# -z keeps paths with spaces or quotes intact; a rename record
# is status, source, destination, each NUL-terminated.
rename_source() {
  git diff -M -z --name-status HEAD 2>/dev/null |
    while IFS= read -r -d '' status; do
      IFS= read -r -d '' path_a
      case $status in
        R*)
          IFS= read -r -d '' path_b
          if [ "$path_b" = "$rel_file" ]; then
            printf '%s' "$path_a"
            return
          fi
          ;;
      esac
    done || true
}

src_file=$(rename_source)

# print_added_lines - reads a -U0 diff on stdin and prints
# each working-tree line number its hunks add, once.
print_added_lines() {
  awk '
    /^@@ / {
      plus = $3; sub(/^\+/, "", plus);
      n = split(plus, a, ",");
      start = a[1] + 0; cnt = (n > 1 ? a[2] + 0 : 1);
      for (i = 0; i < cnt; i++) print start + i;
    }' | sort -un
}

# A stopped `git merge` lists one merged commit per line, and
# --git-path finds a linked worktree's own MERGE_HEAD.
merge_head_file=$(git rev-parse --git-path MERGE_HEAD)
merge_heads=()
if [ -f "$merge_head_file" ]; then
  while IFS= read -r merge_head; do
    [ -n "$merge_head" ] && merge_heads+=("$merge_head")
  done < "$merge_head_file"
fi
line_set_count=$((1 + ${#merge_heads[@]}))

# Listing both paths keeps git's rename pairing, so the hunks
# compare the rename source against rel_file.
#
# Every diff numbers lines in the same working-tree file, so a
# line printed by all of them is new against every parent.
{
  git diff -U0 -M HEAD -- ${src_file:+"$src_file"} "$rel_file" 2>/dev/null |
    print_added_lines
  for merge_head in "${merge_heads[@]}"; do
    git diff -U0 "$merge_head" -- "$rel_file" 2>/dev/null | print_added_lines
  done
} | sort -n | uniq -c |
  awk -v sets="$line_set_count" '$1 == sets { print $2 }'
