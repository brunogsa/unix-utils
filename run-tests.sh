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
# The repo-root pytest.ini's suites run here too, as one
# more entry alongside the bash suites below.
#
# A prior version left pytest out and pointed at running
# it separately — but nothing enforced that second
# command, so this script's own exit code silently lied
# about whether the repo was actually green.
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

# record_pass/record_fail - shared by the bash-suite loop below
# and the pytest step after it, so both report through the same
# counters, PASS/FAIL line, and failure-replay list rather than
# two near-identical bookkeeping blocks drifting apart.
record_pass() {
  pass_count=$((pass_count + 1))
  printf 'PASS  %s\n' "$1"
}

record_fail() {
  fail_count=$((fail_count + 1))
  failed_suites+=("$1")
  failed_logs+=("$2")
  printf 'FAIL  %s\n' "$1"
}

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
    record_pass "$suite"
  else
    record_fail "$suite" "$log_file"
  fi
done

# pytest.ini at the repo root collects every python suite
# from one bare `pytest` invocation, so it runs here as one
# more suite through the same record_pass/record_fail path.
#
# The python failures replay below exactly like a bash
# suite's would.
#
# A missing pytest binary fails loudly instead of silently
# reading as green: skipping it here would recreate the same gap
# this fold-in exists to close, just moved from "forgot to run
# pytest" to "pytest wasn't on PATH".
suite_index=$((suite_index + 1))
log_file="$log_dir/$suite_index.log"

if ! command -v pytest > /dev/null 2>&1; then
  printf 'pytest: command not found\n' > "$log_file"
  record_fail "pytest" "$log_file"
elif pytest > "$log_file" 2>&1; then
  record_pass "pytest"
else
  record_fail "pytest" "$log_file"
fi

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
