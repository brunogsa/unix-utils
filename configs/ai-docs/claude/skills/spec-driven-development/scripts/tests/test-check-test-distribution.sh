#!/usr/bin/env bash
# test-check-test-distribution.sh - plain-bash test file for
# check-test-distribution.sh.
#
# Usage:
#   bash test-check-test-distribution.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-test-distribution.sh"

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

# assert_contains - passes when the haystack carries the given
# literal text.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  missing text: %s\n  actual:\n%s\n' "$description" "$needle" "$haystack"
  fi
}

# run_script - invokes check-test-distribution.sh against a
# plan-file fixture, capturing stderr/exit code into
# VERDICT_ERR/VERDICT_EXIT (stdout is discarded — these tests
# assert on exit code and diagnostic presence only).
run_script() {
  local plan_file="$1"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes a fresh plan fixture under work_dir from
# its two moving parts (the Test Design body and the Task
# Breakdown body), returns its path via stdout.
#
# Both gates' regions live in one file, so every case here
# differs only in the two bodies that decide the verdict.
write_plan() {
  local name="$1" design_body="$2" task_body="$3"
  local path="$work_dir/$name.md"
  printf '# Plan: %s\n\n## Test Design\n\n%s\n\n## Task Breakdown\n\n%s\n' \
    "$name" "$design_body" "$task_body" > "$path"
  printf '%s' "$path"
}

MATCHING_DESIGN='```
// scripts/tests/test-check-test-distribution.sh
describe("checkTestDistribution", () => {
  // Happy cases
  it("should report every designed test as distributed when the two regions agree");
  // Failure scenarios
  it("should report the orphan title when a designed test reaches no task");
});
```'

it_should_pass_when_the_test_design_section_is_the_n_a_escape_with_a_reason() {
  local fixture
  fixture=$(write_plan "n-a-escape" \
    'N/A — no spec, and no executable behavior.' \
    '### 1. Rewrite the note-taking rules

**Tests (planned)**: N/A — documentation-only edit.')
  run_script "$fixture"
  assert_eq "should pass when the Test Design section is the N/A escape with a reason" "0" "$VERDICT_EXIT"
}

# Word-boundary guard: the escape is the literal "N/A", so a
# section body that merely starts with those letters is still an
# unusable Test Design.
it_should_fail_when_the_test_design_body_starts_with_n_a_x_rather_than_the_escape() {
  local fixture
  fixture=$(write_plan "n-a-x" \
    'N/Ax — a typo, not the template escape.' \
    '### 1. Rewrite the note-taking rules

**Tests (planned)**: N/A — documentation-only edit.')
  run_script "$fixture"
  assert_eq "should fail when the Test Design section body starts with N/Ax rather than the N/A escape" "1" "$VERDICT_EXIT"
}

# The escape is a CONJUNCTION, not a one-sided claim: it stands
# only when both regions agree there is nothing to test.
#
# A plan asserting "no executable behavior" in Test Design while
# a task still plans a real test is genuine drift between the
# two regions — exactly the case a one-sided escape would wave
# through.
it_should_fail_when_the_test_design_is_the_n_a_escape_but_a_task_still_plans_a_real_test() {
  local fixture
  fixture=$(write_plan "n-a-design-real-task-test" \
    'N/A — no spec, and no executable behavior.' \
    '### 1. Rewrite the note-taking rules

**Tests (planned)**: N/A — documentation-only edit.

### 2. Add the deduplication helper

**Tests (planned)**:
- "checkTestDistribution > happy > should report every designed test as distributed when the two regions agree"')
  run_script "$fixture"
  assert_eq "should fail when the Test Design section is the N/A escape but a task still plans a real test (exit code)" \
    "1" "$VERDICT_EXIT"

  # The offending title is the whole payload of this verdict —
  # without it the author cannot tell which task contradicts the
  # N/A claim.
  case "$VERDICT_ERR" in
    *"should report every designed test as distributed when the two regions agree"*)
      pass_count=$((pass_count + 1))
      printf 'ok - should name the task-planned title when the Test Design section is the N/A escape\n'
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - should name the task-planned title when the Test Design section is the N/A escape\n  actual:   %s\n' \
        "$VERDICT_ERR"
      ;;
  esac
}

# The mirror of the case above: agreement must hold in the other
# direction too, so an all-N/A task breakdown cannot silently
# drop designed tests.
it_should_fail_when_the_test_design_lists_real_titles_but_every_task_is_n_a() {
  local fixture
  fixture=$(write_plan "real-design-all-n-a-tasks" "$MATCHING_DESIGN" \
    '### 1. Wire the gate

**Tests (planned)**: N/A — documentation-only edit.

### 2. Report the diffs

**Tests (planned)**: N/A — documentation-only edit.')
  run_script "$fixture"
  assert_eq "should fail when the Test Design section lists real titles but every task is N/A (exit code)" \
    "1" "$VERDICT_EXIT"

  # Pins the REASON, not just the code: an empty set B once
  # tripped `set -eo pipefail` and killed the run with no
  # output, which reads as this same exit 1 while checking
  # nothing.
  case "$VERDICT_ERR" in
    *"should report every designed test as distributed when the two regions agree"*)
      pass_count=$((pass_count + 1))
      printf 'ok - should name the orphaned designed title when every task is N/A\n'
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - should name the orphaned designed title when every task is N/A\n  actual:   %s\n' \
        "$VERDICT_ERR"
      ;;
  esac
}

it_should_fail_when_the_plan_has_no_test_design_section_at_all() {
  local path="$work_dir/no-design-section.md"
  printf '# Plan: no design section\n\n## Task Breakdown\n\n### 1. Ship the thing\n\n**Tests (planned)**: N/A — documentation-only edit.\n' > "$path"
  run_script "$path"
  assert_eq "should fail when the plan has no Test Design section at all" "1" "$VERDICT_EXIT"
}

it_should_fail_when_the_test_design_body_is_prose_with_no_titles_and_no_escape() {
  local fixture
  fixture=$(write_plan "prose-design" \
    'We will figure out the test list once the refactor settles.' \
    '### 1. Ship the thing

**Tests (planned)**: N/A — documentation-only edit.')
  run_script "$fixture"
  assert_eq "should fail when the Test Design section has prose but no it() titles and no N/A escape" "1" "$VERDICT_EXIT"
}

it_should_pass_when_every_designed_test_appears_in_a_tasks_planned_test_list() {
  local fixture
  fixture=$(write_plan "matching" "$MATCHING_DESIGN" \
    '### 1. Wire the gate

**Tests (planned)**:
- "checkTestDistribution > happy > should report every designed test as distributed when the two regions agree"

### 2. Report the diffs

**Tests (planned)**:
- "checkTestDistribution > failure > should report the orphan title when a designed test reaches no task"')
  run_script "$fixture"
  assert_eq "should pass when every designed test appears in a task's planned-test list" "0" "$VERDICT_EXIT"
}

it_should_fail_when_a_task_lists_a_test_absent_from_the_test_design_section() {
  local fixture
  fixture=$(write_plan "invented-title" "$MATCHING_DESIGN" \
    '### 1. Wire the gate

**Tests (planned)**:
- "checkTestDistribution > happy > should report every designed test as distributed when the two regions agree"

### 2. Report the diffs

**Tests (planned)**:
- "checkTestDistribution > failure > should shout loudly when a title was never designed"')
  run_script "$fixture"
  assert_eq "should fail when a task lists a test absent from the Test Design section (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should fail when a task lists a test absent from the Test Design section (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should fail when a task lists a test absent from the Test Design section (diagnostic present)\n'
  fi
}

# Annotated-form fixture: every it() carries an inline `// T<n>` annotation
# naming the task that will write it, so there is no separate per-task
# `**Tests (planned)**:` list left for a task heading to carry.
ANNOTATED_DESIGN='```
describe("checkTestDistribution", () => {
  // Happy cases
  it("should report every designed test as distributed when the two regions agree");   // T1
  // Failure scenarios
  it("should report the orphan title when a designed test reaches no task");   // T2
});
```'

it_should_pass_in_annotated_form_when_every_it_carries_a_t_token_naming_a_real_task() {
  local fixture
  fixture=$(write_plan "annotated-matching" "$ANNOTATED_DESIGN" \
    '### 1. Wire the gate

No Tests (planned) bullet needed — the T1 annotation on the it() above already names this task.

### 2. Report the diffs

No Tests (planned) bullet needed — the T2 annotation on the it() above already names this task.')
  run_script "$fixture"
  assert_eq "should pass in annotated form when every it() carries a T<n> token naming a real task" "0" "$VERDICT_EXIT"
}

it_should_fail_in_annotated_form_when_an_it_carries_no_t_token() {
  local fixture design
  design='```
describe("checkTestDistribution", () => {
  // Happy cases
  it("should report every designed test as distributed when the two regions agree");   // T1
  // Failure scenarios
  it("should report the orphan title when a designed test reaches no task");
});
```'
  fixture=$(write_plan "annotated-missing-t" "$design" \
    '### 1. Wire the gate

### 2. Report the diffs')
  run_script "$fixture"
  assert_eq "should fail in annotated form when an it() carries no T<n> token (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should fail in annotated form when an it() carries no T<n> token (names the unassigned title)" \
    "$VERDICT_ERR" "should report the orphan title when a designed test reaches no task"
}

it_should_fail_in_annotated_form_when_a_t_token_names_a_task_the_task_breakdown_never_defines() {
  local fixture design
  design='```
describe("checkTestDistribution", () => {
  // Happy cases
  it("should report every designed test as distributed when the two regions agree");   // T1
  // Failure scenarios
  it("should report the orphan title when a designed test reaches no task");   // T9
});
```'
  fixture=$(write_plan "annotated-invented-task" "$design" \
    '### 1. Wire the gate

### 2. Report the diffs')
  run_script "$fixture"
  assert_eq "should fail in annotated form when a T<n> token names a task the Task Breakdown never defines (exit code)" \
    "1" "$VERDICT_EXIT"
  assert_contains "should fail in annotated form when a T<n> token names a task the Task Breakdown never defines (names the invented task)" \
    "$VERDICT_ERR" "T9"
}

it_should_pass_when_the_test_design_section_is_the_n_a_escape_with_a_reason
it_should_fail_when_the_test_design_is_the_n_a_escape_but_a_task_still_plans_a_real_test
it_should_fail_when_the_test_design_lists_real_titles_but_every_task_is_n_a
it_should_fail_when_the_test_design_body_starts_with_n_a_x_rather_than_the_escape
it_should_fail_when_the_plan_has_no_test_design_section_at_all
it_should_fail_when_the_test_design_body_is_prose_with_no_titles_and_no_escape
it_should_pass_when_every_designed_test_appears_in_a_tasks_planned_test_list
it_should_fail_when_a_task_lists_a_test_absent_from_the_test_design_section
it_should_pass_in_annotated_form_when_every_it_carries_a_t_token_naming_a_real_task
it_should_fail_in_annotated_form_when_an_it_carries_no_t_token
it_should_fail_in_annotated_form_when_a_t_token_names_a_task_the_task_breakdown_never_defines

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
