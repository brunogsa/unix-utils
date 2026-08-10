#!/usr/bin/env bash
# run-tests.sh - Run every bash test suite in this repo.
#
# Usage:
#   ./run-tests.sh
#
# Exit codes:
#   0 - every suite passed
#   1 - at least one suite failed
#
# The python suites are NOT run here. The repo-root
# pytest.ini already collects all of them from one
# `pytest` invocation, so a second entry point would
# only add a PATH dependency on an already-working one.
#
# Why this exists:
#   Four separate bash test trees had nothing
#   enumerating them, so a suite ran only when someone
#   remembered it by name.
#
#   The hooks tree was the sharpest case: ten gate
#   suites, zero callers, so a regression in any Stop
#   hook would have shipped silently.
#
# Discovery is by glob, never by an enumerated list:
#   a runner that needs each new suite registered
#   reproduces the exact failure it exists to fix.
#
# Every suite runs even after one fails, because a
# runner that stops at the first failure hides the
# other 36.

set -uo pipefail

# Anchored on this script's own directory, not the
# caller's, so the globs below resolve the same from
# any subdirectory.
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$repo_root" || exit 1

log_dir=$(mktemp -d)
trap 'rm -rf "$log_dir"' EXIT

pass_count=0
fail_count=0
failed_suites=()
failed_logs=()
suite_index=0

for suite in \
  configs/ai-docs/claude/tests/test-*.sh \
  configs/ai-docs/claude/scripts/tests/test-*.sh \
  configs/ai-docs/claude/hooks/tests/test-*.sh \
  configs/ai-docs/claude/skills/*/scripts/tests/test-*.sh
do
  [ -f "$suite" ] || continue

  # Named by index, not by the suite path: two trees
  # can hold a suite of the same name, and flattening
  # the path would collide their logs.
  suite_index=$((suite_index + 1))
  log_file="$log_dir/$suite_index.log"

  if bash "$suite" > "$log_file" 2>&1; then
    pass_count=$((pass_count + 1))
    printf 'PASS  %s\n' "$suite"
  else
    fail_count=$((fail_count + 1))
    failed_suites+=("$suite")
    failed_logs+=("$log_file")
    printf 'FAIL  %s\n' "$suite"
  fi
done

# A bare FAIL line names the suite but not the
# assertion, forcing a second run by hand to learn
# what broke. Replaying each failing log closes that.
#
# The count guards the loop because macOS ships bash
# 3.2, where expanding an empty array under `set -u`
# aborts the script.
if [ "$fail_count" -gt 0 ]; then
  for i in "${!failed_suites[@]}"; do
    printf '\n===== %s =====\n' "${failed_suites[$i]}"
    cat "${failed_logs[$i]}"
  done
fi

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
