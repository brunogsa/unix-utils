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

# A `-C` the gate cannot name on the `commit` stage itself
# leaves it unable to say which repository the commit even
# lands in, so the `-a` set goes unread rather than being
# resolved against whichever repo the caller stands in.
it_should_fall_back_to_the_index_when_a_committing_git_dash_c_target_is_missing() {
  local repo
  repo=$(new_repo unit12commitdashcmissing)
  write_clean_shell_file "$repo/deploy.sh"
  commit_tracked_file "$repo" deploy.sh
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" "git -C $tmp_root/no-such-dir commit -am \"x\""

  assert_eq "should allow a -a commit whose git -C target does not exist when the index is clean" \
    0 "$GATE_EXIT"
  assert_contains "should say the file set could not be read when the committing git -C target is missing" \
    "command string" "$GATE_STDERR"
}

it_should_still_judge_the_index_when_a_committing_git_dash_c_target_is_missing() {
  local repo
  repo=$(new_repo unit12commitdashcstaged)
  write_violating_shell_file "$repo/release.sh"
  git -C "$repo" add release.sh

  run_gate "$repo" "git -C $tmp_root/no-such-dir commit -m \"x\""

  assert_eq "should block on the index verdict when the committing git -C target is missing" \
    1 "$GATE_EXIT"
}

# diff.relative=true makes `git diff --name-only` answer
# relative to the subdirectory it runs in, which the gate
# would then join onto the repo root and drop as missing.
it_should_block_a_staged_violation_when_diff_relative_is_set_in_a_subdirectory() {
  local repo
  repo=$(new_repo unit13diffrelative)
  git -C "$repo" config diff.relative true
  mkdir -p "$repo/sub"
  write_violating_shell_file "$repo/sub/deploy.sh"
  git -C "$repo" add sub/deploy.sh

  run_gate "$repo/sub" 'git commit -m "x"'

  assert_eq "should block a staged violation when diff.relative is set and the commit runs in a subdirectory" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file when diff.relative is set" \
    "deploy.sh" "$GATE_STDERR"
}

it_should_block_a_commit_dash_a_violation_when_diff_relative_is_set_in_a_subdirectory() {
  local repo
  repo=$(new_repo unit13diffrelativeall)
  git -C "$repo" config diff.relative true
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/deploy.sh"
  commit_tracked_file "$repo" sub/deploy.sh
  write_violating_shell_file "$repo/sub/deploy.sh"

  run_gate "$repo/sub" 'git commit -am "x"'

  assert_eq "should block a commit -a violation when diff.relative is set and the commit runs in a subdirectory" \
    1 "$GATE_EXIT"
}

# `git commit <pathspec>` commits the working-tree version
# of that path and never consults the index.
it_should_block_a_violation_in_a_file_named_as_a_commit_pathspec() {
  local repo
  repo=$(new_repo unit14commitpathspec)
  write_clean_shell_file "$repo/deploy.sh"
  commit_tracked_file "$repo" deploy.sh
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git commit deploy.sh -m "x"'

  assert_eq "should block a commit whose pathspec names an unstaged violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the offending file the commit pathspec brought in" \
    "deploy.sh" "$GATE_STDERR"
}

it_should_block_a_violation_in_a_file_named_after_a_commit_double_dash() {
  local repo
  repo=$(new_repo unit14commitdoubledash)
  write_clean_shell_file "$repo/deploy.sh"
  commit_tracked_file "$repo" deploy.sh
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git commit -m "x" -- deploy.sh'

  assert_eq "should block a commit whose pathspec follows a double dash" \
    1 "$GATE_EXIT"
}

it_should_not_read_a_commit_option_value_as_a_pathspec() {
  local repo
  repo=$(new_repo unit14commitvalue)
  write_clean_shell_file "$repo/clean.sh"

  run_gate "$repo" 'git commit -m "no-such-file.sh" --author "A <a@b.c>"'

  assert_eq "should allow a commit whose option values merely look like paths" \
    0 "$GATE_EXIT"
  assert_not_contains "should not warn when option values are skipped as pathspecs" \
    "command string" "$GATE_STDERR"
}

it_should_fall_back_to_the_index_when_a_commit_pathspec_is_a_variable() {
  local repo
  repo=$(new_repo unit14commitvariable)

  run_gate "$repo" 'git commit "$FILE" -m "x"'

  assert_contains "should say the file set could not be read when a commit pathspec is a variable" \
    "command string" "$GATE_STDERR"
}

