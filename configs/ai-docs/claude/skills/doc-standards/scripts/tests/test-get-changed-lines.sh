#!/usr/bin/env bash
# test-get-changed-lines.sh - plain-bash test file for
# get-changed-lines.sh.
#
# Usage:
#   bash test-get-changed-lines.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching this skill area's other
# test suites.
#
# Each case builds its own throwaway git repo, since the
# script's whole contract is "what does git say changed" - there
# is nothing to assert without a real repo underneath it.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/get-changed-lines.sh"

# pwd -P resolves /var -> /private/var on macOS.
# The script anchors on `git rev-parse --show-toplevel`, always
# physical, so an unresolved work_dir would make every
# relative-path comparison miss.
work_dir=$(cd "$(mktemp -d)" && pwd -P)
missing_out="$(mktemp)"
run_tmp="$(mktemp -d)"
trap 'rm -rf "$work_dir" "$run_tmp"; rm -f "$missing_out"' EXIT

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

# new_repo - creates an empty git repo under work_dir and prints
# its path.
# Identity is set locally so the fixture commit never depends on
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

# --- Case 3: tracked, modified -> only the added lines vs HEAD
# ---
repo=$(new_repo repo3)
printf 'one\ntwo\nthree\n' > "$repo/mod.txt"
git -C "$repo" add mod.txt
git -C "$repo" commit -q -m base
printf 'one\ntwo\nthree\nfour\nfive\n' > "$repo/mod.txt"
out=$(cd "$repo" && "$SCRIPT" mod.txt)
assert_eq "modified tracked file reports only appended lines" "$(printf '4\n5')" "$out"

# --- Case 4: tracked, staged-but-uncommitted new file -> whole
# file, via diff-vs-HEAD (not untracked) branch. Needs initial
# commit so HEAD exists for `git diff HEAD` to compare against;
# unborn HEAD makes the diff fail silently.
repo=$(new_repo repo4)
git -C "$repo" commit -q --allow-empty -m base
printf 'a\nb\n' > "$repo/staged.txt"
git -C "$repo" add staged.txt
out=$(cd "$repo" && "$SCRIPT" staged.txt)
assert_eq "staged-but-uncommitted new file reports every line" "$(printf '1\n2')" "$out"

# --- Case 5: file missing -> exit 2 ---
repo=$(new_repo repo5)
git -C "$repo" commit -q --allow-empty -m base
(cd "$repo" && "$SCRIPT" missing.txt) >"$missing_out" 2>&1
rc=$?
assert_eq "missing file exits 2" "2" "$rc"

# --- Case 6: not inside a git work tree -> exit 2 ---
plain_dir="$work_dir/plain"
mkdir -p "$plain_dir"
printf 'x\n' > "$plain_dir/file.txt"
(cd "$plain_dir" && "$SCRIPT" file.txt) >"$run_tmp/get-changed-lines-norepo.out" 2>&1
rc=$?
assert_eq "outside a git work tree exits 2" "2" "$rc"

# --- Case 7: no argument -> usage error, exit 2 ---
"$SCRIPT" >"$run_tmp/get-changed-lines-noargs.out" 2>&1
rc=$?
assert_eq "no argument exits 2" "2" "$rc"

# --- Case 8: file reached through a symlinked directory still
# resolves --- `git rev-parse --show-toplevel` is always
# physical, so a caller reaching the same repo through a symlink
# must still match it once abs_file is resolved.
repo=$(new_repo repo8)
printf 'one\ntwo\n' > "$repo/mod.txt"
git -C "$repo" add mod.txt
git -C "$repo" commit -q -m base
printf 'one\ntwo\nthree\n' > "$repo/mod.txt"
link="$work_dir/repo8-link"
ln -s "$repo" "$link"
out=$(cd "$link" && "$SCRIPT" mod.txt)
assert_eq "file reached via a symlinked dir still resolves" "3" "$out"

# --- Case 9: invoked from an unrelated repo's cwd, targeting a
# file that lives in a DIFFERENT repo via an absolute path ->
# must resolve against the file's OWN repo, not the invoker's
# cwd repo.
#
# Regression test for the bug where `git rev-parse
# --is-inside-work-tree` / `--show-toplevel` ran bare and
# silently picked up the invoker's cwd instead of the target
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

