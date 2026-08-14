#!/usr/bin/env bash
# test-prep-refactor-context.sh - plain-bash test suite for
# prep-refactor-context.sh, the /refactor context-prep script.
#
# Builds a scratch git repo per test so results never depend
# on this repo's own history, then runs the real script end
# to end against it.
#
# No bats dependency, matching the sibling
# test-prep-local-context.sh suite.
#
# Exits 0 when every assertion passes, non-zero otherwise.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/prep-refactor-context.sh"

pass_count=0
fail_count=0

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

# make_scratch_repo - builds a throwaway git repo at a fresh
# mktemp dir with a single "master" branch and one commit
# adding tracked.txt, "master" left checked out as HEAD.
#
# Base resolution falls back to resolve-base-ref.sh's local
# "master" lookup, so this repo needs no origin remote.
# Echoes the repo path.
make_scratch_repo() {
  local repo
  repo="$(mktemp -d)"
  git -C "$repo" init -q -b master
  git -C "$repo" config user.email test@example.com
  git -C "$repo" config user.name "Test User"

  echo "tracked line 1" > "$repo/tracked.txt"
  git -C "$repo" add tracked.txt
  git -C "$repo" commit -q -m "initial commit

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

  echo "$repo"
}

# make_diverged_scratch_repo - builds a repo shaped for the
# merge-base test.
#
# Shape:
#   C0 (common ancestor, adds shared.txt)
#   master:  C0 -> C1 (adds base-only.txt), after the split
#   feature: C0 -> C2 (adds feature-only.txt), checked out HEAD
#
# This shape is what makes merge-base vs plain-base
# observable.
#
# C1 sits on master but not on the path from the merge-base
# to feature, so diffing from the merge-base (correct) omits
# it while diffing from master's tip directly (the bug this
# script must avoid) would render it as a reversed deletion.
#
# Echoes the repo path.
make_diverged_scratch_repo() {
  local repo
  repo="$(mktemp -d)"
  git -C "$repo" init -q -b master
  git -C "$repo" config user.email test@example.com
  git -C "$repo" config user.name "Test User"

  echo "shared" > "$repo/shared.txt"
  git -C "$repo" add shared.txt
  git -C "$repo" commit -q -m "common ancestor commit

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

  git -C "$repo" checkout -q -b feature
  echo "feature-only" > "$repo/feature-only.txt"
  git -C "$repo" add feature-only.txt
  git -C "$repo" commit -q -m "feature-only commit

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

  git -C "$repo" checkout -q master
  echo "base-only" > "$repo/base-only.txt"
  git -C "$repo" add base-only.txt
  git -C "$repo" commit -q -m "base-only commit

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

  git -C "$repo" checkout -q feature

  echo "$repo"
}

it_should_write_all_four_output_files_creating_a_not_yet_existing_work_dir_on_the_happy_path() {
  local repo work_dir output missing="" f result
  repo="$(make_scratch_repo)"
  echo "tracked line 1 modified" > "$repo/tracked.txt"

  # Nested, not-yet-existing dir: also exercises the script's
  # own defensive `mkdir -p`, since nothing pre-creates this.
  work_dir="$(mktemp -d)/nested/output"

  output=$(cd "$repo" && bash "$SCRIPT" "$work_dir" 2>&1)

  for f in diff changed-files.txt untracked-files.txt commit-messages.txt; do
    [ -e "$work_dir/$f" ] || missing="$missing $f"
  done
  [ -s "$work_dir/diff" ] || missing="$missing diff-is-empty"

  result="all four files present and diff non-empty"
  [ -z "$missing" ] || result="missing/empty:$missing (script output: $output)"

  rm -rf "$repo" "$(dirname "$(dirname "$work_dir")")"
  assert_eq "should write all four output files, creating a not-yet-existing work_dir, with a non-empty diff on the happy path" \
    "all four files present and diff non-empty" "$result"
}

it_should_list_an_untracked_file_in_both_untracked_and_changed_but_contribute_no_diff_lines() {
  local repo work_dir untracked_content changed_content diff_content result
  repo="$(make_scratch_repo)"
  echo "brand new" > "$repo/new-untracked.txt"
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" "$work_dir" >/dev/null 2>&1)
  untracked_content="$(cat "$work_dir/untracked-files.txt" 2>/dev/null)"
  changed_content="$(cat "$work_dir/changed-files.txt" 2>/dev/null)"
  diff_content="$(cat "$work_dir/diff" 2>/dev/null)"

  result="wrong placement"
  if [[ "$untracked_content" == *"new-untracked.txt"* \
     && "$changed_content" == *"new-untracked.txt"* \
     && "$diff_content" != *"new-untracked.txt"* ]]; then
    result="listed in untracked-files.txt and changed-files.txt, absent from diff"
  fi

  rm -rf "$repo" "$work_dir"
  assert_eq "should list an untracked file in both untracked-files.txt and changed-files.txt while contributing no lines to diff" \
    "listed in untracked-files.txt and changed-files.txt, absent from diff" "$result"
}

it_should_capture_a_staged_but_uncommitted_change_in_the_diff() {
  local repo work_dir diff_content result
  repo="$(make_scratch_repo)"
  echo "staged modification" >> "$repo/tracked.txt"
  git -C "$repo" add tracked.txt
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" "$work_dir" >/dev/null 2>&1)
  diff_content="$(cat "$work_dir/diff" 2>/dev/null)"

  rm -rf "$repo" "$work_dir"
  result="diff missing the staged change"
  [[ "$diff_content" == *"staged modification"* ]] && result="diff captured the staged-but-uncommitted change"
  assert_eq "should capture a staged-but-uncommitted change in diff (proves working-tree coverage)" \
    "diff captured the staged-but-uncommitted change" "$result"
}