# Two spellings of one directory (a symlinked temp root such
# as /var -> /private/var) must not hand the checker the
# same file twice.
it_should_report_a_violation_once_when_two_spellings_name_the_same_file() {
  local repo alias count
  repo=$(new_repo unit15spellings)
  alias="$tmp_root/unit15alias"
  ln -s "$repo" "$alias"
  write_violating_shell_file "$repo/deploy.sh"
  git -C "$repo" add deploy.sh

  run_gate "$repo" "git add $alias/deploy.sh && git commit -m \"x\""

  count=$(printf '%s\n' "$GATE_STDERR" | grep -c '^== ')
  assert_eq "should report a violating file once when two spellings name it" \
    1 "$count"
}

# A directory pathspec commits every modified file under
# it, so the gate must expand the directory rather than
# drop it for not being a file.
it_should_block_a_violation_in_a_file_under_a_directory_commit_pathspec() {
  local repo
  repo=$(new_repo unit16dirviolation)
  mkdir -p "$repo/services/billing"
  write_clean_shell_file "$repo/services/billing/deploy.sh"
  commit_tracked_file "$repo" services/billing/deploy.sh
  write_violating_shell_file "$repo/services/billing/deploy.sh"

  run_gate "$repo" 'git commit services/ -m "x"'

  assert_eq "should block a commit whose directory pathspec holds a modified violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the violating file found under the directory pathspec" \
    "deploy.sh" "$GATE_STDERR"
}

it_should_allow_a_directory_commit_pathspec_with_no_modified_file_under_it() {
  local repo
  repo=$(new_repo unit16dirclean)
  mkdir -p "$repo/services"
  write_clean_shell_file "$repo/services/deploy.sh"
  commit_tracked_file "$repo" services/deploy.sh

  run_gate "$repo" 'git commit services/ -m "x"'

  assert_eq "should allow a directory pathspec with nothing modified under it" \
    0 "$GATE_EXIT"
  assert_eq "should stay silent for a directory pathspec with nothing modified under it" \
    "" "$GATE_STDERR"
}

# A git that refuses the working-tree listing must not read
# as "nothing modified": the gate warns, like every other
# unreadable git call, and lets the commit through.
it_should_warn_and_allow_when_a_directory_commit_pathspec_cannot_be_listed() {
  local repo shim_dir real_git
  repo=$(new_repo unit16dirlistfails)
  mkdir -p "$repo/services"
  write_clean_shell_file "$repo/services/deploy.sh"
  commit_tracked_file "$repo" services/deploy.sh
  write_violating_shell_file "$repo/services/deploy.sh"
  shim_dir="$tmp_root/unit16shim"
  real_git=$(command -v git)
  mkdir -p "$shim_dir"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'case " $* " in *" HEAD "*) exit 128;; esac\n'
    printf 'exec %s "$@"\n' "$real_git"
  } > "$shim_dir/git"
  chmod +x "$shim_dir/git"

  GATE_STDERR=$(cd "$repo" \
    && PATH="$shim_dir:$PATH" bash "$SCRIPT" 'git commit services/ -m "x"' 2>&1 >/dev/null)
  GATE_EXIT=$?

  assert_eq "should allow the commit when the directory listing fails" \
    0 "$GATE_EXIT"
  assert_contains "should warn that the directory pathspec could not be listed" \
    "could not list" "$GATE_STDERR"
}

it_should_allow_a_commit_pathspec_naming_neither_a_file_nor_a_directory() {
  local repo
  repo=$(new_repo unit16missingpath)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git commit no-such-path -m "x"'

  assert_eq "should allow a commit pathspec that names nothing on disk" \
    0 "$GATE_EXIT"
}

# `git add <dir>` stages untracked files under it too, and
# `git diff HEAD` lists tracked paths only, so a brand-new
# file in the directory would otherwise ship unchecked.
it_should_block_a_violation_in_an_untracked_file_under_a_git_add_directory() {
  local repo
  repo=$(new_repo unit17adduntracked)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/kept.sh"
  commit_tracked_file "$repo" sub/kept.sh
  write_violating_shell_file "$repo/sub/new-script.sh"

  run_gate "$repo" 'git add sub/ && git commit -m "x"'

  assert_eq "should block a git add of a directory holding an untracked violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the untracked file under the added directory" \
    "new-script.sh" "$GATE_STDERR"
}

