#!/usr/bin/env bash
# test-resolve-task-order.sh - plain-bash test file for resolve-task-order.sh.
#
# Usage:
#   bash test-resolve-task-order.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/resolve-task-order.sh"

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

# assert_true - inline assert helper: prints ok/not-ok on a boolean condition string.
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

# run_script - invokes resolve-task-order.sh against a plan-file fixture and a
# task-ids list, capturing stdout/stderr/exit code into
# VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local plan_file="$1" task_ids="$2"
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" "$task_ids" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes the given Task-Breakdown-section body to a fresh plan
# fixture under work_dir, returns its path via stdout.
write_plan() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## Task Breakdown\n\n%s\n' "$body" >"$path"
  printf '%s' "$path"
}

# run_verify_script - invokes resolve-task-order.sh in --verify mode against a
# plan-file fixture, the in-scope task-ids set (what the user was shown),
# and a candidate task-order list (what the user typed back), capturing
# stdout/stderr/exit code into VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_verify_script() {
  local plan_file="$1" task_ids="$2" candidate_order="$3"
  local out_file="$work_dir/verify-stdout.txt"
  local err_file="$work_dir/verify-stderr.txt"
  bash "$SCRIPT" --verify "$plan_file" "$task_ids" "$candidate_order" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

it_should_print_a_linear_order_for_a_simple_chain_of_dependencies() {
  local fixture
  fixture=$(write_plan "chain" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 2')
  run_script "$fixture" "1, 2, 3"
  assert_eq "should print a linear order for a simple chain of dependencies (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should print a linear order for a simple chain of dependencies (order)" "1, 2, 3" "$VERDICT_OUT"
}

it_should_print_a_linear_order_for_a_fork_where_one_task_has_two_independent_children() {
  local fixture
  fixture=$(write_plan "fork" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 1')
  run_script "$fixture" "1, 2, 3"
  assert_eq "should print a linear order for a fork where one task has two independent children (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should print a linear order for a fork where one task has two independent children (order)" "1, 2, 3" "$VERDICT_OUT"
}

it_should_print_every_id_in_lowest_id_order_for_a_fully_disconnected_task_set() {
  local fixture
  fixture=$(write_plan "disconnected" '### 2. A task

**Depends on**: none

### 5. Another task

**Depends on**: none

### 9. Yet another task

**Depends on**: none')
  run_script "$fixture" "5, 2, 9"
  assert_eq "should print every id in lowest-id order for a fully disconnected task set (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should print every id in lowest-id order for a fully disconnected task set (order)" "2, 5, 9" "$VERDICT_OUT"
}

it_should_refuse_to_stack_and_name_both_parents_when_a_task_has_a_true_join_inside_the_requested_set() {
  local fixture
  fixture=$(write_plan "join" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 2
- Task 3')
  run_script "$fixture" "1, 2, 3, 4"
  assert_eq "should refuse to stack when a task has a true join inside the requested set (exit code)" "1" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"task 4 depends on 2 in-set tasks (2, 3)"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should refuse to stack when a task has a true join inside the requested set (names both parents)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should refuse to stack when a task has a true join inside the requested set (names both parents)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_print_an_order_when_a_joins_second_parent_is_outside_the_requested_set() {
  local fixture
  fixture=$(write_plan "join-outside-set" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 2
- Task 5

### 5. Fifth task

**Depends on**: none')
  run_script "$fixture" "1, 2, 4"
  assert_eq "should print an order when a join's second parent is outside the requested set (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should print an order when a join's second parent is outside the requested set (order)" "1, 2, 4" "$VERDICT_OUT"
}

it_should_break_ties_by_lowest_numeric_id_across_multiple_availability_rounds() {
  local fixture
  fixture=$(write_plan "tie-break" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**: none')
  run_script "$fixture" "4, 3, 2, 1"
  assert_eq "should break ties by lowest numeric id across multiple availability rounds (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should break ties by lowest numeric id across multiple availability rounds (order)" "1, 2, 3, 4" "$VERDICT_OUT"
}

it_should_linearize_a_subset_of_the_plans_task_ids_ignoring_tasks_outside_the_subset() {
  local fixture
  fixture=$(write_plan "subset" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 2

### 4. Fourth task

**Depends on**:
- Task 3

### 5. Fifth task

**Depends on**:
- Task 4')
  run_script "$fixture" "1, 3"
  assert_eq "should linearize a subset of the plan's task ids, ignoring tasks outside the subset (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should linearize a subset of the plan's task ids, ignoring tasks outside the subset (order)" "1, 3" "$VERDICT_OUT"
}

it_should_sort_numeric_ids_correctly_while_parsing_both_depends_on_grammar_forms() {
  local fixture
  fixture=$(write_plan "numeric-and-grammar" '### 9. Ninth task

**Depends on**: none

### 10. Tenth task

**Depends on**: none

### 11. Eleventh task

**Depends on**:
- Task 9')
  run_script "$fixture" "10, 9, 11"
  assert_eq "should sort numeric ids correctly (9 before 10) while parsing both none and bullet-list Depends-on forms (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should sort numeric ids correctly (9 before 10) while parsing both none and bullet-list Depends-on forms (order)" "9, 10, 11" "$VERDICT_OUT"
}

it_should_be_tolerant_of_task_ids_without_spaces_after_commas() {
  local fixture
  fixture=$(write_plan "no-space-commas" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 2')
  run_script "$fixture" "1,2,3"
  assert_eq "should be tolerant of task ids without spaces after commas (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should be tolerant of task ids without spaces after commas (order)" "1, 2, 3" "$VERDICT_OUT"
}

it_should_error_when_the_plan_file_does_not_exist() {
  run_script "$work_dir/does-not-exist.md" "1"
  assert_eq "should error when the plan file does not exist (exit code)" "2" "$VERDICT_EXIT"
  assert_true "should error when the plan file does not exist (diagnostic present)" "$([ -n "$VERDICT_ERR" ] && echo true || echo false)"
}

it_should_error_when_invoked_with_the_wrong_number_of_arguments() {
  local fixture
  fixture=$(write_plan "wrong-args" '### 1. First task

**Depends on**: none')
  local err_file="$work_dir/wrong-args-stderr.txt"
  bash "$SCRIPT" "$fixture" >/dev/null 2>"$err_file"
  local exit_code=$?
  assert_eq "should error when invoked with the wrong number of arguments (exit code)" "2" "$exit_code"
  assert_true "should error when invoked with the wrong number of arguments (diagnostic present)" "$([ -s "$err_file" ] && echo true || echo false)"
}

it_should_error_when_a_requested_task_id_does_not_exist_in_the_task_breakdown() {
  local fixture
  fixture=$(write_plan "unknown-id" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1')
  run_script "$fixture" "1, 2, 9"
  assert_eq "should error when a requested task id does not exist in the Task Breakdown (exit code)" "2" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"9"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should error when a requested task id does not exist in the Task Breakdown (names the missing id)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should error when a requested task id does not exist in the Task Breakdown (names the missing id)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_error_when_the_plan_has_no_task_breakdown_section() {
  local path="$work_dir/no-breakdown.md"
  printf '## Some Other Section\n\nnothing relevant here\n' >"$path"
  run_script "$path" "1"
  assert_eq "should error when the plan has no Task Breakdown section (exit code)" "2" "$VERDICT_EXIT"
  assert_true "should error when the plan has no Task Breakdown section (diagnostic present)" "$([ -n "$VERDICT_ERR" ] && echo true || echo false)"
}

it_should_accept_a_valid_non_obvious_reorder_under_verify_that_is_not_the_lowest_id_order() {
  local fixture
  fixture=$(write_plan "verify-valid-reorder" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**: none

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 1')
  run_verify_script "$fixture" "1, 2, 3, 4" "2, 1, 3, 4"
  assert_eq "should accept a valid non-obvious reorder under --verify (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should accept a valid non-obvious reorder under --verify (no output)" "" "$VERDICT_OUT"
}

it_should_reject_under_verify_a_task_ordered_before_its_dependency() {
  local fixture
  fixture=$(write_plan "verify-single-violation" '### 1. First task

**Depends on**: none

### 3. Third task

**Depends on**:
- Task 1')
  run_verify_script "$fixture" "1, 3" "3, 1"
  assert_eq "should reject under --verify a task ordered before its dependency (exit code)" "1" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"task 3 is ordered before its dependency task 1"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should reject under --verify a task ordered before its dependency (diagnostic names the pair)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should reject under --verify a task ordered before its dependency (diagnostic names the pair)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_report_every_offending_pair_under_verify_when_multiple_tasks_precede_their_dependencies() {
  local fixture
  fixture=$(write_plan "verify-multiple-violations" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**: none

### 4. Fourth task

**Depends on**:
- Task 3')
  run_verify_script "$fixture" "1, 2, 3, 4" "2, 1, 4, 3"
  assert_eq "should report every offending pair under --verify (exit code)" "1" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"task 2 is ordered before its dependency task 1"*"task 4 is ordered before its dependency task 3"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should report every offending pair under --verify (both pairs named, ascending id order)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should report every offending pair under --verify (both pairs named, ascending id order)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_reject_a_join_under_verify_regardless_of_the_candidate_order() {
  local fixture
  fixture=$(write_plan "verify-join" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 2
- Task 3')
  run_verify_script "$fixture" "1, 2, 3, 4" "4, 3, 2, 1"
  assert_eq "should reject a join under --verify regardless of the candidate order (exit code)" "1" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"task 4 depends on 2 in-set tasks (2, 3)"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should reject a join under --verify regardless of the candidate order (names both parents)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should reject a join under --verify regardless of the candidate order (names both parents)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_error_under_verify_when_the_candidate_order_repeats_an_id() {
  local fixture
  fixture=$(write_plan "verify-duplicate" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1')
  run_verify_script "$fixture" "1, 2" "1, 1, 2"
  assert_eq "should error under --verify when the candidate order repeats an id (exit code)" "2" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"1"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should error under --verify when the candidate order repeats an id (names the repeated id)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should error under --verify when the candidate order repeats an id (names the repeated id)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_error_under_verify_when_the_candidate_order_omits_a_task_breakdown_id() {
  local fixture
  fixture=$(write_plan "verify-missing" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 2')
  run_verify_script "$fixture" "1, 2, 3" "1, 2"
  assert_eq "should error under --verify when the candidate order omits a Task Breakdown id (exit code)" "2" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"3"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should error under --verify when the candidate order omits a Task Breakdown id (names the missing id)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should error under --verify when the candidate order omits a Task Breakdown id (names the missing id)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_accept_a_pr_subset_reorder_under_verify_when_the_plan_has_other_prs_tasks_outside_the_scope() {
  local fixture
  fixture=$(write_plan "verify-pr-subset" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**: none

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 3')
  run_verify_script "$fixture" "1, 2" "2, 1"
  assert_eq "should accept a PR-subset reorder under --verify when the plan has other PRs' tasks outside the scope (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should accept a PR-subset reorder under --verify when the plan has other PRs' tasks outside the scope (no output)" "" "$VERDICT_OUT"
}

it_should_scope_the_omission_diagnostic_to_the_in_scope_task_ids_under_verify() {
  local fixture
  fixture=$(write_plan "verify-scoped-omission" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**: none

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 3')
  run_verify_script "$fixture" "1, 2" "2"
  assert_eq "should scope the omission diagnostic to the in-scope task ids under --verify (exit code)" "2" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"3"* | *"4"*)
    fail_count=$((fail_count + 1))
    printf 'not ok - should scope the omission diagnostic to the in-scope task ids under --verify (names only the in-scope id)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  *"1"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should scope the omission diagnostic to the in-scope task ids under --verify (names only the in-scope id)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should scope the omission diagnostic to the in-scope task ids under --verify (names only the in-scope id)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_reject_a_parent_ordering_violation_within_a_pr_subset_under_verify() {
  local fixture
  fixture=$(write_plan "verify-subset-violation" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**: none

### 3. Third task

**Depends on**:
- Task 1

### 4. Fourth task

**Depends on**:
- Task 3')
  run_verify_script "$fixture" "1, 3" "3, 1"
  assert_eq "should reject a parent-ordering violation within a PR subset under --verify (exit code)" "1" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
  *"task 3 is ordered before its dependency task 1"*)
    pass_count=$((pass_count + 1))
    printf 'ok - should reject a parent-ordering violation within a PR subset under --verify (diagnostic names the pair)\n'
    ;;
  *)
    fail_count=$((fail_count + 1))
    printf 'not ok - should reject a parent-ordering violation within a PR subset under --verify (diagnostic names the pair)\n  actual stderr: %s\n' "$VERDICT_ERR"
    ;;
  esac
}

it_should_error_when_verify_is_invoked_with_the_wrong_number_of_arguments() {
  local fixture
  fixture=$(write_plan "verify-wrong-args" '### 1. First task

**Depends on**: none')
  local err_file="$work_dir/verify-wrong-args-stderr.txt"
  bash "$SCRIPT" --verify "$fixture" >/dev/null 2>"$err_file"
  local exit_code=$?
  assert_eq "should error when --verify is invoked with the wrong number of arguments (exit code)" "2" "$exit_code"
  assert_true "should error when --verify is invoked with the wrong number of arguments (diagnostic present)" "$([ -s "$err_file" ] && echo true || echo false)"
}

it_should_print_a_linear_order_for_a_simple_chain_of_dependencies
it_should_print_a_linear_order_for_a_fork_where_one_task_has_two_independent_children
it_should_print_every_id_in_lowest_id_order_for_a_fully_disconnected_task_set
it_should_refuse_to_stack_and_name_both_parents_when_a_task_has_a_true_join_inside_the_requested_set
it_should_print_an_order_when_a_joins_second_parent_is_outside_the_requested_set
it_should_break_ties_by_lowest_numeric_id_across_multiple_availability_rounds
it_should_linearize_a_subset_of_the_plans_task_ids_ignoring_tasks_outside_the_subset
it_should_sort_numeric_ids_correctly_while_parsing_both_depends_on_grammar_forms
it_should_be_tolerant_of_task_ids_without_spaces_after_commas
it_should_error_when_the_plan_file_does_not_exist
it_should_error_when_invoked_with_the_wrong_number_of_arguments
it_should_error_when_a_requested_task_id_does_not_exist_in_the_task_breakdown
it_should_error_when_the_plan_has_no_task_breakdown_section
it_should_accept_a_valid_non_obvious_reorder_under_verify_that_is_not_the_lowest_id_order
it_should_reject_under_verify_a_task_ordered_before_its_dependency
it_should_report_every_offending_pair_under_verify_when_multiple_tasks_precede_their_dependencies
it_should_reject_a_join_under_verify_regardless_of_the_candidate_order
it_should_error_under_verify_when_the_candidate_order_repeats_an_id
it_should_error_under_verify_when_the_candidate_order_omits_a_task_breakdown_id
it_should_accept_a_pr_subset_reorder_under_verify_when_the_plan_has_other_prs_tasks_outside_the_scope
it_should_scope_the_omission_diagnostic_to_the_in_scope_task_ids_under_verify
it_should_reject_a_parent_ordering_violation_within_a_pr_subset_under_verify
it_should_error_when_verify_is_invoked_with_the_wrong_number_of_arguments

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
