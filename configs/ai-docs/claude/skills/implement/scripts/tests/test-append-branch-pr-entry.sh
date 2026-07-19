#!/usr/bin/env bash
# test-append-branch-pr-entry.sh - plain-bash test file for append-branch-pr-entry.sh.
#
# Usage:
#   bash test-append-branch-pr-entry.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/append-branch-pr-entry.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual, prints ok/not-ok.
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

# assert_true - inline assert helper: prints ok/not-ok based on a boolean condition already evaluated by the caller.
assert_true() {
  local description="$1" condition="$2"
  if [ "$condition" = "true" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n' "$description"
  fi
}

# run_script - invokes append-branch-pr-entry.sh with the given args, capturing
# stdout/stderr/exit code into VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$@" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

it_should_create_branches_file_with_one_entry_when_none_exists_yet() {
  local branches_file="$work_dir/happy-create/branches_test-slug.md"
  mkdir -p "$(dirname "$branches_file")"
  run_script "$branches_file" "test-slug" "PR-1" "feat-foo/pr1"
  assert_eq "should create branches_<slug>.md with one entry when none exists yet (exit code)" "0" "$VERDICT_EXIT"

  local content
  content=$(cat "$branches_file")
  local has_header="false" has_entry="false"
  [[ "$content" == *"# Branches: test-slug"* ]] && has_header="true"
  [[ "$content" == *'**PR-1** — branch: `feat-foo/pr1`'* ]] && has_entry="true"
  assert_true "should create branches_<slug>.md with one entry when none exists yet (header present)" "$has_header"
  assert_true "should create branches_<slug>.md with one entry when none exists yet (entry present)" "$has_entry"
}

it_should_append_a_new_entry_when_branches_file_already_has_prior_prs() {
  local branches_file="$work_dir/happy-append/branches_test-slug.md"
  mkdir -p "$(dirname "$branches_file")"
  run_script "$branches_file" "test-slug" "PR-1" "feat-foo/pr1"

  run_script "$branches_file" "test-slug" "PR-2" "feat-foo/pr2"
  assert_eq "should append a new entry when branches_<slug>.md already has prior PRs (exit code)" "0" "$VERDICT_EXIT"

  local content
  content=$(cat "$branches_file")
  local has_pr1="false" has_pr2="false" pr1_before_pr2="false"
  [[ "$content" == *'**PR-1** — branch: `feat-foo/pr1`'* ]] && has_pr1="true"
  [[ "$content" == *'**PR-2** — branch: `feat-foo/pr2`'* ]] && has_pr2="true"
  local pr1_line pr2_line
  pr1_line=$(grep -n '\*\*PR-1\*\*' "$branches_file" | cut -d: -f1)
  pr2_line=$(grep -n '\*\*PR-2\*\*' "$branches_file" | cut -d: -f1)
  if [ -n "$pr1_line" ] && [ -n "$pr2_line" ] && [ "$pr1_line" -lt "$pr2_line" ]; then
    pr1_before_pr2="true"
  fi
  assert_true "should append a new entry when branches_<slug>.md already has prior PRs (prior PR-1 preserved)" "$has_pr1"
  assert_true "should append a new entry when branches_<slug>.md already has prior PRs (new PR-2 appended)" "$has_pr2"
  assert_true "should append a new entry when branches_<slug>.md already has prior PRs (PR-1 stays before PR-2)" "$pr1_before_pr2"
}

it_should_backfill_the_no_checkout_prs_entry_when_the_manifest_is_created_on_pr2_batch_end() {
  local branches_file="$work_dir/corner-backfill/branches_test-slug.md"
  mkdir -p "$(dirname "$branches_file")"
  run_script "$branches_file" "test-slug" "PR-2" "feat-foo/pr2" "PR-1" "feat-foo"
  assert_eq "should backfill the no-checkout PR's entry when the manifest is created on PR-2's batch-end (exit code)" "0" "$VERDICT_EXIT"

  local pr1_line pr2_line backfill_before_primary="false"
  pr1_line=$(grep -n '\*\*PR-1\*\*' "$branches_file" | cut -d: -f1)
  pr2_line=$(grep -n '\*\*PR-2\*\*' "$branches_file" | cut -d: -f1)
  if [ -n "$pr1_line" ] && [ -n "$pr2_line" ] && [ "$pr1_line" -lt "$pr2_line" ]; then
    backfill_before_primary="true"
  fi
  assert_true "should backfill the no-checkout PR's entry when the manifest is created on PR-2's batch-end (backfilled PR-1 entry precedes PR-2's own entry)" "$backfill_before_primary"

  local content
  content=$(cat "$branches_file")
  local has_backfill_branch="false"
  [[ "$content" == *'**PR-1** — branch: `feat-foo`'* ]] && has_backfill_branch="true"
  assert_true "should backfill the no-checkout PR's entry when the manifest is created on PR-2's batch-end (backfilled branch name recorded)" "$has_backfill_branch"
}

it_should_leave_the_manifest_unchanged_when_appending_the_same_pr_n_entry_twice() {
  local branches_file="$work_dir/failure-idempotent/branches_test-slug.md"
  mkdir -p "$(dirname "$branches_file")"
  run_script "$branches_file" "test-slug" "PR-1" "feat-foo/pr1"
  local first_content
  first_content=$(cat "$branches_file")

  run_script "$branches_file" "test-slug" "PR-1" "feat-foo/pr1"
  assert_eq "should leave the manifest unchanged when appending the same PR-N entry twice (idempotent re-run) (exit code)" "0" "$VERDICT_EXIT"

  local second_content
  second_content=$(cat "$branches_file")
  assert_eq "should leave the manifest unchanged when appending the same PR-N entry twice (idempotent re-run) (content unchanged)" "$first_content" "$second_content"
}

it_should_preserve_a_pre_existing_symlink_when_the_manifest_is_created_through_it() {
  local real_dir="$work_dir/symlink-safety/real-checkout"
  local worktree_dir="$work_dir/symlink-safety/worktree"
  mkdir -p "$real_dir" "$worktree_dir"

  local real_path="$real_dir/branches_test-slug.md"
  local worktree_path="$worktree_dir/branches_test-slug.md"

  # A dangling symlink: worktree-setup.md's own convention (branches_<slug>.md
  # may not exist yet in the original checkout, so the symlink is created
  # before its target exists, per worktree-setup.md).
  ln -s "$real_path" "$worktree_path"

  run_script "$worktree_path" "test-slug" "PR-1" "feat-foo/pr1"
  assert_eq "should preserve a pre-existing symlink at branches_<slug>.md when the manifest is created through it (exit code)" "0" "$VERDICT_EXIT"

  local is_symlink="false"
  [ -L "$worktree_path" ] && is_symlink="true"
  assert_true "should preserve a pre-existing symlink at branches_<slug>.md when the manifest is created through it (still a symlink, not replaced by a regular file)" "$is_symlink"

  local resolves_correctly="false"
  if [ -L "$worktree_path" ] && [ "$(readlink "$worktree_path")" = "$real_path" ]; then
    resolves_correctly="true"
  fi
  assert_true "should preserve a pre-existing symlink at branches_<slug>.md when the manifest is created through it (still resolves to the original checkout's path)" "$resolves_correctly"

  local target_has_content="false"
  if [ -f "$real_path" ] && grep -q '\*\*PR-1\*\*' "$real_path"; then
    target_has_content="true"
  fi
  assert_true "should preserve a pre-existing symlink at branches_<slug>.md when the manifest is created through it (write landed at the resolved target path)" "$target_has_content"
}

it_should_create_branches_file_with_one_entry_when_none_exists_yet
it_should_append_a_new_entry_when_branches_file_already_has_prior_prs
it_should_backfill_the_no_checkout_prs_entry_when_the_manifest_is_created_on_pr2_batch_end
it_should_leave_the_manifest_unchanged_when_appending_the_same_pr_n_entry_twice
it_should_preserve_a_pre_existing_symlink_when_the_manifest_is_created_through_it

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