# `git commit <dir>` commits tracked paths only, so blocking
# on an untracked file would refuse a commit that never
# contains it.
it_should_allow_a_directory_commit_pathspec_holding_only_an_untracked_violation() {
  local repo
  repo=$(new_repo unit17commituntracked)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/kept.sh"
  commit_tracked_file "$repo" sub/kept.sh
  write_violating_shell_file "$repo/sub/new-script.sh"

  run_gate "$repo" 'git commit sub/ -m "x"'

  assert_eq "should allow a directory commit when the only violation is untracked" \
    0 "$GATE_EXIT"
}

it_should_block_a_violation_in_a_tracked_file_under_a_git_add_directory() {
  local repo
  repo=$(new_repo unit17addtracked)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/deploy.sh"
  commit_tracked_file "$repo" sub/deploy.sh
  write_violating_shell_file "$repo/sub/deploy.sh"

  run_gate "$repo" 'git add sub/ && git commit -m "x"'

  assert_eq "should block a git add of a directory holding a modified violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the modified file under the added directory" \
    "deploy.sh" "$GATE_STDERR"
}

# The real checker already treats a gitignored file as having
# no changed lines, so its exit code cannot tell whether the
# gate handed that file over. A stub checker that records the
# files it was given can.
it_should_not_check_a_gitignored_untracked_file_under_a_git_add_directory() {
  local repo stub received
  repo=$(new_repo unit17addignored)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/kept.sh"
  commit_tracked_file "$repo" sub/kept.sh
  printf 'ignored-script.sh\n' > "$repo/.gitignore"
  write_violating_shell_file "$repo/sub/ignored-script.sh"
  write_violating_shell_file "$repo/sub/new-script.sh"
  stub="$tmp_root/unit17recorder.js"
  received="$tmp_root/unit17received.txt"
  printf 'require("fs").writeFileSync(process.env.RECEIVED_FILES, process.argv.slice(2).join("\\n"));\n' > "$stub"

  GATE_STDERR=$(cd "$repo" && RECEIVED_FILES="$received" CHECK_COMMENT_FORMAT_JS="$stub" \
    bash "$SCRIPT" 'git add sub/ && git commit -m "x"' 2>&1 >/dev/null)

  assert_contains "should hand the checker the untracked file that is not ignored" \
    "sub/new-script.sh" "$(cat "$received")"
  assert_not_contains "should not hand the checker the gitignored untracked file" \
    "ignored-script.sh" "$(cat "$received")"
}

it_should_warn_and_allow_when_untracked_files_under_a_git_add_directory_cannot_be_listed() {
  local repo shim_dir real_git
  repo=$(new_repo unit17lsfilesfails)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/kept.sh"
  commit_tracked_file "$repo" sub/kept.sh
  write_violating_shell_file "$repo/sub/new-script.sh"
  shim_dir="$tmp_root/unit17shim"
  real_git=$(command -v git)
  mkdir -p "$shim_dir"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'case " $* " in *" ls-files "*) exit 128;; esac\n'
    printf 'exec %s "$@"\n' "$real_git"
  } > "$shim_dir/git"
  chmod +x "$shim_dir/git"

  GATE_STDERR=$(cd "$repo" \
    && PATH="$shim_dir:$PATH" bash "$SCRIPT" 'git add sub/ && git commit -m "x"' 2>&1 >/dev/null)
  GATE_EXIT=$?

  assert_eq "should allow the commit when the untracked listing fails" \
    0 "$GATE_EXIT"
  assert_contains "should warn that the untracked files could not be listed" \
    "could not list" "$GATE_STDERR"
}

# `--pathspec-from-file` names its pathspecs in a file, so a
# gate that ignores the option sees a commit with no
# pathspecs and lets a violating file through.
it_should_block_a_violation_listed_in_a_commit_pathspec_from_file() {
  local repo
  repo=$(new_repo unit18commitfile)
  write_violating_shell_file "$repo/deploy.sh"
  printf 'seed.txt\ndeploy.sh\n' > "$repo/paths.txt"

  run_gate "$repo" 'git commit --pathspec-from-file=paths.txt -m "x"'

  assert_eq "should block a commit whose pathspec file lists a violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the violating file the pathspec file lists" \
    "deploy.sh" "$GATE_STDERR"
}

