#!/usr/bin/env bash
# test-check-pr-dag.sh - plain-bash test file for check-pr-dag.sh.
#
# Usage:
#   bash test-check-pr-dag.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-pr-dag.sh"

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

# run_script - invokes check-pr-dag.sh against a plan-file fixture, capturing
# stderr/exit code into VERDICT_ERR/VERDICT_EXIT (stdout is discarded — these
# tests assert on exit code and diagnostic presence only).
run_script() {
  local plan_file="$1"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$plan_file" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes the given PR-Breakdown-section body to a fresh plan
# fixture under work_dir, returns its path via stdout.
write_plan() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## PR Breakdown\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_pass_when_every_pr_dependency_resolves_to_a_real_non_cyclic_pr_label() {
  local fixture
  fixture=$(write_plan "happy-resolves" '1. **PR-1** — Naming and validators. Tasks: 1, 2, 3. Depends on: none.
2. **PR-2** — Worktree hygiene. Tasks: 4. Depends on: none.
3. **PR-3** — Core loop. Tasks: 5, 6. Depends on: PR-1, PR-2.
4. **PR-4** — Diamond merge. Tasks: 7. Depends on: PR-3.')
  run_script "$fixture"
  assert_eq "should pass when every PR dependency resolves to a real, non-cyclic PR label" "0" "$VERDICT_EXIT"
}

it_should_pass_when_the_plan_reads_single_pr_nothing_to_validate() {
  local path="$work_dir/single-pr.md"
  printf '## PR Breakdown\n\nSingle PR.\n' > "$path"
  run_script "$path"
  assert_eq "should pass when the plan reads Single PR. (nothing to validate)" "0" "$VERDICT_EXIT"
}

it_should_pass_when_every_pr_is_independent_no_depends_on_entries() {
  local fixture
  fixture=$(write_plan "independent" '1. **PR-1** — First slice. Tasks: 1. Depends on: none.
2. **PR-2** — Second slice. Tasks: 2. Depends on: none.
3. **PR-3** — Third slice. Tasks: 3. Depends on: none.')
  run_script "$fixture"
  assert_eq "should pass when every PR is independent (no Depends on entries)" "0" "$VERDICT_EXIT"
}

it_should_pass_when_the_plan_reads_the_n_a_escape_for_a_no_pr_repo() {
  local path="$work_dir/n-a-escape.md"
  printf '## PR Breakdown\n\nN/A — sole-maintainer repo commits directly to master, no PR is opened.\n' > "$path"
  run_script "$path"
  assert_eq "should pass when the plan reads the N/A — <reason> escape for a no-PR repo" "0" "$VERDICT_EXIT"
}

# plan-template.md tells authors to write "N/A — no PR dependencies" in
# place of the dependency diagram, which leads the numbered PR list. The
# escape must not disarm validation of the entries that follow it.
it_should_still_validate_pr_entries_that_follow_the_n_a_in_place_of_the_diagram() {
  local fixture
  fixture=$(write_plan "n-a-then-cycle" 'N/A — no PR dependencies

1. **PR-1** — First. Tasks: 1. Depends on: PR-2.
2. **PR-2** — Second. Tasks: 2. Depends on: PR-1.')
  run_script "$fixture"
  assert_eq "should still validate PR entries that follow an N/A written in place of the diagram" "1" "$VERDICT_EXIT"
}

it_should_fail_when_the_section_has_prose_but_no_pr_n_entries_and_no_escape() {
  local path="$work_dir/malformed.md"
  printf '## PR Breakdown\n\nWe will ship this in a couple of pull requests, details TBD.\n' > "$path"
  run_script "$path"
  assert_eq "should fail when the section has prose but no PR-N entries and no N/A or Single PR. escape" "2" "$VERDICT_EXIT"
}

it_should_detect_a_two_pr_cycle_when_pr_1_depends_on_pr_2_and_pr_2_depends_on_pr_1() {
  local fixture
  fixture=$(write_plan "cycle" '1. **PR-1** — First. Tasks: 1. Depends on: PR-2.
2. **PR-2** — Second. Tasks: 2. Depends on: PR-1.')
  run_script "$fixture"
  assert_eq "should detect a two-PR cycle when PR-1 depends on PR-2 and PR-2 depends on PR-1 (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should detect a two-PR cycle when PR-1 depends on PR-2 and PR-2 depends on PR-1 (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should detect a two-PR cycle when PR-1 depends on PR-2 and PR-2 depends on PR-1 (diagnostic present)\n'
  fi
}

it_should_detect_a_dangling_reference_when_a_pr_depends_on_a_pr_n_label_absent_from_the_pr_breakdown() {
  local fixture
  fixture=$(write_plan "dangling" '1. **PR-1** — First. Tasks: 1. Depends on: none.
2. **PR-2** — Second. Tasks: 2. Depends on: PR-9.')
  run_script "$fixture"
  assert_eq "should detect a dangling reference when a PR depends on a PR-N label absent from the PR Breakdown (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should detect a dangling reference when a PR depends on a PR-N label absent from the PR Breakdown (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should detect a dangling reference when a PR depends on a PR-N label absent from the PR Breakdown (diagnostic present)\n'
  fi
}

it_should_detect_a_duplicate_label_when_two_pr_breakdown_entries_share_the_same_pr_n_label() {
  local fixture
  fixture=$(write_plan "duplicate" '1. **PR-1** — First. Tasks: 1. Depends on: none.
2. **PR-1** — Duplicate label. Tasks: 2. Depends on: none.')
  run_script "$fixture"
  assert_eq "should detect a duplicate label when two PR Breakdown entries share the same PR-N label (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should detect a duplicate label when two PR Breakdown entries share the same PR-N label (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should detect a duplicate label when two PR Breakdown entries share the same PR-N label (diagnostic present)\n'
  fi
}

it_should_pass_when_a_heading_per_pr_plans_dependencies_all_resolve() {
  local fixture
  fixture=$(write_plan "happy-heading-grammar" '### PR-1. Naming and validators

**Depends on**: none

### PR-2. [Done] Core loop

**Depends on**: PR-1

Sequenced behind the validators so the riskiest conversion lands on a checked base.')
  run_script "$fixture"
  assert_eq "should pass when a plan writing one heading per PR has every dependency resolve" "0" "$VERDICT_EXIT"
}

it_should_detect_a_cycle_between_two_prs_written_as_headings() {
  local fixture
  fixture=$(write_plan "cycle-heading-grammar" '### PR-1. First

**Depends on**: PR-2

### PR-2. Second

**Depends on**: PR-1')
  run_script "$fixture"
  assert_eq "should detect a cycle between two PRs written as headings" "1" "$VERDICT_EXIT"
}

it_should_pass_when_every_pr_dependency_resolves_to_a_real_non_cyclic_pr_label
it_should_pass_when_a_heading_per_pr_plans_dependencies_all_resolve
it_should_detect_a_cycle_between_two_prs_written_as_headings
it_should_pass_when_the_plan_reads_single_pr_nothing_to_validate
it_should_pass_when_every_pr_is_independent_no_depends_on_entries
it_should_pass_when_the_plan_reads_the_n_a_escape_for_a_no_pr_repo
it_should_still_validate_pr_entries_that_follow_the_n_a_in_place_of_the_diagram
it_should_fail_when_the_section_has_prose_but_no_pr_n_entries_and_no_escape
it_should_detect_a_two_pr_cycle_when_pr_1_depends_on_pr_2_and_pr_2_depends_on_pr_1
it_should_detect_a_dangling_reference_when_a_pr_depends_on_a_pr_n_label_absent_from_the_pr_breakdown
it_should_detect_a_duplicate_label_when_two_pr_breakdown_entries_share_the_same_pr_n_label

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
