#!/usr/bin/env bash
# test-check-files-union.sh - plain-bash test file for
# check-files-union.sh.
#
# Usage:
#   bash test-check-files-union.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-files-union.sh"

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

# assert_contains - inline assert helper: checks that a
# captured stream carries an expected substring.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
  fi
}

# run_script - invokes check-files-union.sh against a plan
# fixture, capturing stderr/exit code into
# VERDICT_ERR/VERDICT_EXIT (stdout is discarded).
run_script() {
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$@" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes a plan fixture with the given Task
# Details body and files-union body, returns its path.
write_plan() {
  local name="$1" details="$2" union="$3"
  local path="$work_dir/$name.md"
  printf '## Task Details\n\n%s\n\n## Files to Create or Modify\n\n%s\n\n## Next Section\n\n- `not/in/union.txt`\n' \
    "$details" "$union" > "$path"
  printf '%s' "$path"
}

it_should_exit_non_zero_and_name_each_missing_path_when_a_per_task_files_entry_is_absent_from_the_files_union() {
  local fixture
  fixture=$(write_plan "missing" '### 1. First

**Files (logical order)**:
- `a/one.sh`
- `a/missing-one.sh`

### 2. Second

**Files (logical order)**:
- `b/two.sh`
- `b/missing-two.sh`' '- `a/one.sh`
- `b/two.sh`')
  run_script "$fixture"
  assert_eq "exits 1 when entries are missing from the union" "1" "$VERDICT_EXIT"
  assert_contains "names the first missing path" "a/missing-one.sh" "$VERDICT_ERR"
  assert_contains "names the second missing path" "b/missing-two.sh" "$VERDICT_ERR"
}

it_should_exit_zero_when_every_per_task_files_entry_is_in_the_files_union() {
  local fixture
  fixture=$(write_plan "happy" '### 1. First

**Files (logical order)**:
- `a/one.sh`
- N/A — nothing else

### 2. Second

**Files (logical order)**:
- `a/one.sh`
- `b/two.sh`' '<details>

- `a/one.sh`
- `b/two.sh` (edited, then deleted)

</details>')
  run_script "$fixture"
  assert_eq "exits 0 when every entry is in the union" "0" "$VERDICT_EXIT"
}

it_should_exit_two_when_the_plan_file_is_missing_or_arg_count_is_wrong() {
  run_script
  assert_eq "exits 2 with no argument" "2" "$VERDICT_EXIT"
  run_script "$work_dir/nope.md"
  assert_eq "exits 2 for a missing plan file" "2" "$VERDICT_EXIT"
}

it_should_exit_two_when_the_plan_has_no_task_details_section() {
  local path="$work_dir/nodetails.md"
  printf '## Files to Create or Modify\n\n- `a/one.sh`\n' > "$path"
  run_script "$path"
  assert_eq "exits 2 with no Task Details section" "2" "$VERDICT_EXIT"
}

it_should_exit_two_when_the_plan_has_no_files_union_section() {
  local path="$work_dir/nounion.md"
  printf '## Task Details\n\n**Files (logical order)**:\n- `a/one.sh`\n' > "$path"
  run_script "$path"
  assert_eq "exits 2 with no files union section" "2" "$VERDICT_EXIT"
}

it_should_exit_zero_when_the_files_union_entry_is_not_the_first_bullet_token() {
  local fixture
  fixture=$(write_plan "suffix" '### 1. First

**Files (logical order)**:
- `a/one.sh` (new)' '- `a/one.sh`')
  run_script "$fixture"
  assert_eq "annotation after the path is ignored" "0" "$VERDICT_EXIT"
}

it_should_exit_zero_when_the_only_entry_is_an_na_line() {
  local fixture
  fixture=$(write_plan "na" '### 1. First

**Files (logical order)**:
- N/A — `/tmp`-scoped, no source files' '- `a/one.sh`')
  run_script "$fixture"
  assert_eq "an N/A entry names no path" "0" "$VERDICT_EXIT"
}

it_should_exit_zero_when_the_only_entry_is_an_na_line
it_should_exit_zero_when_the_files_union_entry_is_not_the_first_bullet_token
it_should_exit_two_when_the_plan_has_no_files_union_section
it_should_exit_two_when_the_plan_has_no_task_details_section
it_should_exit_two_when_the_plan_file_is_missing_or_arg_count_is_wrong
it_should_exit_zero_when_every_per_task_files_entry_is_in_the_files_union
it_should_exit_non_zero_and_name_each_missing_path_when_a_per_task_files_entry_is_absent_from_the_files_union

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