# A NUL-separated list is read by a different branch than a
# newline-separated one.
it_should_block_a_violation_listed_in_a_nul_separated_commit_pathspec_file() {
  local repo
  repo=$(new_repo unit18commitnul)
  write_violating_shell_file "$repo/deploy.sh"
  printf 'seed.txt\0deploy.sh\0' > "$repo/paths.bin"

  run_gate "$repo" 'git commit --pathspec-from-file=paths.bin --pathspec-file-nul -m "x"'

  assert_eq "should block a commit whose NUL-separated pathspec file lists a violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the violating file the NUL-separated pathspec file lists" \
    "deploy.sh" "$GATE_STDERR"
}

# The option takes its value as the next token too, and that
# token must be neither skipped past the list nor read as a
# pathspec itself.
it_should_block_a_violation_listed_in_a_pathspec_file_named_by_a_separate_argument() {
  local repo
  repo=$(new_repo unit18separatearg)
  write_violating_shell_file "$repo/deploy.sh"
  printf 'deploy.sh\n' > "$repo/paths.txt"

  run_gate "$repo" 'git commit --pathspec-from-file paths.txt -m "x"'

  assert_eq "should block when the pathspec file is a separate argument" \
    1 "$GATE_EXIT"
  assert_contains "should name the violating file listed in the separately named pathspec file" \
    "deploy.sh" "$GATE_STDERR"
}

it_should_block_a_violation_listed_in_a_git_add_pathspec_from_file() {
  local repo
  repo=$(new_repo unit18addfile)
  write_violating_shell_file "$repo/deploy.sh"
  printf 'deploy.sh\n' > "$repo/paths.txt"

  run_gate "$repo" 'git add --pathspec-from-file=paths.txt && git commit -m "x"'

  assert_eq "should block a git add whose pathspec file lists a violating file" \
    1 "$GATE_EXIT"
  assert_contains "should name the violating file a git add pathspec file lists" \
    "deploy.sh" "$GATE_STDERR"
}

# Only the add arm stages untracked files, so a directory
# listed in an add pathspec file widens to them while the
# same line in a commit pathspec file does not.
it_should_check_an_untracked_file_under_a_directory_listed_in_a_git_add_pathspec_file() {
  local repo
  repo=$(new_repo unit18adddir)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/kept.sh"
  commit_tracked_file "$repo" sub/kept.sh
  write_violating_shell_file "$repo/sub/new-script.sh"
  printf 'sub\n' > "$repo/paths.txt"

  run_gate "$repo" 'git add --pathspec-from-file=paths.txt && git commit -m "x"'

  assert_eq "should block a git add pathspec file listing a directory holding an untracked violation" \
    1 "$GATE_EXIT"
}

it_should_allow_a_directory_listed_in_a_commit_pathspec_file_holding_only_an_untracked_violation() {
  local repo
  repo=$(new_repo unit18commitdir)
  mkdir -p "$repo/sub"
  write_clean_shell_file "$repo/sub/kept.sh"
  commit_tracked_file "$repo" sub/kept.sh
  write_violating_shell_file "$repo/sub/new-script.sh"
  printf 'sub\n' > "$repo/paths.txt"

  run_gate "$repo" 'git commit --pathspec-from-file=paths.txt -m "x"'

  assert_eq "should allow a commit pathspec file listing a directory whose only violation is untracked" \
    0 "$GATE_EXIT"
}

# git reads the file's entries from the repo root, while the
# file's own path (like any argv pathspec) is relative to the
# directory the command runs in.
it_should_resolve_pathspec_file_entries_from_the_repo_root_when_run_from_a_subdirectory() {
  local repo
  repo=$(new_repo unit18subdir)
  mkdir -p "$repo/sub"
  write_violating_shell_file "$repo/sub/deploy.sh"
  printf 'sub/deploy.sh\n' > "$repo/sub/paths.txt"

  run_gate "$repo" 'cd sub && git commit --pathspec-from-file=paths.txt -m "x"'

  assert_eq "should block a violation listed from the repo root while running in a subdirectory" \
    1 "$GATE_EXIT"
  assert_contains "should name the file at its repo-root path" \
    "sub/deploy.sh" "$GATE_STDERR"
}

