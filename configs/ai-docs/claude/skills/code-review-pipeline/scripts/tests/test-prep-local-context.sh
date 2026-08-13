#!/usr/bin/env bash
# test-prep-local-context.sh - plain-bash test suite for
# prep-local-context.sh, the Wave 1 local-mode context-prep
# script.
#
# Builds a scratch git repo per test so results never depend
# on this repo's own history, then runs the real script
# end to end against it.
#
# No bats dependency, matching the sibling
# test-subagent-prompt-script-refs.sh suite.
#
# Exits 0 when every assertion passes, non-zero otherwise.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/prep-local-context.sh"

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
# mktemp dir with a "base" branch and a "feature" branch that
# diverge from a shared common-ancestor commit, "feature" left
# checked out as HEAD. Echoes the repo path.
#
# Shape:
#   C0 (common ancestor, adds shared.txt)
#   base:    C0 -> C1 (adds base-only.txt)
#   feature: C0 -> C2 (adds feature-only.txt), checked out HEAD
#
# This shape is what makes the two-dot/three-dot range
# distinction observable: C1 sits on base but not on the path
# from the merge-base to feature, so a three-dot diff (which
# diffs against the merge-base) omits it while a two-dot diff
# (base tip vs feature tip) would include it.
make_scratch_repo() {
  local repo
  repo="$(mktemp -d)"
  git -C "$repo" init -q -b feature
  git -C "$repo" config user.email test@example.com
  git -C "$repo" config user.name "Test User"

  echo "shared" > "$repo/shared.txt"
  git -C "$repo" add shared.txt
  git -C "$repo" commit -q -m "common ancestor commit"

  git -C "$repo" branch base
  git -C "$repo" checkout -q base
  echo "base-only" > "$repo/base-only.txt"
  git -C "$repo" add base-only.txt
  git -C "$repo" commit -q -m "base-only commit"

  git -C "$repo" checkout -q feature
  echo "feature-only" > "$repo/feature-only.txt"
  git -C "$repo" add feature-only.txt
  git -C "$repo" commit -q -m "feature-only commit"

  echo "$repo"
}

# make_scratch_repo_with_n_added_lines <n> - a minimal repo
# where "feature" adds exactly <n> lines to a new file over
# "base", for pinning the tiny-pr.txt boundary.
make_scratch_repo_with_n_added_lines() {
  local n="$1" repo i
  repo="$(mktemp -d)"
  git -C "$repo" init -q -b feature
  git -C "$repo" config user.email test@example.com
  git -C "$repo" config user.name "Test User"

  echo "shared" > "$repo/shared.txt"
  git -C "$repo" add shared.txt
  git -C "$repo" commit -q -m "common ancestor commit"

  git -C "$repo" branch base

  : > "$repo/added.txt"
  for ((i = 1; i <= n; i++)); do
    echo "line $i" >> "$repo/added.txt"
  done
  git -C "$repo" add added.txt
  git -C "$repo" commit -q -m "add $n lines"

  echo "$repo"
}

it_should_write_all_seven_output_files_with_a_non_empty_diff_on_the_happy_path() {
  local repo work_dir output missing="" f result
  repo="$(make_scratch_repo)"
  # Nested, not-yet-existing dir: also exercises the script's
  # own defensive `mkdir -p`, since nothing pre-creates this.
  work_dir="$(mktemp -d)/nested/output"

  output=$(cd "$repo" && bash "$SCRIPT" base "$work_dir" 2>&1)

  for f in diff changed-files.txt commit-messages.txt commentable-lines.txt \
           skipped-binary.txt skipped-deleted.txt tiny-pr.txt; do
    [ -e "$work_dir/$f" ] || missing="$missing $f"
  done
  [ -s "$work_dir/diff" ] || missing="$missing diff-is-empty"

  result="all seven files present and diff non-empty"
  [ -z "$missing" ] || result="missing/empty:$missing (script output: $output)"

  rm -rf "$repo" "$(dirname "$(dirname "$work_dir")")"
  assert_eq "should write all seven output files, creating a not-yet-existing work_dir, with a non-empty diff on the happy path" \
    "all seven files present and diff non-empty" "$result"
}

it_should_write_tiny_pr_true_when_added_lines_is_ninety_nine() {
  local repo work_dir content
  repo="$(make_scratch_repo_with_n_added_lines 99)"
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" base "$work_dir" >/dev/null 2>&1)
  content="$(cat "$work_dir/tiny-pr.txt" 2>/dev/null)"

  rm -rf "$repo" "$work_dir"
  assert_eq "should write tiny-pr.txt=true when added_lines is 99 (just under the 100 cap)" \
    "true" "$content"
}

