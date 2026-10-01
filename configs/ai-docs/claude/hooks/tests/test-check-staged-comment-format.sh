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

# assert_not_contains - asserts the report is free of a
# given substring, which is how a path that resolved a file
# set is told apart from one that gave up and warned.
assert_not_contains() {
  local description="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected not to contain: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
      ;;
    *)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
  esac
}

# new_repo - fresh fixture repo with one commit, so
# HEAD exists and --changed-only can resolve a scope.
new_repo() {
  local dir="$tmp_root/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q
  printf 'seed\n' > "$dir/seed.txt"
  git -C "$dir" add seed.txt
  git -C "$dir" -c user.email=suite@example.com \
    -c user.name='Hook Suite' commit -qm 'seed'
  printf '%s' "$dir"
}

# commit_tracked_file - commits a file into a fixture repo,
# so a later edit to it is a tracked modification rather
# than the untracked file `git commit -a` would skip.
commit_tracked_file() {
  local repo="$1" path="$2"
  git -C "$repo" add "$path"
  git -C "$repo" -c user.email=suite@example.com \
    -c user.name='Hook Suite' commit -qm "add $path"
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

# run_gate_from - invokes the gate from an arbitrary
# directory, which is how the `cd <repo> && git add ...`
# shape dispatched agents emit gets reproduced.
run_gate_from() {
  local from="$1" command="$2"
  GATE_STDERR=$(cd "$from" && bash "$SCRIPT" "$command" 2>&1 >/dev/null)
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

# Every dispatched agent here emits `cd <repo> && git add
# ... && git commit ...`, because its working directory
# resets on each call, so pathspecs are relative to the
# `cd` target rather than to the hook's own directory.
it_should_block_a_violation_staged_after_a_leading_cd() {
  local repo
  repo=$(new_repo unit6cd)
  mkdir -p "$repo/sub"
  write_violating_shell_file "$repo/sub/deploy.sh"

  run_gate_from "$repo/sub" \
    "cd $repo && git add sub/deploy.sh && git commit -m \"x\""

  assert_eq "should block a commit whose git add follows a leading cd into the repo root" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file the leading cd made reachable" \
    "deploy.sh" "$GATE_STDERR"
}

# `git -C <dir> add` is the same hole reached without a
# `cd`: the pathspecs are relative to <dir>, and <dir>
# alone moves them, leaving the hook's own directory
# irrelevant to where they live.
it_should_block_a_violation_staged_through_git_dash_c() {
  local repo
  repo=$(new_repo unit7dashc)
  mkdir -p "$repo/sub"
  write_violating_shell_file "$repo/sub/deploy.sh"

  run_gate_from "$repo/sub" \
    "git -C $repo add sub/deploy.sh && git commit -m \"x\""

  assert_eq "should block a commit whose git -C add names a violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file git -C made reachable" \
    "deploy.sh" "$GATE_STDERR"
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

# A `cd` the gate cannot follow leaves every later
# pathspec rooted nowhere it can name, so the command
# string is discarded whole rather than resolved against
# a directory that is merely the one it started in.
it_should_fall_back_to_the_index_when_a_cd_target_is_missing() {
  local repo
  repo=$(new_repo unit8missingdir)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" \
    "cd $tmp_root/no-such-dir && git add deploy.sh && git commit -m \"x\""

  assert_eq "should allow a commit whose cd target does not exist when the index is clean" \
    0 "$GATE_EXIT"
  assert_contains "should say the file set could not be read when the cd target is missing" \
    "command string" "$GATE_STDERR"
}

it_should_fall_back_to_the_index_when_a_cd_argument_is_a_variable() {
  local repo
  repo=$(new_repo unit8cdvar)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'cd "$(pwd)" && git add deploy.sh && git commit -m "x"'

  assert_eq "should allow a commit whose cd argument is a command substitution when the index is clean" \
    0 "$GATE_EXIT"
  assert_contains "should say the file set could not be read when the cd argument is non-literal" \
    "command string" "$GATE_STDERR"
}

it_should_still_judge_the_index_when_a_cd_argument_is_a_variable() {
  local repo
  repo=$(new_repo unit8cdvarstaged)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate "$repo" 'cd $HOME && git add deploy.sh && git commit -m "x"'

  assert_eq "should block on the index verdict when the cd argument is a variable" \
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

# `git commit -a` stages every tracked modified file at
# commit time, and the gate parses only `git add`
# pathspecs — so a `-a` commit left it with no file set at
# all, and the still-empty index then passed it in silence.
it_should_block_a_violation_git_commit_dash_a_would_stage() {
  local repo
  repo=$(new_repo unit9commitall)
  write_clean_shell_file "$repo/deploy.sh"
  commit_tracked_file "$repo" deploy.sh
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git commit -am "x"'

  assert_eq "should block a commit whose -a stages a violating tracked file" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file -a stages" \
    "deploy.sh" "$GATE_STDERR"
  assert_not_contains "should read the -a file set rather than warn it could not be read" \
    "command string" "$GATE_STDERR"
}

# `-a` names its set relative to the repo the commit runs
# in, so a leading `cd` moves that set the same way it
# moves an `add` pathspec.
it_should_block_a_commit_dash_a_violation_after_a_leading_cd() {
  local repo
  repo=$(new_repo unit9cdall)
  write_clean_shell_file "$repo/deploy.sh"
  commit_tracked_file "$repo" deploy.sh
  write_violating_shell_file "$repo/deploy.sh"

  run_gate_from "$tmp_root" "cd $repo && git commit -a -m \"x\""

  assert_eq "should block a -a commit whose tracked files live under a leading cd" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file the leading cd made reachable to -a" \
    "deploy.sh" "$GATE_STDERR"
}

# A `git -C <dir> commit` commits <dir>'s index, not the
# one where the shell happens to stand, so reading the
# caller's own directory judges the wrong repo entirely.
it_should_judge_the_index_of_the_repo_the_commit_dash_c_names() {
  local repo elsewhere
  repo=$(new_repo unit10dashccommit)
  elsewhere=$(new_repo unit10dashcotherrepo)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate_from "$elsewhere" "git -C $repo commit -m \"x\""

  assert_eq "should block on the index of the repo git -C commit names, not the caller's" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file staged in the repo git -C commit names" \
    "release.sh" "$GATE_STDERR"
}

it_should_judge_the_commit_dash_c_index_from_outside_any_repo() {
  local repo
  repo=$(new_repo unit10dashcnorepo)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate_from "$tmp_root" "git -C $repo commit -m \"x\""

  assert_eq "should block on the git -C commit index when the caller stands outside any repo" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file when the caller stands outside any repo" \
    "release.sh" "$GATE_STDERR"
}

# A `-C` target the gate cannot name lands in the same gap
# an unfollowable `cd` does: every later pathspec is rooted
# nowhere it can point at, so the whole command string is
# discarded and the index alone decides.
it_should_fall_back_to_the_index_when_a_git_dash_c_target_is_missing() {
  local repo
  repo=$(new_repo unit11dashcmissing)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" \
    "git -C $tmp_root/no-such-dir add deploy.sh && git commit -m \"x\""

  assert_eq "should allow a commit whose git -C target does not exist when the index is clean" \
    0 "$GATE_EXIT"
  assert_contains "should say the file set could not be read when the git -C target is missing" \
    "command string" "$GATE_STDERR"
}

it_should_fall_back_to_the_index_when_a_git_dash_c_target_is_non_literal() {
  local repo
  repo=$(new_repo unit11dashcsubst)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git -C "$(pwd)" add deploy.sh && git commit -m "x"'

  assert_eq "should allow a commit whose git -C target is a command substitution when the index is clean" \
    0 "$GATE_EXIT"
  assert_contains "should say the file set could not be read when the git -C target is non-literal" \
    "command string" "$GATE_STDERR"
}

it_should_still_judge_the_index_when_a_git_dash_c_target_is_a_variable() {
  local repo
  repo=$(new_repo unit11dashcvarstaged)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate "$repo" 'git -C $REPO add deploy.sh && git commit -m "x"'

  assert_eq "should block on the index verdict when the git -C target is a variable" \
    1 "$GATE_EXIT"
}

it_should_block_a_violation_in_a_file_the_command_stages
it_should_ignore_a_git_add_quoted_inside_a_commit_message
it_should_block_a_violation_staged_after_a_leading_cd
it_should_block_a_violation_staged_through_git_dash_c
it_should_block_a_violation_in_an_already_staged_file
it_should_fall_back_to_the_index_when_a_pathspec_is_a_variable
it_should_still_judge_the_index_when_a_pathspec_is_a_variable
it_should_fall_back_to_the_index_when_a_cd_target_is_missing
it_should_fall_back_to_the_index_when_a_cd_argument_is_a_variable
it_should_still_judge_the_index_when_a_cd_argument_is_a_variable
it_should_allow_a_staged_markdown_file_beside_a_clean_shell_file
it_should_block_a_shell_violation_staged_beside_a_markdown_file
it_should_allow_the_commit_when_the_checker_is_missing
it_should_allow_the_commit_when_the_checker_reports_trouble
it_should_block_a_violation_git_commit_dash_a_would_stage
it_should_block_a_commit_dash_a_violation_after_a_leading_cd
it_should_judge_the_index_of_the_repo_the_commit_dash_c_names
it_should_judge_the_commit_dash_c_index_from_outside_any_repo
it_should_fall_back_to_the_index_when_a_git_dash_c_target_is_missing
it_should_fall_back_to_the_index_when_a_git_dash_c_target_is_non_literal
it_should_still_judge_the_index_when_a_git_dash_c_target_is_a_variable

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
