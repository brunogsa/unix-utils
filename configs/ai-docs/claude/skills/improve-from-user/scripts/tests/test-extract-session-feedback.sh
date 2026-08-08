#!/usr/bin/env bash
# test-extract-session-feedback.sh - plain-bash test file
# for extract-session-feedback.py.
#
# Usage:
#   bash test-extract-session-feedback.sh
#
# Exits 0 when every assertion passes, nonzero otherwise.
# No pytest dependency, matching this skill's other test
# files.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/extract-session-feedback.py"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
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

# run_script - invokes extract-session-feedback.py with the
# given args, capturing stdout/stderr/exit code into
# VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  python3 "$SCRIPT" "$@" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

it_should_reject_the_removed_session_id_project_dir_and_cwd_flags_with_a_nonzero_exit() {
  run_script --session-id fake-session --project-dir /nonexistent --cwd /nonexistent

  # Both must hold: a nonzero exit alone doesn't prove
  # argparse rejected the flags (the old resolve_transcript()
  # also failed nonzero, for a different reason), so this is
  # one behavior, asserted once.
  local rejected_via_argparse="false"
  if [ "$VERDICT_EXIT" -ne 0 ] && [[ "$VERDICT_ERR" == *"unrecognized arguments"* ]]; then
    rejected_via_argparse="true"
  fi
  assert_eq \
    "ExtractSessionFeedbackSweep > failure > should reject the removed --session-id, --project-dir, and --cwd flags with a nonzero exit" \
    "true" "$rejected_via_argparse"
}

it_should_reject_the_removed_session_id_project_dir_and_cwd_flags_with_a_nonzero_exit

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