it_should_write_tiny_pr_false_when_added_lines_is_one_hundred() {
  local repo work_dir content
  repo="$(make_scratch_repo_with_n_added_lines 100)"
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" base "$work_dir" >/dev/null 2>&1)
  content="$(cat "$work_dir/tiny-pr.txt" 2>/dev/null)"

  rm -rf "$repo" "$work_dir"
  assert_eq "should write tiny-pr.txt=false when added_lines reaches the 100 cap" \
    "false" "$content"
}

it_should_fail_and_name_the_ref_when_base_ref_is_neither_an_origin_branch_nor_a_local_commit_ish() {
  local repo work_dir output exit_code result
  repo="$(make_scratch_repo)"
  work_dir="$(mktemp -d)"

  output=$(cd "$repo" && bash "$SCRIPT" totally-bogus-ref-xyz "$work_dir" 2>&1)
  exit_code=$?

  result="wrong exit code ($exit_code): $output"
  if [ "$exit_code" -ne 0 ]; then
    case "$output" in
      *"base ref 'totally-bogus-ref-xyz' is neither a branch on origin nor a local commit-ish"*)
        result="failed non-zero, naming the unresolvable ref" ;;
      *) result="failed non-zero but without the expected message: $output" ;;
    esac
  fi

  rm -rf "$repo" "$work_dir"
  assert_eq "should exit non-zero and name the ref when base_ref is neither a branch on origin nor a local commit-ish" \
    "failed non-zero, naming the unresolvable ref" "$result"
}

it_should_fail_naming_the_problem_when_called_with_the_wrong_argument_count() {
  local repo output exit_code result
  repo="$(make_scratch_repo)"

  output=$(cd "$repo" && bash "$SCRIPT" only-one-arg 2>&1)
  exit_code=$?

  result="exit $exit_code: $output"
  if [ "$exit_code" -ne 0 ]; then
    case "$output" in
      *sage*base_ref*work_dir*) result="failed non-zero, naming the wrong argument count" ;;
      *) result="failed non-zero but without a usage message naming the problem: $output" ;;
    esac
  fi

  rm -rf "$repo"
  assert_eq "should exit non-zero and print a usage message naming base_ref/work_dir when called with the wrong argument count" \
    "failed non-zero, naming the wrong argument count" "$result"
}

it_should_fail_naming_the_problem_when_run_outside_a_git_repository() {
  local non_repo_dir work_dir output exit_code result
  non_repo_dir="$(mktemp -d)"
  work_dir="$(mktemp -d)"

  output=$(cd "$non_repo_dir" && bash "$SCRIPT" base "$work_dir" 2>&1)
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

it_should_use_three_dot_range_for_the_diff_and_two_dot_range_for_the_commit_log() {
  local repo work_dir diff_content log_content result
  repo="$(make_scratch_repo)"
  work_dir="$(mktemp -d)"

  (cd "$repo" && bash "$SCRIPT" base "$work_dir" >/dev/null 2>&1)
  diff_content="$(cat "$work_dir/diff" 2>/dev/null)"
  log_content="$(cat "$work_dir/commit-messages.txt" 2>/dev/null)"

  result="wrong ranges"
  if [[ "$diff_content" == *"feature-only.txt"* \
     && "$diff_content" != *"base-only.txt"* \
     && "$log_content" == *"feature-only commit"* \
     && "$log_content" != *"base-only commit"* ]]; then
    result="diff excludes base's own commit (three-dot from merge-base) and the log excludes it too (two-dot from base tip)"
  fi

  rm -rf "$repo" "$work_dir"
  assert_eq "should diff base_rev...HEAD (excluding base's own commit, since it diffs from the merge-base) while logging base_rev..HEAD (also excluding it, since it lists only commits reachable from HEAD)" \
    "diff excludes base's own commit (three-dot from merge-base) and the log excludes it too (two-dot from base tip)" \
    "$result"
}

it_should_print_the_usage_header_and_exit_zero_on_help_flag() {
  local output exit_code result
  output=$(bash "$SCRIPT" --help 2>&1)
  exit_code=$?

  result="exit $exit_code: $output"
  if [ "$exit_code" -eq 0 ] && [[ "$output" == *"prep-local-context.sh"* ]] && [[ "$output" == *"Usage"* ]]; then
    result="printed usage header, exit 0"
  fi

  assert_eq "should print the usage header and exit 0 on --help" \
    "printed usage header, exit 0" "$result"
}

it_should_write_all_seven_output_files_with_a_non_empty_diff_on_the_happy_path
it_should_write_tiny_pr_true_when_added_lines_is_ninety_nine
it_should_write_tiny_pr_false_when_added_lines_is_one_hundred
it_should_fail_and_name_the_ref_when_base_ref_is_neither_an_origin_branch_nor_a_local_commit_ish
it_should_fail_naming_the_problem_when_called_with_the_wrong_argument_count
it_should_fail_naming_the_problem_when_run_outside_a_git_repository
it_should_use_three_dot_range_for_the_diff_and_two_dot_range_for_the_commit_log
it_should_print_the_usage_header_and_exit_zero_on_help_flag

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
