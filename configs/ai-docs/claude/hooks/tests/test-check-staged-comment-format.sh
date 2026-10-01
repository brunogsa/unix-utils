#!/usr/bin/env bash
# Plain-bash test file for
# lib/check-staged-comment-format.sh.
#
# Usage:
#   bash test-check-staged-comment-format.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design — matches
# the sibling hook suites in this directory.
#
# Every fixture repo gets a real initial commit: the
# checker's --changed-only scope comes from a `git diff`
# against HEAD, and a repo with no HEAD at all would
# make the gate fail open on every case below.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/lib/check-staged-comment-format.sh"

pass_count=0
fail_count=0

tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
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

# assert_contains - asserts the report carries a given
# substring, so the caller is told which file to fix
# rather than merely being refused.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to contain: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

# new_repo - fresh fixture repo with one commit, so
# HEAD exists and --changed-only can resolve a scope.
new_repo() {
  local name="$1" dir="$tmp_root/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q
  printf 'seed\n' > "$dir/seed.txt"
  git -C "$dir" add seed.txt
  git -C "$dir" -c user.email=suite@example.com \
    -c user.name='Hook Suite' commit -qm 'seed'
  printf '%s' "$dir"
}

# write_violating_shell_file - a shell file whose one
# comment line runs past the 64-character width cap.
write_violating_shell_file() {
  local path="$1"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# this comment line runs well past the sixty-four character width cap\n'
    printf 'echo deploying\n'
  } > "$path"
}

# run_gate - invokes the gate from inside a fixture repo
# with the given commit command string. Captures the exit
# code into GATE_EXIT and the report into GATE_STDERR.
run_gate() {
  local repo="$1" command="$2"
  GATE_STDERR=$(cd "$repo" && bash "$SCRIPT" "$command" 2>&1 >/dev/null)
  GATE_EXIT=$?
}

# The index-timing trap: at PreToolUse the `git add` has
# not run yet, so a gate reading only the index would pass
# this commit vacuously.
it_should_block_a_violation_in_a_file_the_command_stages() {
  local repo
  repo=$(new_repo unit1)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git add deploy.sh && git commit -m "x"'

  assert_eq "should block a commit whose git add names an unstaged violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file the git add brought in" \
    "deploy.sh" "$GATE_STDERR"
}

# A `git add` appearing only inside a commit message is
# data, not structure — the shared parser drops heredoc
# bodies precisely so it is never read as a real one.
it_should_ignore_a_git_add_quoted_inside_a_commit_message() {
  local repo command
  repo=$(new_repo unit1heredoc)
  write_violating_shell_file "$repo/deploy.sh"
  command=$(printf 'git commit -m "$(cat <<%sEOF%s\nundo the git add deploy.sh step\nEOF\n)"' "'" "'")

  run_gate "$repo" "$command"

  assert_eq "should allow a commit that only quotes a git add inside its message" \
    0 "$GATE_EXIT"
}

# The index half of the union: a file already staged is
# part of the commit even when the command string names no
# file at all.
it_should_block_a_violation_in_an_already_staged_file() {
  local repo
  repo=$(new_repo unit2)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate "$repo" 'git commit -m "x"'

  assert_eq "should block a commit whose index already holds a violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file found in the index" \
    "release.sh" "$GATE_STDERR"
}

it_should_block_a_violation_in_a_file_the_command_stages
it_should_ignore_a_git_add_quoted_inside_a_commit_message
it_should_block_a_violation_in_an_already_staged_file

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
