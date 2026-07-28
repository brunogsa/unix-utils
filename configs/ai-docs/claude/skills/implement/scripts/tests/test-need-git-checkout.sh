#!/usr/bin/env bash
# test-need-git-checkout.sh - plain-bash test file for need-git-checkout.sh.
#
# Usage:
#   bash test-need-git-checkout.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/need-git-checkout.sh"

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

# run_script - invokes need-git-checkout.sh against a plan-file fixture and a
# PR-N label, capturing stdout/stderr/exit code into
# VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
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
# fixture named plan_<slug>.md under work_dir, returns its path via stdout.
write_plan() {
  local slug="$1" body="$2"
  local path="$work_dir/plan_$slug.md"
  printf '## PR Breakdown\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_say_no_checkout_needed_on_the_first_invocation_targeting_a_dag_root_pr() {
  local plan_file
  plan_file=$(write_plan "happy-root" '1. **PR-1** — Naming and validators. Tasks: 1, 2, 3. Depends on: none.
2. **PR-2** — Core loop. Tasks: 4, 5. Depends on: PR-1.')

  run_script "$plan_file" "PR-1"
  assert_eq "should say no checkout needed on the first /implement invocation in a worktree targeting a DAG-root PR (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should say no checkout needed on the first /implement invocation in a worktree targeting a DAG-root PR (decision)" "no" "$VERDICT_OUT"
}

it_should_say_checkout_needed_when_an_earlier_pr_already_recorded_its_branch() {
  local plan_file
  plan_file=$(write_plan "happy-completed-batch" '1. **[Done] PR-1** — Naming and validators. Tasks: 1, 2, 3. Depends on: none. Branch: `feat-foo/pr1`.
2. **PR-2** — Core loop. Tasks: 4, 5. Depends on: none.')

  run_script "$plan_file" "PR-2"
  assert_eq "should say checkout needed when an earlier PR already recorded its branch on the plan (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should say checkout needed when an earlier PR already recorded its branch on the plan (decision)" "yes" "$VERDICT_OUT"
}

it_should_say_checkout_needed_on_first_invocation_when_the_targeted_pr_has_a_dependency() {
  local plan_file
  plan_file=$(write_plan "corner-dependent-first-run" '1. **PR-1** — Naming and validators. Tasks: 1, 2, 3. Depends on: none.
2. **PR-2** — Core loop. Tasks: 4, 5. Depends on: PR-1.')

  run_script "$plan_file" "PR-2"
  assert_eq "should say checkout needed on the first invocation when the targeted PR has a dependency, even though it's the first run (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should say checkout needed on the first invocation when the targeted PR has a dependency, even though it's the first run (decision)" "yes" "$VERDICT_OUT"
}

it_should_error_when_the_requested_pr_n_label_is_absent_from_the_pr_breakdown() {
  local plan_file
  plan_file=$(write_plan "failure-absent-label" '1. **PR-1** — First slice. Tasks: 1. Depends on: none.
2. **PR-2** — Second slice. Tasks: 2. Depends on: PR-1.')

  run_script "$plan_file" "PR-9"
  assert_eq "should error when given a PR-N label absent from the plan's PR Breakdown (exit code)" "1" "$VERDICT_EXIT"
  local has_diagnostic="false"
  [ -n "$VERDICT_ERR" ] && has_diagnostic="true"
  assert_true "should error when given a PR-N label absent from the plan's PR Breakdown (diagnostic present)" "$has_diagnostic"
}

it_should_say_no_checkout_needed_on_the_first_invocation_targeting_a_dag_root_pr
it_should_say_checkout_needed_when_an_earlier_pr_already_recorded_its_branch
it_should_say_checkout_needed_on_first_invocation_when_the_targeted_pr_has_a_dependency
it_should_error_when_the_requested_pr_n_label_is_absent_from_the_pr_breakdown

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