# --- Case 10: tracked, modified, dash-leading bare filename ->
# dirname/basename must not parse it as an option.
#
# Regression test for the bug where a bare relative filename
# starting with `-` (no directory component) got parsed as an
# option by `dirname`/`basename` instead of as a path.
repo=$(new_repo repo10)
printf 'one\ntwo\nthree\n' > "$repo/-dashfile.md"
git -C "$repo" add -- -dashfile.md
git -C "$repo" commit -q -m base
printf 'one\ntwo\nthree\nfour\n' > "$repo/-dashfile.md"
out=$(cd "$repo" && "$SCRIPT" -dashfile.md)
rc=$?
assert_eq "tracked modified dash-leading filename reports appended line" "4" "$out"
assert_eq "tracked modified dash-leading filename exits 0" "0" "$rc"

# --- Case 11: untracked, dash-leading bare filename -> every
# line counts as changed. Exercises the awk site on the
# untracked branch, where `--` does not work on BSD awk.
repo=$(new_repo repo11)
printf 'one\ntwo\nthree\n' > "$repo/-dashfile.md"
out=$(cd "$repo" && "$SCRIPT" -dashfile.md)
assert_eq "untracked dash-leading filename reports every line" "$(printf '1\n2\n3')" "$out"

# --- Case 12: `git mv` with no content change -> nothing
# changed.
#
# The new path is absent at HEAD, so a plain diff vs HEAD would
# report every line; the rename source is the right baseline,
# which lets a pure rename of a legacy file through the
# comment-format guard.
repo=$(new_repo repo12)
printf 'alpha\nbravo\ncharlie\ndelta\necho\nfoxtrot\n' > "$repo/old-name.md"
git -C "$repo" add old-name.md
git -C "$repo" commit -q -m base
git -C "$repo" mv old-name.md new-name.md
out=$(cd "$repo" && "$SCRIPT" new-name.md)
rc=$?
assert_eq "file renamed with no content change reports no changed lines" "" "$out"
assert_eq "file renamed with no content change exits 0" "0" "$rc"

# --- Case 13: `git mv` plus one edited line -> only that line.
repo=$(new_repo repo13)
printf 'alpha\nbravo\ncharlie\ndelta\necho\nfoxtrot\n' > "$repo/old-name.md"
git -C "$repo" add old-name.md
git -C "$repo" commit -q -m base
git -C "$repo" mv old-name.md new-name.md
printf 'alpha\nbravo\nCHARLIE edited\ndelta\necho\nfoxtrot\n' > "$repo/new-name.md"
out=$(cd "$repo" && "$SCRIPT" new-name.md)
assert_eq "file renamed with one edited line reports only that line" "3" "$out"

# --- Case 14: staged new file while an unrelated tracked file
# is deleted -> still every line.
#
# Rename detection sees an add and a delete in the same diff;
# dissimilar content must not be paired into a rename that
# hides the new file's lines.
repo=$(new_repo repo14)
printf 'alpha\nbravo\ncharlie\n' > "$repo/removed.md"
git -C "$repo" add removed.md
git -C "$repo" commit -q -m base
git -C "$repo" rm -q removed.md
printf 'one\ntwo\nthree\n' > "$repo/added.md"
git -C "$repo" add added.md
out=$(cd "$repo" && "$SCRIPT" added.md)
assert_eq "staged new file unrelated to a deleted file reports every line" "$(printf '1\n2\n3')" "$out"

# new_repo_with_base_file - a repo whose single base commit
# holds an 8-line file at $2, the shared ancestor every merge
# case below branches from.
new_repo_with_base_file() {
  local repo
  repo=$(new_repo "$1")
  printf 'alpha\nbravo\ncharlie\ndelta\necho\nfoxtrot\ngolf\nhotel\n' > "$repo/$2"
  git -C "$repo" add -- "$2"
  git -C "$repo" commit -q -m base
  printf '%s' "$repo"
}