it_should_scope_all_outputs_to_a_pathspec_argument_excluding_files_outside_it() {
  local repo work_dir changed_content result
  repo="$(make_scratch_repo)"
  mkdir -p "$repo/in-scope" "$repo/out-of-scope"
  echo "in scope" > "$repo/in-scope/file.txt"
  echo "out of scope" > "$repo/out-of-scope/file.txt"
  git -C "$repo" add in-scope/file.txt out-of-scope/file.txt
  git -C "$repo" commit -q -m "add scoped files

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
  echo "in scope modified" > "$repo/in-scope/file.txt"
  echo "out of scope modified" > "$repo/out-of-scope/file.txt"
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" "$work_dir" in-scope >/dev/null 2>&1)
  changed_content="$(cat "$work_dir/changed-files.txt" 2>/dev/null)"

  result="wrong scoping"
  if [[ "$changed_content" == *"in-scope/file.txt"* && "$changed_content" != *"out-of-scope/file.txt"* ]]; then
    result="in-scope file present, out-of-scope file excluded"
  fi

  rm -rf "$repo" "$work_dir"
  assert_eq "should scope changed-files.txt to a pathspec argument, excluding a changed file outside it" \
    "in-scope file present, out-of-scope file excluded" "$result"
}

it_should_fail_naming_the_empty_scope_when_nothing_changed_and_nothing_is_untracked() {
  local repo work_dir output exit_code result
  repo="$(make_scratch_repo)"
  work_dir="$(mktemp -d)"

  output=$(cd "$repo" && bash "$SCRIPT" "$work_dir" 2>&1)
  exit_code=$?

  result="exit $exit_code: $output"
  if [ "$exit_code" -ne 0 ]; then
    case "$output" in
      *"nothing to refactor"*) result="failed non-zero, naming the empty scope" ;;
      *) result="failed non-zero but without naming the empty scope: $output" ;;
    esac
  fi

  rm -rf "$repo" "$work_dir"
  assert_eq "should exit non-zero and name the empty scope when nothing changed and nothing is untracked" \
    "failed non-zero, naming the empty scope" "$result"
}

it_should_fail_naming_the_problem_when_run_outside_a_git_repository() {
  local non_repo_dir work_dir output exit_code result
  non_repo_dir="$(mktemp -d)"
  work_dir="$(mktemp -d)"

  output=$(cd "$non_repo_dir" && bash "$SCRIPT" "$work_dir" 2>&1)
  exit_code=$?

  result="exit $exit_code: $output"
  if [ "$exit_code" -ne 0 ]; then
    case "$output" in
      *"git repository"*) result="failed non-zero, naming the missing git repository" ;;
      *) result="failed non-zero but without naming the problem: $output" ;;
    esac
  fi

  rm -rf "$non_repo_dir" "$work_dir"
  assert_eq "should exit non-zero and name the problem when run outside a git repository" \
    "failed non-zero, naming the missing git repository" "$result"
}

it_should_fail_naming_work_dir_when_called_with_zero_arguments() {
  local repo output exit_code result
  repo="$(make_scratch_repo)"

  output=$(cd "$repo" && bash "$SCRIPT" 2>&1)
  exit_code=$?

  result="exit $exit_code: $output"
  if [ "$exit_code" -ne 0 ]; then
    case "$output" in
      *sage*work_dir*) result="failed non-zero, naming work_dir in a usage message" ;;
      *) result="failed non-zero but without a usage message naming work_dir: $output" ;;
    esac
  fi

  rm -rf "$repo"
  assert_eq "should exit non-zero and print a usage message naming work_dir when called with zero arguments" \
    "failed non-zero, naming work_dir in a usage message" "$result"
}

it_should_print_the_usage_header_and_exit_zero_on_help_flag() {
  local output exit_code result
  output=$(bash "$SCRIPT" --help 2>&1)
  exit_code=$?

  result="exit $exit_code: $output"
  if [ "$exit_code" -eq 0 ] && [[ "$output" == *"prep-refactor-context.sh"* ]] && [[ "$output" == *"Usage"* ]]; then
    result="printed usage header, exit 0"
  fi

  assert_eq "should print the usage header and exit 0 on --help" \
    "printed usage header, exit 0" "$result"
}

it_should_diff_from_the_merge_base_excluding_the_base_branchs_own_newer_commits() {
  local repo work_dir diff_content result
  repo="$(make_diverged_scratch_repo)"
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" "$work_dir" >/dev/null 2>&1)
  diff_content="$(cat "$work_dir/diff" 2>/dev/null)"

  result="wrong range"
  if [[ "$diff_content" == *"feature-only.txt"* && "$diff_content" != *"base-only.txt"* ]]; then
    result="diff includes feature's own addition and excludes base's own newer commit"
  fi

  rm -rf "$repo" "$work_dir"
  assert_eq "should diff from the merge-base (excluding master's own newer commit) rather than from master's tip, which would render that commit as a reversed change" \
    "diff includes feature's own addition and excludes base's own newer commit" "$result"
}

it_should_write_all_four_output_files_creating_a_not_yet_existing_work_dir_on_the_happy_path
it_should_list_an_untracked_file_in_both_untracked_and_changed_but_contribute_no_diff_lines
it_should_capture_a_staged_but_uncommitted_change_in_the_diff
it_should_scope_all_outputs_to_a_pathspec_argument_excluding_files_outside_it
it_should_fail_naming_the_empty_scope_when_nothing_changed_and_nothing_is_untracked
it_should_fail_naming_the_problem_when_run_outside_a_git_repository
it_should_fail_naming_work_dir_when_called_with_zero_arguments
it_should_print_the_usage_header_and_exit_zero_on_help_flag
it_should_diff_from_the_merge_base_excluding_the_base_branchs_own_newer_commits

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
