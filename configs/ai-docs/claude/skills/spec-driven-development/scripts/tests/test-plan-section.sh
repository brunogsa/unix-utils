#!/usr/bin/env bash
# test-plan-section.sh - plain-bash test file for plan-section.sh.
#
# Usage:
#   bash test-plan-section.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/plan-section.sh"

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

# run_script - invokes plan-section.sh, capturing stdout/exit code into
# VERDICT_OUT/VERDICT_EXIT.
run_script() {
  local out_file="$work_dir/stdout.txt"
  VERDICT_EXIT=0
  bash "$SCRIPT" "$@" >"$out_file" 2>/dev/null || VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

it_should_print_only_the_matched_section_body_excluding_the_heading_line() {
  local path="$work_dir/exact-match.md"
  printf '## PR Breakdown\n\nSingle PR.\n\n## Next Section\n\nunrelated\n' > "$path"
  run_script "$path" "##" '^PR Breakdown[[:space:]]*$'
  assert_eq "should print only the matched section body, excluding the heading line" \
    "$(printf '\nSingle PR.\n')" "$VERDICT_OUT"
}

it_should_stop_at_the_next_same_level_heading_and_exit_0() {
  local path="$work_dir/same-level-boundary.md"
  printf '## Task Breakdown\n\nbody line\n\n## Another Section\n\nnot included\n' > "$path"
  run_script "$path" "##" '^Task Breakdown[[:space:]]*$'
  assert_eq "should stop at the next same-level heading (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should stop at the next same-level heading (body excludes the next section)" \
    "$(printf '\nbody line\n')" "$VERDICT_OUT"
}

it_should_not_end_the_section_at_a_deeper_subheading() {
  local path="$work_dir/deeper-subheading.md"
  printf '## Task Breakdown\n\n### 1. First task\n\n**Depends on**: none\n\n## Next Section\n\nnot included\n' > "$path"
  run_script "$path" "##" '^Task Breakdown[[:space:]]*$'
  assert_eq "should not end the section at a deeper (###) subheading" \
    "$(printf '\n### 1. First task\n\n**Depends on**: none\n')" "$VERDICT_OUT"
}

it_should_print_empty_stdout_and_exit_0_when_no_heading_matches() {
  local path="$work_dir/no-match.md"
  printf '## Some Other Section\n\nbody\n' > "$path"
  run_script "$path" "##" '^PR Breakdown[[:space:]]*$'
  assert_eq "should exit 0 when no heading matches" "0" "$VERDICT_EXIT"
  assert_eq "should print empty stdout when no heading matches" "" "$VERDICT_OUT"
}

it_should_support_a_prefix_match_for_a_dynamic_heading_without_matching_a_longer_number() {
  local path="$work_dir/prefix-match.md"
  printf '### 3. New third task\n\nthird body\n\n### 30. Thirtieth task\n\nthirtieth body\n' > "$path"
  run_script "$path" "###" '^3[.]'
  assert_eq "should match task 3 via a bracket-expression dot, not task 30 (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should match task 3's body only, not leak task 30's body (regression guard for the awk -v backslash-escape hazard)" \
    "$(printf '\nthird body\n')" "$VERDICT_OUT"
}

it_should_exit_2_on_wrong_arg_count() {
  run_script "one-arg-only"
  assert_eq "should exit 2 on wrong arg count" "2" "$VERDICT_EXIT"
}

it_should_exit_2_when_the_plan_file_is_missing() {
  run_script "$work_dir/does-not-exist.md" "##" '^PR Breakdown[[:space:]]*$'
  assert_eq "should exit 2 when the plan file is missing" "2" "$VERDICT_EXIT"
}

it_should_print_only_the_matched_section_body_excluding_the_heading_line
it_should_stop_at_the_next_same_level_heading_and_exit_0
it_should_not_end_the_section_at_a_deeper_subheading
it_should_print_empty_stdout_and_exit_0_when_no_heading_matches
it_should_support_a_prefix_match_for_a_dynamic_heading_without_matching_a_longer_number
it_should_exit_2_on_wrong_arg_count
it_should_exit_2_when_the_plan_file_is_missing

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
