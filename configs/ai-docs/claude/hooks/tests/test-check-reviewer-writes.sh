#!/usr/bin/env bash
# Plain-bash test file for check-reviewer-writes.sh.
#
# Usage:
#   bash test-check-reviewer-writes.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-reviewer-writes.sh"

pass_count=0
fail_count=0

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

# run_hook - feeds a Write payload for one path; prints
# the exit code and whether the output auto-approves.
run_hook() {
  local path="$1" output code
  output=$(printf '{"tool_input":{"file_path":"%s"}}' "$path" | bash "$SCRIPT" 2>/dev/null)
  code=$?
  if [[ "$output" == *'"permissionDecision":"allow"'* ]]; then
    printf '%s allow' "$code"
  else
    printf '%s no-allow' "$code"
  fi
}

assert_eq "allows the inferred layer map written to the working directory" \
  "0 allow" "$(run_hook "/work/repo/layers_inferred_2026-11-16_01-19.yaml")"

assert_eq "still allows a verdict markdown file" \
  "0 allow" "$(run_hook "/work/repo/verdict_metrics_2026-11-16_01-19.md")"

assert_eq "still allows scratch under /tmp" \
  "0 allow" "$(run_hook "/tmp/auto-review.abc123/wave2.json")"

assert_eq "blocks an unrelated yaml name in the working directory" \
  "2 no-allow" "$(run_hook "/work/repo/config.yaml")"

assert_eq "blocks a layers_inferred name with a non-yaml extension" \
  "2 no-allow" "$(run_hook "/work/repo/layers_inferred_2026-11-16.sh")"

assert_eq "blocks a write whose path is missing" \
  "2 no-allow" "$(run_hook "")"

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
