#!/usr/bin/env bash
# test-check-tasks-dag.sh - plain-bash test file for check-tasks-dag.sh.
#
# Usage:
#   bash test-check-tasks-dag.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-tasks-dag.sh"

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

# run_script - invokes check-tasks-dag.sh against a plan-file fixture,
# capturing stderr/exit code into VERDICT_ERR/VERDICT_EXIT (stdout is
# discarded — these tests assert on exit code and diagnostic presence only).
run_script() {
  local plan_file="$1"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes the given Task-Breakdown-section body to a fresh plan
# fixture under work_dir, returns its path via stdout.
write_plan() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## Task Breakdown\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_pass_when_every_task_dependency_resolves_to_a_real_non_cyclic_task_id() {
  local fixture
  fixture=$(write_plan "happy-resolves" '### 1. [Done] First task

**Depends on**: none

### 2. New second task

**Depends on**:
- Task 1

### 3. New third task

**Depends on**:
- Task 1
- Task 2')
  run_script "$fixture"
  assert_eq "should pass when every task dependency resolves to a real, non-cyclic task id" "0" "$VERDICT_EXIT"
}

it_should_pass_when_no_task_declares_a_depends_on_entry_fully_independent_task_list() {
  local fixture
  fixture=$(write_plan "independent" '### 1. New first task

**Depends on**: none

### 2. New second task

**Depends on**: none

### 3. New third task

**Depends on**: none')
  run_script "$fixture"
  assert_eq "should pass when no task declares a Depends on entry (fully independent task list)" "0" "$VERDICT_EXIT"
}

it_should_detect_a_two_task_cycle_when_task_1_depends_on_task_2_and_task_2_depends_on_task_1() {
  local fixture
  fixture=$(write_plan "cycle" '### 1. New first task

**Depends on**:
- Task 2

### 2. New second task

**Depends on**:
- Task 1')
  run_script "$fixture"
  assert_eq "should detect a two-task cycle when Task 1 depends on Task 2 and Task 2 depends on Task 1 (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should detect a two-task cycle when Task 1 depends on Task 2 and Task 2 depends on Task 1 (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should detect a two-task cycle when Task 1 depends on Task 2 and Task 2 depends on Task 1 (diagnostic present)\n'
  fi
}

it_should_detect_a_dangling_reference_when_a_task_depends_on_a_task_id_absent_from_the_task_breakdown() {
  local fixture
  fixture=$(write_plan "dangling" '### 1. New first task

**Depends on**: none

### 2. New second task

**Depends on**:
- Task 9')
  run_script "$fixture"
  assert_eq "should detect a dangling reference when a task depends on a task id absent from the Task Breakdown (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should detect a dangling reference when a task depends on a task id absent from the Task Breakdown (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should detect a dangling reference when a task depends on a task id absent from the Task Breakdown (diagnostic present)\n'
  fi
}

it_should_detect_a_duplicate_label_when_two_task_breakdown_entries_share_the_same_task_number() {
  local fixture
  fixture=$(write_plan "duplicate" '### 1. New first task

**Depends on**: none

### 1. New duplicate task

**Depends on**: none')
  run_script "$fixture"
  assert_eq "should detect a duplicate label when two Task Breakdown entries share the same task number (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should detect a duplicate label when two Task Breakdown entries share the same task number (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should detect a duplicate label when two Task Breakdown entries share the same task number (diagnostic present)\n'
  fi
}

it_should_pass_when_every_task_dependency_resolves_to_a_real_non_cyclic_task_id
it_should_pass_when_no_task_declares_a_depends_on_entry_fully_independent_task_list
it_should_detect_a_two_task_cycle_when_task_1_depends_on_task_2_and_task_2_depends_on_task_1
it_should_detect_a_dangling_reference_when_a_task_depends_on_a_task_id_absent_from_the_task_breakdown
it_should_detect_a_duplicate_label_when_two_task_breakdown_entries_share_the_same_task_number

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
