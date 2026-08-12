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

# pwd -P resolves /var -> /private/var on macOS. changed-lines.sh anchors on
# `git rev-parse --show-toplevel`, always physical, so an unresolved work_dir
# would make its relative-path comparison miss - same caveat as
# test-changed-lines.sh.
work_dir=$(cd "$(mktemp -d)" && pwd -P)
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

# new_repo - creates an empty git repo under work_dir and prints its path.
# Identity is set locally so the fixture commit never depends on the
# machine's global git config. Mirrors test-changed-lines.sh's helper,
# since --changed-only's whole contract is "what does changed-lines.sh
# report" - there is nothing to assert without a real repo underneath it.
new_repo() {
  local dir="$work_dir/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q .
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
  printf '%s' "$dir"
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

# --- --changed-only cases ---
#
# Every fixture below shares one violation shape: a parent bullet with a
# nested child right below it, followed by a sibling bullet flush against
# the child (no gap) - the same sub-bullet hit the two tests above already
# exercise, just placed inside a real git repo so changed-lines.sh has
# something to diff against.

it_should_hide_a_pre_existing_violation_and_still_report_a_newly_added_one_under_changed_only() {
  local repo
  repo=$(new_repo mixed-scope-check)

  local parent_a='- Parent A with a nested child right below it.'
  local child_a='  - Child A sub-bullet, one level deeper.'
  local sibling_a='- Sibling A flush against the child above (no gap).'
  local parent_b='- Parent B with a nested child right below it.'
  local child_b='  - Child B sub-bullet, one level deeper.'
  local sibling_b='- Sibling B flush against the child above (no gap).'

  printf '%s\n%s\n%s\n' "$parent_a" "$child_a" "$sibling_a" > "$repo/mixed.md"
  git -C "$repo" add mixed.md
  git -C "$repo" commit -q -m base

  # Section A is untouched (still identical to HEAD) - its sub-bullet hit
  # predates this session's edit. Section B is newly appended - its
  # sub-bullet hit is the only one this session's diff actually created.
  printf '%s\n%s\n%s\n%s\n%s\n%s\n' \
    "$parent_a" "$child_a" "$sibling_a" "$parent_b" "$child_b" "$sibling_b" \
    > "$repo/mixed.md"

  local out rc
  out=$(cd "$repo" && python3 "$SCRIPT" --changed-only mixed.md 2>&1)
  rc=$?

  assert_eq 'should report only the newly added sub-bullet hit under --changed-only, not the pre-existing one' \
    "$(printf '== mixed.md\n5:sub-bullet')" "$out"
  assert_eq 'should exit 1 under --changed-only when one in-scope violation remains' '1' "$rc"
}

it_should_leave_a_pre_existing_violation_untouched_and_fix_only_the_newly_added_one_under_changed_only() {
  local repo
  repo=$(new_repo mixed-scope-fix)

  local parent_a='- Parent A with a nested child right below it.'
  local child_a='  - Child A sub-bullet, one level deeper.'
  local sibling_a='- Sibling A flush against the child above (no gap).'
  local parent_b='- Parent B with a nested child right below it.'
  local child_b='  - Child B sub-bullet, one level deeper.'
  local sibling_b='- Sibling B flush against the child above (no gap).'

  printf '%s\n%s\n%s\n' "$parent_a" "$child_a" "$sibling_a" > "$repo/mixed.md"
  git -C "$repo" add mixed.md
  git -C "$repo" commit -q -m base

  printf '%s\n%s\n%s\n%s\n%s\n%s\n' \
    "$parent_a" "$child_a" "$sibling_a" "$parent_b" "$child_b" "$sibling_b" \
    > "$repo/mixed.md"

  local rc
  (cd "$repo" && python3 "$SCRIPT" --fix --changed-only mixed.md) \
    >"$work_dir/mixed-scope-fix-stdout.txt" 2>&1
  rc=$?

  local expected
  expected=$(printf '%s\n%s\n%s\n%s\n%s\n\n%s' \
    "$parent_a" "$child_a" "$sibling_a" "$parent_b" "$child_b" "$sibling_b")
  assert_eq 'should insert a blank line only after the newly added sub-bullet hit, leaving the pre-existing one untouched' \
    "$expected" "$(cat "$repo/mixed.md")"
  assert_eq 'should exit 0 after --fix --changed-only fixes every in-scope violation (the pre-existing one stays out of scope)' \
    '0' "$rc"
}

it_should_report_no_violations_under_changed_only_for_a_tracked_unmodified_file() {
  local repo
  repo=$(new_repo unmodified-scope)

  printf '%s\n%s\n%s\n' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).' \
    > "$repo/unmodified.md"
  git -C "$repo" add unmodified.md
  git -C "$repo" commit -q -m base

  local before out rc
  before="$(cat "$repo/unmodified.md")"

  out=$(cd "$repo" && python3 "$SCRIPT" --changed-only unmodified.md 2>&1)
  rc=$?
  assert_eq 'should print nothing under --changed-only for a tracked, unmodified file with a pre-existing violation' \
    '' "$out"
  assert_eq 'should exit 0 under --changed-only for a tracked, unmodified file (no lines in scope)' '0' "$rc"

  (cd "$repo" && python3 "$SCRIPT" --fix --changed-only unmodified.md) \
    >"$work_dir/unmodified-fix-stdout.txt" 2>&1
  rc=$?
  assert_eq 'should leave a tracked, unmodified file byte-identical under --fix --changed-only (nothing in scope)' \
    "$before" "$(cat "$repo/unmodified.md")"
  assert_eq 'should exit 0 after --fix --changed-only on a tracked, unmodified file' '0' "$rc"
}

