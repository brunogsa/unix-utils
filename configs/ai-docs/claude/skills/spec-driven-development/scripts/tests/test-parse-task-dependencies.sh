#!/usr/bin/env bash
# test-parse-task-dependencies.sh - plain-bash test file for
# parse-task-dependencies.sh, the one parser of the Task
# Breakdown's **Depends on** grammar.
#
# Usage:
#   bash test-parse-task-dependencies.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/parse-task-dependencies.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual,
# prints ok/not-ok.
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

# run_script - invokes parse-task-dependencies.sh against a
# plan-file fixture, capturing stdout/stderr/exit code into
# VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local plan_file="$1"
  bash "$SCRIPT" "$plan_file" >"$work_dir/stdout.txt" 2>"$work_dir/stderr.txt"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$work_dir/stdout.txt")
  VERDICT_ERR=$(cat "$work_dir/stderr.txt")
}

# write_plan - writes the given Task-Breakdown-section body to a
# fresh plan fixture under work_dir, returns its path via
# stdout.
write_plan() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## Task Breakdown\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

canonical_grammar="  canonical grammar: '**Depends on**: none', or a bare '**Depends on**:' line followed by either a lone '- none' bullet or one '- Task N' bullet per dependency (never both)"

it_should_print_one_edge_line_per_task_for_none_and_task_bullets() {
  local fixture
  fixture=$(write_plan "edges" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1

### 3. Third task

**Depends on**:
- Task 1
- Task 2')
  run_script "$fixture"
  assert_eq "should print one edge line per task for none and Task bullets (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should print one edge line per task for none and Task bullets (stdout)" "$(printf 'Task 1\t\nTask 2\tTask 1\nTask 3\tTask 1,Task 2')" "$VERDICT_OUT"
}

it_should_read_a_lone_none_bullet_as_no_dependencies() {
  local fixture
  fixture=$(write_plan "none-bullet" '### 1. First task

**Depends on**:
- none

### 2. Second task

**Depends on**:
- Task 1')
  run_script "$fixture"
  assert_eq "should read a lone none bullet as no dependencies (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should read a lone none bullet as no dependencies (stdout)" "$(printf 'Task 1\t\nTask 2\tTask 1')" "$VERDICT_OUT"
}

it_should_reject_a_none_bullet_mixed_with_task_bullets_in_either_order() {
  local fixture
  fixture=$(write_plan "none-then-task" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- none
- Task 1')
  run_script "$fixture"
  assert_eq "should reject none-then-Task bullets (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should reject none-then-Task bullets (stdout empty)" "" "$VERDICT_OUT"
  assert_eq "should reject none-then-Task bullets (canonical error)" "$(printf 'error: unparsable **Depends on** field in: Task 2\n%s' "$canonical_grammar")" "$VERDICT_ERR"

  fixture=$(write_plan "task-then-none" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**:
- Task 1
- none')
  run_script "$fixture"
  assert_eq "should reject Task-then-none bullets (exit code)" "1" "$VERDICT_EXIT"
}

it_should_reject_an_inline_task_reference_and_a_bare_field_with_no_bullet() {
  local fixture
  fixture=$(write_plan "malformed" '### 1. First task

**Depends on**: none

### 2. Second task

**Depends on**: Task 1

### 3. Third task

**Depends on**:

Prose that is not a bullet.')
  run_script "$fixture"
  assert_eq "should reject an inline Task reference and a bare field with no bullet (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should reject an inline Task reference and a bare field with no bullet (canonical error names every offender)" "$(printf 'error: unparsable **Depends on** field in: Task 2, Task 3\n%s' "$canonical_grammar")" "$VERDICT_ERR"
}

it_should_error_when_the_section_has_no_task_entries() {
  local fixture
  fixture=$(write_plan "no-entries" 'Nothing here is a task heading.')
  run_script "$fixture"
  assert_eq "should error when the section has no task entries (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should error when the section has no task entries (diagnostic)" "error: Task Breakdown section found but no task entries could be parsed from it" "$VERDICT_ERR"
}

it_should_error_on_a_missing_plan_file_and_on_a_wrong_argument_count() {
  run_script "$work_dir/absent.md"
  assert_eq "should error on a missing plan file (exit code)" "2" "$VERDICT_EXIT"
  bash "$SCRIPT" >/dev/null 2>&1
  assert_eq "should error on a wrong argument count (exit code)" "2" "$?"
}

it_should_print_an_edge_line_for_a_task_that_declares_no_depends_on_field() {
  local fixture
  fixture=$(write_plan "no-field" '### 1. First task

Just a description.')
  run_script "$fixture"
  assert_eq "should print an edge line for a task that declares no Depends on field (stdout)" "$(printf 'Task 1\t')" "$VERDICT_OUT"
}

it_should_report_a_blank_line_between_depends_on_and_its_bullet_as_a_plan_finding() {
  local fixture
  fixture=$(write_plan "blank-before-bullet" '### 1. First task

**Depends on**:

- none

### 2. Second task

**Depends on**:
- Task 1')
  run_script "$fixture"
  assert_eq "should report a blank line between Depends on and its bullet as a plan finding (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should report a blank line between Depends on and its bullet as a plan finding (canonical error)" "$(printf 'error: unparsable **Depends on** field in: Task 1\n%s' "$canonical_grammar")" "$VERDICT_ERR"
}

it_should_print_one_edge_line_per_task_for_none_and_task_bullets
it_should_read_a_lone_none_bullet_as_no_dependencies
it_should_reject_a_none_bullet_mixed_with_task_bullets_in_either_order
it_should_reject_an_inline_task_reference_and_a_bare_field_with_no_bullet
it_should_error_when_the_section_has_no_task_entries
it_should_error_on_a_missing_plan_file_and_on_a_wrong_argument_count
it_should_print_an_edge_line_for_a_task_that_declares_no_depends_on_field
it_should_report_a_blank_line_between_depends_on_and_its_bullet_as_a_plan_finding

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
