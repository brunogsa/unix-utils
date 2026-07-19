#!/usr/bin/env bash
# test-get-pr-tasks.sh - plain-bash test file for get-pr-tasks.sh.
#
# Usage:
#   bash test-get-pr-tasks.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/get-pr-tasks.sh"

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

# run_script - invokes get-pr-tasks.sh against a plan-file fixture and a PR-N
# label, capturing stdout/stderr/exit code into VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local plan_file="$1" pr_label="$2"
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" "$pr_label" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes the given PR-Breakdown-section body to a fresh plan
# fixture under work_dir, returns its path via stdout.
write_plan() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## PR Breakdown\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_resolve_a_pr_n_label_to_its_listed_task_id_list() {
  local fixture
  fixture=$(write_plan "happy" '1. **PR-1** — Naming and validators. Tasks: 1, 2, 3. Depends on: none.
2. **PR-2** — Worktree hygiene. Tasks: 4. Depends on: none.
3. **PR-3** — Core loop. Tasks: 5, 6, 7. Depends on: PR-1, PR-2.')
  run_script "$fixture" "PR-3"
  assert_eq "should resolve a PR-N label to its listed task-id list (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should resolve a PR-N label to its listed task-id list (task list)" "5, 6, 7" "$VERDICT_OUT"
}

it_should_resolve_a_pr_n_label_that_lists_a_single_task() {
  local fixture
  fixture=$(write_plan "corner-single-task" '1. **PR-1** — First slice. Tasks: 1. Depends on: none.
2. **PR-2** — Second slice. Tasks: 4. Depends on: none.')
  run_script "$fixture" "PR-2"
  assert_eq "should resolve a PR-N label that lists a single task (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should resolve a PR-N label that lists a single task (task list)" "4" "$VERDICT_OUT"
}

it_should_error_when_the_requested_pr_n_label_is_absent_from_the_pr_breakdown() {
  local fixture
  fixture=$(write_plan "absent-label" '1. **PR-1** — First slice. Tasks: 1. Depends on: none.
2. **PR-2** — Second slice. Tasks: 2. Depends on: PR-1.')
  run_script "$fixture" "PR-9"
  assert_eq "should error when the requested PR-N label is absent from the PR Breakdown (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should error when the requested PR-N label is absent from the PR Breakdown (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should error when the requested PR-N label is absent from the PR Breakdown (diagnostic present)\n'
  fi
}

it_should_resolve_a_pr_n_label_to_its_listed_task_id_list
it_should_resolve_a_pr_n_label_that_lists_a_single_task
it_should_error_when_the_requested_pr_n_label_is_absent_from_the_pr_breakdown

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