it_should_fix_every_hit_in_an_untracked_file_under_changed_only_same_as_a_full_scan() {
  local repo
  repo=$(new_repo untracked-scope)
  git -C "$repo" commit -q --allow-empty -m base

  printf '%s\n%s\n%s\n' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).' \
    > "$repo/untracked.md"

  local rc
  (cd "$repo" && python3 "$SCRIPT" --fix --changed-only untracked.md) \
    >"$work_dir/untracked-fix-stdout.txt" 2>&1
  rc=$?

  local expected
  expected=$(printf '%s\n%s\n\n%s' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).')
  assert_eq 'should insert a blank line after the hit in a never-added file under --changed-only, same as a full scan' \
    "$expected" "$(cat "$repo/untracked.md")"
  assert_eq 'should exit 0 for an untracked file after --fix --changed-only fixes its only hit' '0' "$rc"

  local check_rc
  (cd "$repo" && python3 "$SCRIPT" --changed-only untracked.md) \
    >"$work_dir/untracked-check-stdout.txt" 2>&1
  check_rc=$?
  assert_eq 'should pass the plain check after --fix --changed-only fixed the untracked file`s only hit' '0' "$check_rc"
}

it_should_exit_2_when_changed_lines_sh_fails_outside_a_git_work_tree_in_check_mode() {
  local plain_dir="$work_dir/plain-check"
  mkdir -p "$plain_dir"
  printf '%s\n%s\n%s\n' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).' \
    > "$plain_dir/plain.md"

  local err rc
  err=$(cd "$plain_dir" && python3 "$SCRIPT" --changed-only plain.md 2>&1 1>/dev/null)
  rc=$?
  assert_eq 'should exit 2 in check mode when changed-lines.sh fails outside a git work tree' '2' "$rc"
  assert_eq 'should name the file in stderr when changed-lines.sh fails (check mode)' \
    'changed-lines.sh failed for plain.md: changed-lines.sh: not inside a git work tree' "$err"
}

it_should_exit_2_when_changed_lines_sh_fails_outside_a_git_work_tree_in_fix_mode() {
  local plain_dir="$work_dir/plain-fix"
  mkdir -p "$plain_dir"
  printf '%s\n%s\n%s\n' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).' \
    > "$plain_dir/plain.md"

  local before err rc
  before="$(cat "$plain_dir/plain.md")"
  err=$(cd "$plain_dir" && python3 "$SCRIPT" --fix --changed-only plain.md 2>&1 1>/dev/null)
  rc=$?
  assert_eq 'should exit 2 in --fix mode when changed-lines.sh fails outside a git work tree' '2' "$rc"
  assert_eq 'should name the file in stderr when changed-lines.sh fails (--fix mode)' \
    'changed-lines.sh failed for plain.md: changed-lines.sh: not inside a git work tree' "$err"
  assert_eq 'should never insert into the file when changed-lines.sh fails (no fake fix on error)' \
    "$before" "$(cat "$plain_dir/plain.md")"
}

it_should_apply_changed_only_independently_per_file_when_given_multiple_files() {
  local repo
  repo=$(new_repo multi-file-scope)

  printf '%s\n%s\n%s\n' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).' \
    > "$repo/tracked.md"
  git -C "$repo" add tracked.md
  git -C "$repo" commit -q -m base

  printf '%s\n%s\n%s\n' \
    '- Parent bullet with a nested child right below it.' \
    '  - Child sub-bullet, one level deeper.' \
    '- Sibling bullet flush against the child above (no gap).' \
    > "$repo/untracked.md"

  local out rc
  out=$(cd "$repo" && python3 "$SCRIPT" --changed-only tracked.md untracked.md 2>&1)
  rc=$?

  assert_eq 'should report only the untracked file`s hit when --changed-only is given both an unmodified tracked file and an untracked file' \
    "$(printf '== untracked.md\n2:sub-bullet')" "$out"
  assert_eq 'should exit 1 (one in-scope violation, from the untracked file only)' '1' "$rc"
}

it_should_insert_a_blank_line_after_a_sub_bullet_hit_and_pass_the_check_afterward
it_should_insert_a_blank_line_after_an_over_80pct_hit_and_pass_the_check_afterward
it_should_leave_the_file_byte_identical_when_fix_flag_is_omitted
it_should_exit_2_when_given_a_missing_file
it_should_exit_2_when_given_an_unknown_flag
it_should_hide_a_pre_existing_violation_and_still_report_a_newly_added_one_under_changed_only
it_should_leave_a_pre_existing_violation_untouched_and_fix_only_the_newly_added_one_under_changed_only
it_should_report_no_violations_under_changed_only_for_a_tracked_unmodified_file
it_should_fix_every_hit_in_an_untracked_file_under_changed_only_same_as_a_full_scan
it_should_exit_2_when_changed_lines_sh_fails_outside_a_git_work_tree_in_check_mode
it_should_exit_2_when_changed_lines_sh_fails_outside_a_git_work_tree_in_fix_mode
it_should_apply_changed_only_independently_per_file_when_given_multiple_files

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
