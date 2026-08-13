#!/usr/bin/env bash
# prep-local-context.sh - assemble Wave 1 local-mode review
# context on disk
#
# Usage:
#   prep-local-context.sh <base_ref> <work_dir>
#
# stdin: none
# stdout: one "<name>: <path>" line per file written into
#   <work_dir>
# exit: 0 on success, 1 on bad input or an unresolvable
#   base ref

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

if [[ $# -ne 2 ]]; then
  echo "usage: prep-local-context.sh <base_ref> <work_dir>" >&2
  exit 1
fi

base_ref="$1"
work_dir="$2"

git rev-parse --show-toplevel >/dev/null 2>&1 \
  || { echo "prep-local-context: not inside a git repository" >&2; exit 1; }

# The caller owns work_dir's lifecycle (creation and
# cleanup); this only guards against a not-yet-created path,
# it never mktemps or removes anything of its own.
mkdir -p "$work_dir"

# A branch on origin diffs against the freshly fetched remote
# copy, so a stale local branch never silently narrows the
# diff. Anything else must already resolve locally (SHA,
# HEAD~N, tag).
if git ls-remote --exit-code --heads origin "$base_ref" >/dev/null 2>&1; then
  git fetch origin "$base_ref"
  base_rev="origin/$base_ref"
else
  git rev-parse --verify --quiet "$base_ref^{commit}" >/dev/null \
    || { echo "base ref '$base_ref' is neither a branch on origin nor a local commit-ish" >&2; exit 1; }
  base_rev="$base_ref"
fi

git diff -U20 "$base_rev...HEAD"             > "$work_dir/diff"
git diff      "$base_rev...HEAD" --name-only > "$work_dir/changed-files.txt"
git log       "$base_rev..HEAD" --format='%B%n---%n' > "$work_dir/commit-messages.txt"

bash "$script_dir/extract-commentable-lines.sh" \
  "$work_dir/diff" > "$work_dir/commentable-lines.txt"

bash "$script_dir/extract-skipped-files.sh" \
  "$work_dir/diff" "$work_dir"

added_lines=$(grep -c '^+[^+]' "$work_dir/diff" || echo 0)
tiny_pr=false
[ "$added_lines" -lt 100 ] && tiny_pr=true
echo "$tiny_pr" > "$work_dir/tiny-pr.txt"

for name in diff changed-files.txt commit-messages.txt commentable-lines.txt \
            skipped-binary.txt skipped-deleted.txt tiny-pr.txt; do
  echo "$name: $work_dir/$name"
done
