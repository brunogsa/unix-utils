#!/usr/bin/env bash
# test-changed-lines.sh - plain-bash test file for changed-lines.sh.
#
# Usage:
#   bash test-changed-lines.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design, matching this skill area's other test suites.
#
# Each case builds its own throwaway git repo, since the script's whole
# contract is "what does git say changed" - there is nothing to assert
# without a real repo underneath it.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/changed-lines.sh"

# pwd -P resolves /var -> /private/var on macOS. The script anchors on
# `git rev-parse --show-toplevel`, always physical, so an unresolved
# work_dir would make every relative-path comparison miss.
work_dir=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# new_repo - creates an empty git repo under work_dir and prints its
# path. Identity is set locally so the fixture commit never depends on
# the machine's global git config.
new_repo() {
  local dir="$work_dir/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q .
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
  printf '%s' "$dir"
}

# --- Case 1: untracked file -> every line counts as changed ---
repo=$(new_repo repo1)
printf 'one\ntwo\nthree\n' > "$repo/new.txt"
out=$(cd "$repo" && "$SCRIPT" new.txt)
assert_eq "untracked file reports every line" "$(printf '1\n2\n3')" "$out"

# --- Case 2: tracked, unmodified -> empty output, exit 0 ---
repo=$(new_repo repo2)
printf 'one\ntwo\nthree\n' > "$repo/base.txt"
git -C "$repo" add base.txt
git -C "$repo" commit -q -m base
out=$(cd "$repo" && "$SCRIPT" base.txt)
rc=$?
assert_eq "unmodified tracked file reports nothing" "" "$out"
assert_eq "unmodified tracked file exits 0" "0" "$rc"

# --- Case 3: tracked, modified -> only the added lines vs HEAD ---
repo=$(new_repo repo3)
printf 'one\ntwo\nthree\n' > "$repo/mod.txt"
git -C "$repo" add mod.txt
git -C "$repo" commit -q -m base
printf 'one\ntwo\nthree\nfour\nfive\n' > "$repo/mod.txt"
out=$(cd "$repo" && "$SCRIPT" mod.txt)
assert_eq "modified tracked file reports only appended lines" "$(printf '4\n5')" "$out"

# --- Case 4: tracked, staged-but-uncommitted new file -> whole file, via
#     the diff-vs-HEAD branch rather than the untracked branch. Needs an
#     initial commit first so HEAD exists for `git diff HEAD` to compare
#     against - an unborn HEAD makes that diff fail silently.
repo=$(new_repo repo4)
git -C "$repo" commit -q --allow-empty -m base
printf 'a\nb\n' > "$repo/staged.txt"
git -C "$repo" add staged.txt
out=$(cd "$repo" && "$SCRIPT" staged.txt)
assert_eq "staged-but-uncommitted new file reports every line" "$(printf '1\n2')" "$out"

# --- Case 5: file missing -> exit 2 ---
repo=$(new_repo repo5)
git -C "$repo" commit -q --allow-empty -m base
(cd "$repo" && "$SCRIPT" missing.txt) >/tmp/changed-lines-missing.out 2>&1
rc=$?
assert_eq "missing file exits 2" "2" "$rc"

# --- Case 6: not inside a git work tree -> exit 2 ---
plain_dir="$work_dir/plain"
mkdir -p "$plain_dir"
printf 'x\n' > "$plain_dir/file.txt"
(cd "$plain_dir" && "$SCRIPT" file.txt) >/tmp/changed-lines-norepo.out 2>&1
rc=$?
assert_eq "outside a git work tree exits 2" "2" "$rc"

# --- Case 7: no argument -> usage error, exit 2 ---
"$SCRIPT" >/tmp/changed-lines-noargs.out 2>&1
rc=$?
assert_eq "no argument exits 2" "2" "$rc"

# --- Case 8: file reached through a symlinked directory still resolves ---
# `git rev-parse --show-toplevel` is always physical, so a caller reaching the
# same repo through a symlink must still match it once abs_file is resolved.
repo=$(new_repo repo8)
printf 'one\ntwo\n' > "$repo/mod.txt"
git -C "$repo" add mod.txt
git -C "$repo" commit -q -m base
printf 'one\ntwo\nthree\n' > "$repo/mod.txt"
link="$work_dir/repo8-link"
ln -s "$repo" "$link"
out=$(cd "$link" && "$SCRIPT" mod.txt)
assert_eq "file reached via a symlinked dir still resolves" "3" "$out"

# --- Case 9: invoked from an unrelated repo's cwd, targeting a file that
# lives in a DIFFERENT repo via an absolute path -> must resolve against
# the file's OWN repo, not the invoker's cwd repo. Regression test for the
# bug where `git rev-parse --is-inside-work-tree` / `--show-toplevel` ran
# bare and silently picked up the invoker's cwd instead of the target
# file's repo.
repo_a=$(new_repo repo9a)
git -C "$repo_a" commit -q --allow-empty -m base

repo_b=$(new_repo repo9b)
printf 'one\ntwo\nthree\n' > "$repo_b/mod.txt"
git -C "$repo_b" add mod.txt
git -C "$repo_b" commit -q -m base
printf 'one\ntwo\nthree\nfour\n' > "$repo_b/mod.txt"

out=$(cd "$repo_a" && "$SCRIPT" "$repo_b/mod.txt")
assert_eq "file in a different repo than the invoker's cwd still resolves against its own repo" "4" "$out"

echo
echo "$pass_count passed, $fail_count failed"
[ "$fail_count" -eq 0 ]
