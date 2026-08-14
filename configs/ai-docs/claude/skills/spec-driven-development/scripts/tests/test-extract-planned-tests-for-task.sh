#!/usr/bin/env bash
# test-extract-planned-tests-for-task.sh - plain-bash test file
# for extract-planned-tests-for-task.sh.
#
# Usage:
#   bash test-extract-planned-tests-for-task.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.
#
# Covers BOTH forms the script must accept:
# - annotated form (new): filters Test Design by the task's T<n>
#   tokens.
#
#     These cases genuinely force the new behavior — RED before
#     it lands.
#
# - list form (old): parses the task's own `**Tests
#   (planned)**:` bullet list, unchanged from before
#   this dispatch.
#
#     This form had zero dedicated coverage before this
#     file existed, so these cases are added as regression
#     pins for already-correct behavior rather than to
#     force new behavior.
#
#     They may already pass before the annotated-form
#     branch is added, since the old code path is
#     untouched.
#

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/extract-planned-tests-for-task.sh"

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

# run_script - invokes extract-planned-tests-for-task.sh,
# capturing stdout/exit code into VERDICT_OUT/VERDICT_EXIT.
run_script() {
  local plan_file="$1" task_n="$2"
  local out_file="$work_dir/stdout.txt"
  bash "$SCRIPT" "$plan_file" "$task_n" >"$out_file" 2>/dev/null
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

# write_plan - writes a fresh plan fixture from its Test Design
# and Task Breakdown bodies, returns its path via stdout.
write_plan() {
  local name="$1" design_body="$2" task_body="$3"
  local path="$work_dir/$name.md"
  printf '# Plan: %s\n\n## Test Design\n\n%s\n\n## Task Breakdown\n\n%s\n' \
    "$name" "$design_body" "$task_body" > "$path"
  printf '%s' "$path"
}

ANNOTATED_DESIGN='```
describe("thing", () => {
  // Happy cases
  it("should accept a valid path");   // T1
  // Failure scenarios
  it("should reject a missing path");   // T2
  it("should reject an empty path");   // T1 T2
});
```'

it_should_filter_test_design_by_t_n_and_print_bare_titles_in_annotated_form() {
  local fixture
  fixture=$(write_plan "annotated-filter" "$ANNOTATED_DESIGN" \
    '### 1. Wire the gate

No Tests (planned) bullet needed — the T1 annotations on the it() lines above already name this task.

### 2. Add validation

No Tests (planned) bullet needed — the T2 annotations on the it() lines above already name this task.')
  run_script "$fixture" "1"
  assert_eq "should filter Test Design by T1 and print bare titles in annotated form" \
    "$(printf 'should accept a valid path\nshould reject an empty path')" \
    "$VERDICT_OUT"
  assert_eq "should filter Test Design by T1 and print bare titles in annotated form (exit code)" "0" "$VERDICT_EXIT"
}

it_should_filter_test_design_by_a_different_t_n_and_print_only_that_tasks_titles_in_annotated_form() {
  local fixture
  fixture=$(write_plan "annotated-filter-other-task" "$ANNOTATED_DESIGN" \
    '### 1. Wire the gate

No Tests (planned) bullet needed — the T1 annotations on the it() lines above already name this task.

### 2. Add validation

No Tests (planned) bullet needed — the T2 annotations on the it() lines above already name this task.')
  run_script "$fixture" "2"
  assert_eq "should filter Test Design by T2 and print only that task's titles in annotated form" \
    "$(printf 'should reject a missing path\nshould reject an empty path')" \
    "$VERDICT_OUT"
}

it_should_print_nothing_when_no_it_in_test_design_carries_the_tasks_t_n_token_in_annotated_form() {
  local fixture
  fixture=$(write_plan "annotated-no-match" "$ANNOTATED_DESIGN" \
    '### 1. Wire the gate

No Tests (planned) bullet needed — the T1 annotations on the it() lines above already name this task.

### 2. Add validation

No Tests (planned) bullet needed — the T2 annotations on the it() lines above already name this task.

### 3. Update the changelog

No Tests (planned) bullet needed — this task has no annotated it() at all.')
  run_script "$fixture" "3"
  assert_eq "should print nothing when no it() in Test Design carries the task's T<n> token in annotated form" "" "$VERDICT_OUT"
  assert_eq "should print nothing when no it() in Test Design carries the task's T<n> token in annotated form (exit code)" "0" "$VERDICT_EXIT"
}

LIST_FORM_DESIGN='```
describe("thing", () => {
  // Happy cases
  it("should accept a valid path");
});
```'

it_should_print_cleaned_titles_for_a_tasks_planned_test_list_in_list_form() {
  local fixture
  fixture=$(write_plan "list-form-titles" "$LIST_FORM_DESIGN" \
    '### 1. Wire the gate

**Tests (planned)**:
- "should accept a valid path"
- "should reject a missing path"   [on-demand]')
  run_script "$fixture" "1"
  assert_eq "should print cleaned titles for a task's planned-test list in list form" \
    "$(printf 'should accept a valid path\nshould reject a missing path')" \
    "$VERDICT_OUT"
}

it_should_print_nothing_when_a_tasks_tests_planned_is_explicit_n_a_in_list_form() {
  local fixture
  fixture=$(write_plan "list-form-n-a" "$LIST_FORM_DESIGN" \
    '### 1. Wire the gate

**Tests (planned)**: N/A — documentation-only edit.')
  run_script "$fixture" "1"
  assert_eq "should print nothing when a task's Tests (planned) is explicit N/A in list form" "" "$VERDICT_OUT"
  assert_eq "should print nothing when a task's Tests (planned) is explicit N/A in list form (exit code)" "0" "$VERDICT_EXIT"
}

it_should_fail_when_the_tests_planned_bullet_is_missing_in_list_form() {
  local fixture
  fixture=$(write_plan "list-form-missing-bullet" "$LIST_FORM_DESIGN" \
    '### 1. Wire the gate

Some prose with no Tests (planned) bullet at all.')
  run_script "$fixture" "1"
  assert_eq "should fail when the Tests (planned) bullet is missing in list form" "1" "$VERDICT_EXIT"
}

it_should_fail_when_the_task_heading_is_missing() {
  local fixture
  fixture=$(write_plan "missing-task-heading" "$LIST_FORM_DESIGN" \
    '### 1. Wire the gate

**Tests (planned)**:
- "should accept a valid path"')
  run_script "$fixture" "9"
  assert_eq "should fail when the task heading is missing" "1" "$VERDICT_EXIT"
}

it_should_filter_test_design_by_t_n_and_print_bare_titles_in_annotated_form
it_should_filter_test_design_by_a_different_t_n_and_print_only_that_tasks_titles_in_annotated_form
it_should_print_nothing_when_no_it_in_test_design_carries_the_tasks_t_n_token_in_annotated_form
it_should_print_cleaned_titles_for_a_tasks_planned_test_list_in_list_form
it_should_print_nothing_when_a_tasks_tests_planned_is_explicit_n_a_in_list_form
it_should_fail_when_the_tests_planned_bullet_is_missing_in_list_form
it_should_fail_when_the_task_heading_is_missing

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
