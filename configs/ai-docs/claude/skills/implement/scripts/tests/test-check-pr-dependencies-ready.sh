#!/usr/bin/env bash
# test-check-pr-dependencies-ready.sh - plain-bash test file for
# check-pr-dependencies-ready.sh.
#
# Usage:
#   bash test-check-pr-dependencies-ready.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.
#
# Unlike its sibling scripts' tests (pure text-fixture parsing), this script
# performs a real `git merge-base --is-ancestor` check, so several test cases
# build a real git repo per scenario via mktemp -d + git init, entirely
# isolated from the actual unix-utils repo this test file lives in.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-pr-dependencies-ready.sh"

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

# assert_contains - inline assert helper: true when haystack contains needle.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to contain: %s\n  actual:              %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

# run_script - invokes check-pr-dependencies-ready.sh against a plan-file
# fixture, a PR-N label, and a worktree path, capturing stderr/exit code
# into VERDICT_ERR/VERDICT_EXIT. stdout is discarded to a file (not
# captured into a variable) since no assertion below needs it - every
# test asserts on the exit code and/or the stderr diagnostic only.
run_script() {
  local plan_file="$1" pr_label="$2" worktree_path="$3"
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" "$pr_label" "$worktree_path" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes a plan fixture named plan_<slug>.md with the given
# "## PR Breakdown" body and "## Task Breakdown" body, returns its path via
# stdout. The Task Breakdown must come first in a real plan_<slug>.md, but
# this script's own section-scoped parsing never depends on ordering, so
# tests are free to lay them out however's clearest.
write_plan() {
  local slug="$1" task_body="$2" pr_body="$3"
  local path="$work_dir/plan_$slug.md"
  {
    printf '## Task Breakdown\n\n%s\n\n' "$task_body"
    printf '## PR Breakdown\n\n%s\n' "$pr_body"
  } > "$path"
  printf '%s' "$path"
}

# init_repo_with_ancestor_branch - builds a real git repo at <dir> where
# <parent_branch> is an actual ancestor of HEAD (mirrors /implement creating
# a dependent PR's branch from its parent's tip).
init_repo_with_ancestor_branch() {
  local dir="$1" parent_branch="$2"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email "test@example.com"
  git -C "$dir" config user.name "Test"
  printf 'root\n' > "$dir/root.txt"
  git -C "$dir" add root.txt
  git -C "$dir" commit -q -m "root commit"

  git -C "$dir" checkout -q -b "$parent_branch"
  printf 'parent\n' > "$dir/parent.txt"
  git -C "$dir" add parent.txt
  git -C "$dir" commit -q -m "parent PR commit"

  git -C "$dir" checkout -q -b "current-pr-branch"
  printf 'dependent\n' > "$dir/dependent.txt"
  git -C "$dir" add dependent.txt
  git -C "$dir" commit -q -m "dependent PR commit"
}

# init_repo_with_sibling_branch - builds a real git repo at <dir> where
# <parent_branch> is a SIBLING of HEAD, not an ancestor (both branch off the
# same root commit independently) — simulates a worktree that never actually
# checked out the parent's commits.
init_repo_with_sibling_branch() {
  local dir="$1" parent_branch="$2"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config user.email "test@example.com"
  git -C "$dir" config user.name "Test"
  printf 'root\n' > "$dir/root.txt"
  git -C "$dir" add root.txt
  git -C "$dir" commit -q -m "root commit"

  git -C "$dir" checkout -q -b "$parent_branch"
  printf 'parent\n' > "$dir/parent.txt"
  git -C "$dir" add parent.txt
  git -C "$dir" commit -q -m "parent PR commit"

  git -C "$dir" checkout -q main
  git -C "$dir" checkout -q -b "current-pr-branch"
  printf 'dependent\n' > "$dir/dependent.txt"
  git -C "$dir" add dependent.txt
  git -C "$dir" commit -q -m "dependent PR commit, never merged parent"
}

it_should_pass_when_every_parent_prs_tasks_are_done_and_head_descends_from_each_parents_branch() {
  local slug="happy-ready" worktree_dir plan_file
  worktree_dir="$work_dir/$slug-worktree"
  init_repo_with_ancestor_branch "$worktree_dir" "feat-foo/pr1"

  plan_file=$(write_plan "$slug" \
    '### 1. [Done] Naming and validators
### 2. [Done] Core loop' \
    '1. **[Done] PR-1** — Naming and validators. Tasks: 1, 2. Depends on: none. Branch: `feat-foo/pr1`.
2. **PR-2** — Core loop. Tasks: 3. Depends on: PR-1.')

  run_script "$plan_file" "PR-2" "$worktree_dir"
  assert_eq "should pass when every parent PR's tasks are Done and the worktree HEAD descends from each parent's branch tip (exit code)" "0" "$VERDICT_EXIT"
}

it_should_pass_immediately_for_a_pr_with_no_declared_dependencies() {
  local slug="corner-no-parents" worktree_dir plan_file
  worktree_dir="$work_dir/$slug-worktree"
  mkdir -p "$worktree_dir"

  plan_file=$(write_plan "$slug" \
    '### 1. [Done] Naming and validators' \
    '1. **PR-1** — Naming and validators. Tasks: 1. Depends on: none.')

  run_script "$plan_file" "PR-1" "$worktree_dir"
  assert_eq "should pass immediately for a PR with no declared dependencies (exit code)" "0" "$VERDICT_EXIT"
}

it_should_block_and_name_the_outstanding_tasks_when_a_parent_pr_has_any_non_done_task() {
  local slug="failure-outstanding-task" worktree_dir plan_file
  worktree_dir="$work_dir/$slug-worktree"
  init_repo_with_ancestor_branch "$worktree_dir" "feat-foo/pr1"

  plan_file=$(write_plan "$slug" \
    '### 1. [Done] Naming and validators
### 2. Core loop still in progress' \
    '1. **PR-1** — Naming and validators. Tasks: 1, 2. Depends on: none. Branch: `feat-foo/pr1`.
2. **PR-2** — Core loop. Tasks: 3. Depends on: PR-1.')

  run_script "$plan_file" "PR-2" "$worktree_dir"
  assert_eq "should block and name the outstanding tasks when a parent PR has any non-Done task (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should block and name the outstanding tasks when a parent PR has any non-Done task (diagnostic names task 2)" "$VERDICT_ERR" "2"
}

it_should_block_when_head_does_not_descend_from_a_parent_prs_branch_tip_even_if_done() {
  local slug="failure-ancestry-mismatch" worktree_dir plan_file
  worktree_dir="$work_dir/$slug-worktree"
  init_repo_with_sibling_branch "$worktree_dir" "feat-foo/pr1"

  plan_file=$(write_plan "$slug" \
    '### 1. [Done] Naming and validators
### 2. [Done] Core loop' \
    '1. **[Done] PR-1** — Naming and validators. Tasks: 1. Depends on: none. Branch: `feat-foo/pr1`.
2. **PR-2** — Core loop. Tasks: 2. Depends on: PR-1.')

  run_script "$plan_file" "PR-2" "$worktree_dir"
  assert_eq "should block when the worktree HEAD does not descend from a parent PR's branch tip, even if that parent's tasks are all Done (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should block when the worktree HEAD does not descend from a parent PR's branch tip, even if that parent's tasks are all Done (diagnostic names the branch)" "$VERDICT_ERR" "feat-foo/pr1"
}

# [on-demand] multi-parent: a diamond-dependency PR must check EVERY listed
# parent, not just the first — pulled in mid-task per the plan's explicit
# "Multi-parent parsing" requirement, which the four originally planned
# titles above don't individually exercise (each uses a single parent).
it_should_block_naming_the_second_parents_outstanding_task_when_a_pr_has_two_parents_on_demand() {
  local slug="failure-multi-parent" worktree_dir plan_file
  worktree_dir="$work_dir/$slug-worktree"
  mkdir -p "$worktree_dir"
  git -C "$worktree_dir" init -q -b main
  git -C "$worktree_dir" config user.email "test@example.com"
  git -C "$worktree_dir" config user.name "Test"
  printf 'root\n' > "$worktree_dir/root.txt"
  git -C "$worktree_dir" add root.txt
  git -C "$worktree_dir" commit -q -m "root commit"

  git -C "$worktree_dir" checkout -q -b "feat-foo/pr1"
  printf 'parent1\n' > "$worktree_dir/parent1.txt"
  git -C "$worktree_dir" add parent1.txt
  git -C "$worktree_dir" commit -q -m "parent PR-1 commit"

  git -C "$worktree_dir" checkout -q -b "feat-foo/pr2" main
  printf 'parent2\n' > "$worktree_dir/parent2.txt"
  git -C "$worktree_dir" add parent2.txt
  git -C "$worktree_dir" commit -q -m "parent PR-2 commit"

  git -C "$worktree_dir" checkout -q -b "feat-foo/pr3" "feat-foo/pr1"
  git -C "$worktree_dir" merge -q "feat-foo/pr2" -m "merge PR-2 into PR-3"

  plan_file=$(write_plan "$slug" \
    '### 1. [Done] First slice
### 2. Second slice still in progress
### 3. [Done] Third slice' \
    '1. **[Done] PR-1** — First slice. Tasks: 1. Depends on: none. Branch: `feat-foo/pr1`.
2. **PR-2** — Second slice. Tasks: 2. Depends on: none. Branch: `feat-foo/pr2`.
3. **PR-3** — Diamond merge. Tasks: 3. Depends on: PR-1, PR-2.')

  run_script "$plan_file" "PR-3" "$worktree_dir"
  assert_eq "should block naming the second parent's outstanding task when a PR has two parents [on-demand] (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should block naming the second parent's outstanding task when a PR has two parents [on-demand] (diagnostic names PR-2)" "$VERDICT_ERR" "PR-2"
}

it_should_block_when_a_parent_pr_has_no_branch_clause_because_it_never_pushed() {
  local slug="failure-parent-never-pushed" worktree_dir plan_file
  worktree_dir="$work_dir/$slug-worktree"
  init_repo_with_ancestor_branch "$worktree_dir" "feat-foo/pr1"

  plan_file=$(write_plan "$slug" \
    '### 1. [Done] Naming and validators
### 2. [Done] Core loop' \
    '1. **[Done] PR-1** — Naming and validators. Tasks: 1. Depends on: none.
2. **PR-2** — Core loop. Tasks: 2. Depends on: PR-1.')

  run_script "$plan_file" "PR-2" "$worktree_dir"
  assert_eq "should block when a parent PR carries no Branch: clause because its batch never pushed, even with every task Done (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should block when a parent PR carries no Branch: clause because its batch never pushed (diagnostic names the missing clause)" "$VERDICT_ERR" "no Branch: clause"
}

it_should_pass_when_every_parent_prs_tasks_are_done_and_head_descends_from_each_parents_branch
it_should_pass_immediately_for_a_pr_with_no_declared_dependencies
it_should_block_when_a_parent_pr_has_no_branch_clause_because_it_never_pushed
it_should_block_and_name_the_outstanding_tasks_when_a_parent_pr_has_any_non_done_task
it_should_block_when_head_does_not_descend_from_a_parent_prs_branch_tip_even_if_done
it_should_block_naming_the_second_parents_outstanding_task_when_a_pr_has_two_parents_on_demand

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
