#!/usr/bin/env bash
# test-parse-pr-breakdown.sh - plain-bash test file for parse-pr-breakdown.sh.
#
# Usage:
#   bash test-parse-pr-breakdown.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/parse-pr-breakdown.sh"

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

# run_script - invokes parse-pr-breakdown.sh against a plan-file fixture,
# capturing stdout/exit code into VERDICT_OUT/VERDICT_EXIT (stderr is
# discarded to a file, not a variable - no assertion below needs it, since
# parse-pr-breakdown.sh's exit-1 trivial-section path prints no diagnostic
# by design, leaving that message to each caller's own $pr_label context).
run_script() {
  local plan_file="$1"
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

# write_plan - writes the given PR-Breakdown-section body to a fresh plan
# fixture under work_dir, returns its path via stdout.
write_plan() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## PR Breakdown\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_emit_one_tsv_line_per_pr_n_entry_for_a_normal_multi_pr_plan() {
  local fixture
  fixture=$(write_plan "happy-multi-pr" '1. **PR-1** — Naming and validators. Tasks: 1, 2, 3. Depends on: none.
2. **PR-2** — Worktree hygiene. Tasks: 4. Depends on: none.
3. **PR-3** — Core loop. Tasks: 5, 6, 7. Depends on: PR-1, PR-2.')
  run_script "$fixture"
  assert_eq "should emit one TSV line per PR-N entry for a normal multi-PR plan (exit code)" "0" "$VERDICT_EXIT"
  local expected
  expected=$(printf 'PR-1\t1, 2, 3\t\nPR-2\t4\t\nPR-3\t5, 6, 7\tPR-1,PR-2')
  assert_eq "should emit one TSV line per PR-N entry for a normal multi-PR plan (TSV body)" "$expected" "$VERDICT_OUT"
}

it_should_report_nothing_to_parse_for_a_single_pr_plan() {
  local path="$work_dir/single-pr.md"
  printf '## PR Breakdown\n\nSingle PR.\n' > "$path"
  run_script "$path"
  assert_eq "should report nothing to parse for a Single PR. plan (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should report nothing to parse for a Single PR. plan (no stdout)" "" "$VERDICT_OUT"
}

it_should_emit_an_empty_deps_field_for_a_pr_with_no_dependencies() {
  local fixture
  fixture=$(write_plan "corner-no-deps" '1. **PR-1** — Naming and validators. Tasks: 1. Depends on: none.')
  run_script "$fixture"
  assert_eq "should emit an empty deps field for a PR with no dependencies (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should emit an empty deps field for a PR with no dependencies (TSV body)" "$(printf 'PR-1\t1\t')" "$VERDICT_OUT"
}

it_should_emit_every_dependency_for_a_pr_with_a_diamond_dependency() {
  local fixture
  fixture=$(write_plan "corner-diamond" '1. **PR-1** — First slice. Tasks: 1. Depends on: none.
2. **PR-2** — Second slice. Tasks: 2. Depends on: none.
3. **PR-3** — Diamond merge. Tasks: 3. Depends on: PR-1, PR-2.')
  run_script "$fixture"
  assert_eq "should emit every dependency for a PR with a diamond dependency (exit code)" "0" "$VERDICT_EXIT"
  local diamond_line
  diamond_line=$(printf '%s\n' "$VERDICT_OUT" | awk -F'\t' '$1 == "PR-3" { print; exit }')
  assert_eq "should emit every dependency for a PR with a diamond dependency (deps field)" "PR-3	3	PR-1,PR-2" "$diamond_line"
}

it_should_emit_one_tsv_line_per_pr_n_entry_for_a_normal_multi_pr_plan
it_should_report_nothing_to_parse_for_a_single_pr_plan
it_should_emit_an_empty_deps_field_for_a_pr_with_no_dependencies
it_should_emit_every_dependency_for_a_pr_with_a_diamond_dependency

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