it_should_warn_and_allow_when_a_pathspec_file_does_not_exist() {
  local repo
  repo=$(new_repo unit18missingfile)
  write_violating_shell_file "$repo/deploy.sh"

  run_gate "$repo" 'git commit --pathspec-from-file=missing.txt -m "x"'

  assert_eq "should allow the commit when the pathspec file is missing" \
    0 "$GATE_EXIT"
  assert_contains "should warn that the pathspec file could not be read" \
    "could not read the pathspec file" "$GATE_STDERR"
  assert_contains "should name the pathspec file it could not read" \
    "missing.txt" "$GATE_STDERR"
}

it_should_warn_and_allow_when_a_pathspec_file_is_unreadable() {
  local repo
  repo=$(new_repo unit18unreadablefile)
  write_violating_shell_file "$repo/deploy.sh"
  printf 'deploy.sh\n' > "$repo/paths.txt"
  chmod 000 "$repo/paths.txt"

  run_gate "$repo" 'git commit --pathspec-from-file=paths.txt -m "x"'
  chmod 644 "$repo/paths.txt"

  assert_eq "should allow the commit when the pathspec file is unreadable" \
    0 "$GATE_EXIT"
  assert_contains "should warn that the unreadable pathspec file could not be read" \
    "could not read the pathspec file" "$GATE_STDERR"
}

# The hook never sees the git process's stdin, so a list read
# from it is the same unknown set a glob is.
it_should_fall_back_to_the_index_when_the_pathspec_list_comes_from_stdin() {
  local repo
  repo=$(new_repo unit18stdin)

  run_gate "$repo" 'git commit --pathspec-from-file=- -m "x"'

  assert_contains "should say the file set could not be read when the list comes from stdin" \
    "command string" "$GATE_STDERR"
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
it_should_fall_back_to_the_index_when_a_committing_git_dash_c_target_is_missing
it_should_still_judge_the_index_when_a_committing_git_dash_c_target_is_missing
it_should_block_a_staged_violation_when_diff_relative_is_set_in_a_subdirectory
it_should_block_a_commit_dash_a_violation_when_diff_relative_is_set_in_a_subdirectory
it_should_block_a_violation_in_a_file_named_as_a_commit_pathspec
it_should_block_a_violation_in_a_file_named_after_a_commit_double_dash
it_should_not_read_a_commit_option_value_as_a_pathspec
it_should_fall_back_to_the_index_when_a_commit_pathspec_is_a_variable
it_should_report_a_violation_once_when_two_spellings_name_the_same_file
it_should_block_a_violation_in_a_file_under_a_directory_commit_pathspec
it_should_allow_a_directory_commit_pathspec_with_no_modified_file_under_it
it_should_warn_and_allow_when_a_directory_commit_pathspec_cannot_be_listed
it_should_allow_a_commit_pathspec_naming_neither_a_file_nor_a_directory
it_should_block_a_violation_in_an_untracked_file_under_a_git_add_directory
it_should_allow_a_directory_commit_pathspec_holding_only_an_untracked_violation
it_should_block_a_violation_in_a_tracked_file_under_a_git_add_directory
it_should_not_check_a_gitignored_untracked_file_under_a_git_add_directory
it_should_warn_and_allow_when_untracked_files_under_a_git_add_directory_cannot_be_listed
it_should_block_a_violation_listed_in_a_commit_pathspec_from_file
it_should_block_a_violation_listed_in_a_nul_separated_commit_pathspec_file
it_should_block_a_violation_listed_in_a_pathspec_file_named_by_a_separate_argument
it_should_block_a_violation_listed_in_a_git_add_pathspec_from_file
it_should_check_an_untracked_file_under_a_directory_listed_in_a_git_add_pathspec_file
it_should_allow_a_directory_listed_in_a_commit_pathspec_file_holding_only_an_untracked_violation
it_should_resolve_pathspec_file_entries_from_the_repo_root_when_run_from_a_subdirectory
it_should_warn_and_allow_when_a_pathspec_file_does_not_exist
it_should_warn_and_allow_when_a_pathspec_file_is_unreadable
it_should_fall_back_to_the_index_when_the_pathspec_list_comes_from_stdin

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
