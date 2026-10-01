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

# write_clean_shell_file - a shell file whose comments
# already satisfy every comment-format rule.
write_clean_shell_file() {
  local path="$1"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# Greet the operator.\n'
    printf 'echo hello\n'
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

# run_gate_with_checker - same, with the checker path
# overridden, which is the seam the infrastructure-failure
# cases need.
run_gate_with_checker() {
  local repo="$1" checker="$2" command="$3"
  GATE_STDERR=$(cd "$repo" \
    && CHECK_COMMENT_FORMAT_JS="$checker" bash "$SCRIPT" "$command" 2>&1 >/dev/null)
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

# A pathspec the shell has not expanded yet cannot be
# resolved, so the command string contributes nothing and
# the index alone decides.
it_should_fall_back_to_the_index_when_a_pathspec_is_a_variable() {
  local repo
  repo=$(new_repo unit3clean)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git add $FILES && git commit -m "x"'

  assert_eq "should allow a commit naming files through a variable when the index is clean" \
    0 "$GATE_EXIT"
  assert_contains "should say the file set could not be read from the command string" \
    "command string" "$GATE_STDERR"
}

it_should_still_judge_the_index_when_a_pathspec_is_a_variable() {
  local repo
  repo=$(new_repo unit3staged)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate "$repo" 'git add $FILES && git commit -m "x"'

  assert_eq "should block on the index verdict when the command names files through a variable" \
    1 "$GATE_EXIT"
}

# A staged file no comment lexer covers must not decide
# the run for the files that do lex.
it_should_allow_a_staged_markdown_file_beside_a_clean_shell_file() {
  local repo
  repo=$(new_repo unit4clean)
  write_clean_shell_file "$repo/greet.sh"
  printf '# Notes\n' > "$repo/notes.md"
  git -C "$repo" add greet.sh notes.md

  run_gate "$repo" 'git commit -m "x"'

  assert_eq "should allow a commit mixing a markdown file with a clean shell file" \
    0 "$GATE_EXIT"
}

it_should_block_a_shell_violation_staged_beside_a_markdown_file() {
  local repo
  repo=$(new_repo unit4violating)
  write_violating_shell_file "$repo/deploy.sh"
  printf '# Notes\n' > "$repo/notes.md"
  git -C "$repo" add deploy.sh notes.md

  run_gate "$repo" 'git commit -m "x"'

  assert_eq "should still block the shell violation when a markdown file is staged too" \
    1 "$GATE_EXIT"
  assert_contains "should name the shell file rather than the markdown one" \
    "deploy.sh" "$GATE_STDERR"
}

# Blocking every commit in the repo on a broken gate is a
# worse failure than missing one violation, so
# infrastructure trouble always fails open.
it_should_allow_the_commit_when_the_checker_is_missing() {
  local repo
  repo=$(new_repo unit5missing)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate_with_checker "$repo" "$tmp_root/no-such-checker.js" \
    'git add deploy.sh && git commit -m "x"'

  assert_eq "should allow the commit when the comment checker is not installed" \
    0 "$GATE_EXIT"
  assert_contains "should warn that the comment checker could not be found" \
    "comment checker" "$GATE_STDERR"
}

it_should_allow_the_commit_when_the_checker_reports_trouble() {
  local repo checker
  repo=$(new_repo unit5broken)
  write_violating_shell_file "$repo/deploy.sh"
  checker="$tmp_root/broken-checker.js"
  printf 'process.exit(2);\n' > "$checker"

  run_gate_with_checker "$repo" "$checker" \
    'git add deploy.sh && git commit -m "x"'

  assert_eq "should allow the commit when the comment checker exits with trouble" \
    0 "$GATE_EXIT"
  assert_contains "should warn that the comment checker could not reach a verdict" \
    "comment checker" "$GATE_STDERR"
}

it_should_block_a_violation_in_a_file_the_command_stages
it_should_ignore_a_git_add_quoted_inside_a_commit_message
it_should_block_a_violation_in_an_already_staged_file
it_should_fall_back_to_the_index_when_a_pathspec_is_a_variable
it_should_still_judge_the_index_when_a_pathspec_is_a_variable
it_should_allow_a_staged_markdown_file_beside_a_clean_shell_file
it_should_block_a_shell_violation_staged_beside_a_markdown_file
it_should_allow_the_commit_when_the_checker_is_missing
it_should_allow_the_commit_when_the_checker_reports_trouble

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