# --- Case 15: merge into a branch that renamed the file, from
# a branch that edited it under the old name -> only the line
# written during the merge.
#
# The merged branch holds the file under its old path only, so
# without pairing that rename every line reads as new against
# it, and its own edit gets blamed on the committer.
#
# The path carries a space, which a word-split path would break.
repo=$(new_repo_with_base_file repo15 'old name.md')
git -C "$repo" checkout -q -b incoming
printf 'alpha\nBRAVO incoming\ncharlie\ndelta\necho\nfoxtrot\ngolf\nhotel\n' > "$repo/old name.md"
git -C "$repo" commit -q -am "edit on incoming"
git -C "$repo" checkout -q -
git -C "$repo" mv 'old name.md' 'new name.md'
printf 'alpha\nbravo\ncharlie\ndelta\necho\nfoxtrot\nGOLF current\nhotel\n' > "$repo/new name.md"
git -C "$repo" commit -q -am "rename and edit on current"
git -C "$repo" merge -q --no-ff --no-commit incoming >/dev/null 2>&1
printf 'india written during the merge\n' >> "$repo/new name.md"
out=$(cd "$repo" && "$SCRIPT" 'new name.md')
assert_eq "merge onto a rename reports only the line written during the merge, not the merged branch's edit" "9" "$out"

# --- Case 16: merge into a branch that only renamed the file,
# from a branch that edited it under the old name -> nothing.
repo=$(new_repo_with_base_file repo16 old-name.md)
git -C "$repo" checkout -q -b incoming
printf 'alpha\nBRAVO incoming\ncharlie\ndelta\necho\nfoxtrot\ngolf\nhotel\n' > "$repo/old-name.md"
git -C "$repo" commit -q -am "edit on incoming"
git -C "$repo" checkout -q -
git -C "$repo" mv old-name.md new-name.md
git -C "$repo" commit -q -m "rename on current"
git -C "$repo" merge -q --no-ff --no-commit incoming >/dev/null 2>&1
out=$(cd "$repo" && "$SCRIPT" new-name.md)
assert_eq "merge onto a pure rename reports nothing when every changed line came from the merged branch" "" "$out"

# --- Case 17: octopus merge of two branches, where only the
# second still holds the file under its old name -> only the
# line written during the merge.
#
# Octopus merges detect no renames, so the second branch's edit
# to the old path stops as a conflict; the committer resolves it
# by carrying that edit into the renamed file.
repo=$(new_repo_with_base_file repo17 old-name.md)
git -C "$repo" checkout -q -b second
printf 'alpha\nBRAVO second\ncharlie\ndelta\necho\nfoxtrot\ngolf\nhotel\n' > "$repo/old-name.md"
git -C "$repo" commit -q -am "edit on second"
git -C "$repo" checkout -q -
git -C "$repo" mv old-name.md new-name.md
git -C "$repo" commit -q -m "rename on current"
git -C "$repo" checkout -q -b first
printf 'unrelated\n' > "$repo/other.md"
git -C "$repo" add other.md
git -C "$repo" commit -q -m "unrelated file on first"
git -C "$repo" checkout -q -
git -C "$repo" merge -q --no-ff --no-commit first second >/dev/null 2>&1
git -C "$repo" rm -q old-name.md
printf 'alpha\nBRAVO second\ncharlie\ndelta\necho\nfoxtrot\ngolf\nhotel\nindia written during the merge\n' > "$repo/new-name.md"
git -C "$repo" add new-name.md
out=$(cd "$repo" && "$SCRIPT" new-name.md)
assert_eq "octopus merge onto a rename reports only the line written during the merge, not the old-path branch's edit" "9" "$out"

# --- Case 18: merge from a branch that renamed the file into
# one that edited it under the old name -> only the line written
# during the merge.
#
# The merged branch already holds the new path here, so this
# case passes without rename pairing against it; it guards that
# path while the pairing logic changes.
repo=$(new_repo_with_base_file repo18 old-name.md)
git -C "$repo" checkout -q -b incoming
git -C "$repo" mv old-name.md new-name.md
printf 'alpha\nBRAVO incoming\ncharlie\ndelta\necho\nfoxtrot\ngolf\nhotel\n' > "$repo/new-name.md"
git -C "$repo" commit -q -am "rename and edit on incoming"
git -C "$repo" checkout -q -
printf 'alpha\nbravo\ncharlie\ndelta\necho\nfoxtrot\nGOLF current\nhotel\n' > "$repo/old-name.md"
git -C "$repo" commit -q -am "edit on current"
git -C "$repo" merge -q --no-ff --no-commit incoming >/dev/null 2>&1
printf 'india written during the merge\n' >> "$repo/new-name.md"
out=$(cd "$repo" && "$SCRIPT" new-name.md)
assert_eq "merge of a renaming branch reports only the line written during the merge" "9" "$out"

echo
echo "$pass_count passed, $fail_count failed"
[ "$fail_count" -eq 0 ]
