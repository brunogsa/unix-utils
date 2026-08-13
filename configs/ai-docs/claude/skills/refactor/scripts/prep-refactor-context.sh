#!/usr/bin/env bash
# prep-refactor-context.sh - assemble /refactor's on-disk
# context: unpushed commits, staged + unstaged changes, and
# untracked files, scoped to optional path arguments.
#
# Usage:
#   prep-refactor-context.sh <work_dir> [<path>...]
#
# stdin: none
# stdout: one "<name>: <path>" line per file written into
#   <work_dir>
# exit: 0 on success, 1 on bad input, an unresolvable base
#   ref, or an empty scope (nothing changed, nothing untracked)

set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "usage: prep-refactor-context.sh <work_dir> [<path>...]" >&2
  exit 1
fi

work_dir="$1"
shift

git rev-parse --show-toplevel >/dev/null 2>&1 \
  || { echo "prep-refactor-context: not inside a git repository" >&2; exit 1; }

# @{upstream} when the branch tracks a remote, else the repo
# default branch, which is all a fresh /implement branch has:
# its tail runs before the first push.
base=$(git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>/dev/null) \
  || base=$(~/.claude/scripts/resolve-base-ref.sh) \
  || { echo "prep-refactor-context: could not resolve a base ref (no upstream, no origin/HEAD, no local main or master)" >&2; exit 1; }

# The merge-base, not $base directly: if $base has advanced past
# this branch, diffing $base itself renders its own newer commits
# as reversed changes this branch never made. Diffing from the
# merge-base to the working tree is the three-dot-diff equivalent
# for a right-hand side that is the working tree, not a commit
# (three-dot syntax requires both sides to be commits).
merge_base=$(git merge-base "$base" HEAD)

# The caller owns work_dir's lifecycle (creation and cleanup);
# this only guards against a not-yet-created path, it never
# mktemps or removes anything of its own.
mkdir -p "$work_dir"

git diff -U20 "$merge_base" -- "$@" > "$work_dir/diff"
git ls-files --others --exclude-standard -- "$@" > "$work_dir/untracked-files.txt"

tracked_changed="$work_dir/.tracked-changed.tmp"
git diff --name-only "$merge_base" -- "$@" > "$tracked_changed"
sort -u "$tracked_changed" "$work_dir/untracked-files.txt" > "$work_dir/changed-files.txt"
rm -f "$tracked_changed"

git log "$merge_base"..HEAD --format='%B%n---%n' -- "$@" > "$work_dir/commit-messages.txt"

if [ ! -s "$work_dir/changed-files.txt" ]; then
  echo "prep-refactor-context: nothing to refactor -- no changed or untracked files in the given scope" >&2
  exit 1
fi

for name in diff changed-files.txt untracked-files.txt commit-messages.txt; do
  echo "$name: $work_dir/$name"
done
