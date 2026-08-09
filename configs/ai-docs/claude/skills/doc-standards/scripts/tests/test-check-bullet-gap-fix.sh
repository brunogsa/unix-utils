#!/usr/bin/env bash
# test-check-bullet-gap-fix.sh - plain-bash test file for
# check-bullet-gap.py's --fix flag.
#
# Usage:
#   bash test-check-bullet-gap-fix.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design, matching this skill area's other test suites
# (test-check-rule-citations.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-bullet-gap.py"

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

# new_fixture - writes $2 into a fresh tmp file, sets FIXTURE to its path.
new_fixture() {
  local name="$1" content="$2"
  FIXTURE="$work_dir/$name"
  printf '%s' "$content" > "$FIXTURE"
}

# run_fix - invokes check-bullet-gap.py --fix on FIXTURE, capturing the
# exit code into FIX_EXIT.
run_fix() {
  python3 "$SCRIPT" --fix "$FIXTURE" >"$work_dir/fix-stdout.txt" 2>&1
  FIX_EXIT=$?
}

# run_check - invokes check-bullet-gap.py (no --fix) on FIXTURE, capturing
# the exit code into CHECK_EXIT.
run_check() {
  python3 "$SCRIPT" "$FIXTURE" >"$work_dir/check-stdout.txt" 2>&1
  CHECK_EXIT=$?
}

it_should_insert_a_blank_line_after_a_sub_bullet_hit_and_pass_the_check_afterward() {
  new_fixture sub-bullet.md "$(cat <<'EOF'
- Parent bullet with a nested child right below it.
  - Child sub-bullet, one level deeper.
- Sibling bullet flush against the child above (no gap).
EOF
)"
  run_fix
  assert_eq 'should insert a blank line after a sub-bullet hit (fix exit code)' "0" "$FIX_EXIT"

  local expected
  expected="$(cat <<'EOF'
- Parent bullet with a nested child right below it.
  - Child sub-bullet, one level deeper.

- Sibling bullet flush against the child above (no gap).
EOF
)"
  assert_eq 'should insert a blank line after a sub-bullet hit (file content)' "$expected" "$(cat "$FIXTURE")"

  run_check
  assert_eq 'should insert a blank line after a sub-bullet hit (file then passes the plain check)' "0" "$CHECK_EXIT"
}

it_should_insert_a_blank_line_after_an_over_80pct_hit_and_pass_the_check_afterward() {
  # 210 chars, over the 205-char gap threshold (80% of 256), under the
  # full 256-char density cap so check-density.sh itself stays quiet.
  local long_bullet="- This bullet is deliberately long enough to cross the eighty percent gap threshold used by check-bullet-gap.py, comfortably under the two-hundred-fifty-six character density cap check-density.sh enforces separately."
  new_fixture over-80pct.md "$(printf '%s\n- Sibling bullet flush against the long one above (no gap).\n' "$long_bullet")"

  run_fix
  assert_eq 'should insert a blank line after an over-80pct hit (fix exit code)' "0" "$FIX_EXIT"

  local expected
  expected="$(printf '%s\n\n- Sibling bullet flush against the long one above (no gap).\n' "$long_bullet")"
  assert_eq 'should insert a blank line after an over-80pct hit (file content)' "$expected" "$(cat "$FIXTURE")"

  run_check
  assert_eq 'should insert a blank line after an over-80pct hit (file then passes the plain check)' "0" "$CHECK_EXIT"
}

it_should_leave_the_file_byte_identical_when_fix_flag_is_omitted() {
  new_fixture no-fix.md "$(cat <<'EOF'
- Parent bullet with a nested child right below it.
  - Child sub-bullet, one level deeper.
- Sibling bullet flush against the child above (no gap).
EOF
)"
  local before
  before="$(cat "$FIXTURE")"
  run_check
  assert_eq 'should leave the file byte-identical when --fix is omitted (exit code still reports the violation)' "1" "$CHECK_EXIT"
  assert_eq 'should leave the file byte-identical when --fix is omitted (file content)' "$before" "$(cat "$FIXTURE")"
}

it_should_exit_2_when_given_a_missing_file() {
  FIXTURE="$work_dir/does-not-exist.md"
  run_fix
  assert_eq 'should exit 2 when --fix is given a missing file' "2" "$FIX_EXIT"
}

it_should_exit_2_when_given_an_unknown_flag() {
  new_fixture unknown-flag.md '- A single bullet.'
  python3 "$SCRIPT" --nope "$FIXTURE" >"$work_dir/unknown-stdout.txt" 2>&1
  assert_eq 'should exit 2 when given an unknown flag' "2" "$?"
}

it_should_insert_a_blank_line_after_a_sub_bullet_hit_and_pass_the_check_afterward
it_should_insert_a_blank_line_after_an_over_80pct_hit_and_pass_the_check_afterward
it_should_leave_the_file_byte_identical_when_fix_flag_is_omitted
it_should_exit_2_when_given_a_missing_file
it_should_exit_2_when_given_an_unknown_flag

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
