#!/usr/bin/env bash
# test-check-deterministic-gates.sh - plain-bash test file for
# check-deterministic-gates.sh.
#
# Usage:
#   bash test-check-deterministic-gates.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.
#
# The runner resolves every gate as a sibling of itself, so
# each test copies it into a throwaway skills tree whose gates
# are stubs.
#
# A stub appends its own argv to a call log and exits with a
# code the test picked. That lets a test assert argument order
# and exit-code handling without rendering a diagram or parsing
# a real plan.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER_SRC="$script_dir/check-deterministic-gates.sh"

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

# assert_not_contains - inline assert helper: the mirror of
# assert_contains.
assert_not_contains() {
  local description="$1" needle="$2" haystack="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  unexpected: %s\n  actual:     %s\n' "$description" "$needle" "$haystack"
  fi
}

# make_stub - writes a gate stub that logs "<name> <argv>" to
# $CALL_LOG, optionally prints a marker line to stderr, and
# exits with the code passed in.
make_stub() {
  local path="$1" name="$2" code="$3" marker="${4:-}"
  {
    cat <<STUB
#!/usr/bin/env bash
echo "$name \$*" >> "\$CALL_LOG"
STUB
    [ -n "$marker" ] && printf 'echo "%s" >&2\n' "$marker"
    printf 'exit %s\n' "$code"
  } > "$path"
  chmod +x "$path"
}

# build_tree - builds a fresh skills tree under work_dir whose
# gates all exit 0, copies the runner in, and sets
# TREE/RUNNER/CALL_LOG/PLAN/SPEC.
build_tree() {
  TREE=$(mktemp -d "$work_dir/tree.XXXXXX")
  local sdd="$TREE/spec-driven-development" doc="$TREE/doc-standards"
  mkdir -p "$sdd/scripts" "$sdd/assets" "$doc/scripts"
  cp "$RUNNER_SRC" "$sdd/scripts/check-deterministic-gates.sh"
  RUNNER="$sdd/scripts/check-deterministic-gates.sh"
  : > "$sdd/assets/plan-template.md"
  : > "$sdd/assets/spec-template.md"
  local g
  for g in check-mermaid-renders.sh check-sections.sh check-test-distribution.sh \
    check-pr-dag.sh check-tasks-dag.sh check-files-union.sh check-ac-task-consistency.py \
    check-ac-coverage.sh check-coverage-checklists.sh; do
    make_stub "$sdd/scripts/$g" "$g" 0
  done
  make_stub "$doc/scripts/check-density.sh" check-density.sh 0
  make_stub "$doc/scripts/check-bullet-gap.py" check-bullet-gap.py 0
  make_stub "$doc/scripts/check-bullet-structure.py" check-bullet-structure.py 0
  CALL_LOG="$TREE/calls.log"
  export CALL_LOG
  : > "$CALL_LOG"
  PLAN="$TREE/plan.md"
  SPEC="$TREE/spec.md"
  : > "$PLAN"
  : > "$SPEC"
}

# run_runner - runs the runner with the given args, capturing
# RUN_OUT (stdout), RUN_ERR (stderr) and RUN_EXIT.
run_runner() {
  bash "$RUNNER" "$@" >"$work_dir/out.txt" 2>"$work_dir/err.txt"
  RUN_EXIT=$?
  RUN_OUT=$(cat "$work_dir/out.txt")
  RUN_ERR=$(cat "$work_dir/err.txt")
}

it_should_run_every_member_in_the_reference_order_and_pass_when_given_a_plan_and_a_spec() {
  build_tree
  run_runner "$PLAN" "$SPEC"
  assert_eq "should pass when every gate passes (exit code)" "0" "$RUN_EXIT"
  local expected
  expected=$(cat <<EOF2
check-mermaid-renders.sh $PLAN
check-mermaid-renders.sh $SPEC
check-density.sh $PLAN
check-bullet-gap.py $PLAN
check-bullet-structure.py $PLAN
check-density.sh $SPEC
check-bullet-gap.py $SPEC
check-bullet-structure.py $SPEC
check-sections.sh $PLAN $TREE/spec-driven-development/assets/plan-template.md
check-sections.sh $SPEC $TREE/spec-driven-development/assets/spec-template.md
check-test-distribution.sh $PLAN
check-pr-dag.sh $PLAN
check-tasks-dag.sh $PLAN
check-files-union.sh $PLAN
check-ac-task-consistency.py $PLAN
check-ac-coverage.sh $PLAN $SPEC
check-coverage-checklists.sh $SPEC
EOF2
)
  assert_eq "should invoke every member in the reference order, plan before spec for check-ac-coverage" "$expected" "$(cat "$CALL_LOG")"
  assert_eq "should print one line per gate invocation" "17" "$(printf '%s\n' "$RUN_OUT" | grep -c '^PASS ')"
}

it_should_skip_the_spec_taking_gates_and_report_them_as_skipped_when_given_no_spec() {
  build_tree
  run_runner "$PLAN"
  assert_eq "should exit 0 when every non-skipped gate passes and no spec is given" "0" "$RUN_EXIT"
  assert_not_contains "should never invoke a spec-taking gate without a spec" "spec.md" "$(cat "$CALL_LOG")"
  assert_not_contains "should never invoke check-ac-coverage without a spec" "check-ac-coverage.sh" "$(cat "$CALL_LOG")"
  assert_not_contains "should never invoke check-coverage-checklists without a spec" "check-coverage-checklists.sh" "$(cat "$CALL_LOG")"
  assert_contains "should report check-ac-coverage as SKIP" "SKIP exit=- check-ac-coverage.sh" "$RUN_OUT"
  assert_contains "should report check-coverage-checklists as SKIP" "SKIP exit=- check-coverage-checklists.sh" "$RUN_OUT"
  assert_not_contains "should never report a skipped gate as PASS" "PASS exit=0 check-ac-coverage.sh" "$RUN_OUT"
  assert_not_contains "should never report the skipped spec gate as PASS" "PASS exit=0 check-coverage-checklists.sh" "$RUN_OUT"
  assert_eq "should skip exactly the seven spec-only invocations" "7" "$(printf '%s\n' "$RUN_OUT" | grep -c '^SKIP ')"
}

it_should_keep_running_after_a_failing_gate_show_its_output_and_exit_non_zero() {
  build_tree
  make_stub "$TREE/spec-driven-development/scripts/check-sections.sh" check-sections.sh 1 "MISSING-SECTION-MARKER"
  run_runner "$PLAN" "$SPEC"
  assert_eq "should exit 1 when any gate failed" "1" "$RUN_EXIT"
  assert_contains "should report the failing gate with its exit code" "FAIL exit=1 check-sections.sh" "$RUN_OUT"
  assert_contains "should show the failing gate's own output" "MISSING-SECTION-MARKER" "$RUN_OUT$RUN_ERR"
  assert_contains "should still run a gate ordered after the failure" "check-coverage-checklists.sh $SPEC" "$(cat "$CALL_LOG")"
}

it_should_stay_quiet_about_a_passing_gate_output() {
  build_tree
  make_stub "$TREE/spec-driven-development/scripts/check-pr-dag.sh" check-pr-dag.sh 0 "PASSING-CHATTER"
  run_runner "$PLAN" "$SPEC"
  assert_not_contains "should not replay a passing gate's output" "PASSING-CHATTER" "$RUN_OUT$RUN_ERR"
}

it_should_count_a_gate_usage_error_as_a_failure() {
  build_tree
  make_stub "$TREE/spec-driven-development/scripts/check-tasks-dag.sh" check-tasks-dag.sh 2 "USAGE-MARKER"
  run_runner "$PLAN" "$SPEC"
  assert_eq "should exit 1 when a gate exits 2" "1" "$RUN_EXIT"
  assert_contains "should report the gate's exit 2" "FAIL exit=2 check-tasks-dag.sh" "$RUN_OUT"
}

it_should_warn_without_failing_the_run_when_a_density_check_finds_a_violation() {
  build_tree
  make_stub "$TREE/doc-standards/scripts/check-density.sh" check-density.sh 1 "TOO-DENSE-MARKER"
  run_runner "$PLAN" "$SPEC"
  assert_eq "should exit 0 when only density reports violations (a Scout, not a blocker)" "0" "$RUN_EXIT"
  assert_contains "should label the density result WARN" "WARN exit=1 check-density.sh" "$RUN_OUT"
  assert_contains "should show the density output" "TOO-DENSE-MARKER" "$RUN_OUT$RUN_ERR"
}

it_should_exit_2_with_usage_on_stderr_when_given_no_arguments() {
  build_tree
  run_runner
  assert_eq "should exit 2 on no args" "2" "$RUN_EXIT"
  assert_contains "should print usage on stderr" "usage:" "$RUN_ERR"
}

it_should_exit_2_with_usage_on_stderr_when_given_more_than_two_arguments() {
  build_tree
  run_runner "$PLAN" "$SPEC" "$PLAN"
  assert_eq "should exit 2 on three args" "2" "$RUN_EXIT"
  assert_contains "should print usage on stderr" "usage:" "$RUN_ERR"
}

it_should_run_exactly_the_spec_gates_and_report_the_plan_gates_as_skipped_when_given_spec_only() {
  build_tree
  run_runner --spec-only "$SPEC"
  assert_eq "should exit 0 when every spec gate passes in spec-only mode" "0" "$RUN_EXIT"
  local expected
  expected=$(cat <<EOF2
check-mermaid-renders.sh $SPEC
check-density.sh $SPEC
check-bullet-gap.py $SPEC
check-bullet-structure.py $SPEC
check-sections.sh $SPEC $TREE/spec-driven-development/assets/spec-template.md
check-coverage-checklists.sh $SPEC
EOF2
)
  assert_eq "should invoke only the spec gates, with the spec template for check-sections" "$expected" "$(cat "$CALL_LOG")"
  assert_not_contains "should never compare the spec against the plan template" "plan-template.md" "$(cat "$CALL_LOG")"
  assert_contains "should report the plan-only check-test-distribution as SKIP" "SKIP exit=- check-test-distribution.sh" "$RUN_OUT"
  assert_contains "should report check-ac-coverage as SKIP since it needs a plan" "SKIP exit=- check-ac-coverage.sh" "$RUN_OUT"
  assert_not_contains "should never report a plan gate as PASS in spec-only mode" "PASS exit=0 check-pr-dag.sh" "$RUN_OUT"
}

it_should_exit_1_with_the_failing_gate_when_a_spec_gate_fails_in_spec_only_mode() {
  build_tree
  make_stub "$TREE/spec-driven-development/scripts/check-sections.sh" check-sections.sh 1 "MISSING-SECTION-MARKER"
  run_runner --spec-only "$SPEC"
  assert_eq "should exit 1 when a spec gate failed in spec-only mode" "1" "$RUN_EXIT"
  assert_contains "should report the failing spec gate" "FAIL exit=1 check-sections.sh (spec)" "$RUN_OUT"
}

it_should_exit_2_with_usage_on_stderr_when_spec_only_has_no_file_argument() {
  build_tree
  run_runner --spec-only
  assert_eq "should exit 2 when --spec-only names no file" "2" "$RUN_EXIT"
  assert_contains "should print usage on stderr" "usage:" "$RUN_ERR"
  assert_eq "should run no gate on a usage error" "" "$(cat "$CALL_LOG")"
}

it_should_exit_2_naming_the_file_when_the_spec_only_file_is_missing() {
  build_tree
  run_runner --spec-only "$TREE/nospec.md"
  assert_eq "should exit 2 on a missing spec in spec-only mode" "2" "$RUN_EXIT"
  assert_contains "should name the missing spec on stderr" "nospec.md" "$RUN_ERR"
  assert_eq "should run no gate when the spec is missing" "" "$(cat "$CALL_LOG")"
}

it_should_exit_2_naming_the_file_when_the_plan_is_missing() {
  build_tree
  run_runner "$TREE/nope.md"
  assert_eq "should exit 2 on a missing plan" "2" "$RUN_EXIT"
  assert_contains "should name the missing file on stderr" "nope.md" "$RUN_ERR"
  assert_eq "should run no gate when an input is missing" "" "$(cat "$CALL_LOG")"
}

it_should_exit_2_naming_the_file_when_the_spec_is_missing() {
  build_tree
  run_runner "$PLAN" "$TREE/nospec.md"
  assert_eq "should exit 2 on a missing spec" "2" "$RUN_EXIT"
  assert_contains "should name the missing spec on stderr" "nospec.md" "$RUN_ERR"
}

it_should_exit_2_naming_the_directory_when_the_doc_standards_sibling_is_missing() {
  build_tree
  rm -rf "$TREE/doc-standards"
  run_runner "$PLAN" "$SPEC"
  assert_eq "should exit 2 when doc-standards cannot be resolved" "2" "$RUN_EXIT"
  assert_contains "should name the unresolved doc-standards directory on stderr" "error: cannot resolve the doc-standards scripts directory" "$RUN_ERR"
  assert_eq "should run no gate when doc-standards cannot be resolved" "" "$(cat "$CALL_LOG")"
}

it_should_exit_2_naming_the_directory_when_the_assets_sibling_is_missing() {
  build_tree
  rm -rf "$TREE/spec-driven-development/assets"
  run_runner "$PLAN" "$SPEC"
  assert_eq "should exit 2 when assets cannot be resolved" "2" "$RUN_EXIT"
  assert_contains "should name the unresolved assets directory on stderr" "error: cannot resolve the assets directory" "$RUN_ERR"
  assert_eq "should run no gate when assets cannot be resolved" "" "$(cat "$CALL_LOG")"
}

it_should_run_every_member_in_the_reference_order_and_pass_when_given_a_plan_and_a_spec
it_should_skip_the_spec_taking_gates_and_report_them_as_skipped_when_given_no_spec
it_should_keep_running_after_a_failing_gate_show_its_output_and_exit_non_zero
it_should_stay_quiet_about_a_passing_gate_output
it_should_count_a_gate_usage_error_as_a_failure
it_should_warn_without_failing_the_run_when_a_density_check_finds_a_violation
it_should_exit_2_with_usage_on_stderr_when_given_no_arguments
it_should_exit_2_with_usage_on_stderr_when_given_more_than_two_arguments
it_should_run_exactly_the_spec_gates_and_report_the_plan_gates_as_skipped_when_given_spec_only
it_should_exit_1_with_the_failing_gate_when_a_spec_gate_fails_in_spec_only_mode
it_should_exit_2_with_usage_on_stderr_when_spec_only_has_no_file_argument
it_should_exit_2_naming_the_file_when_the_spec_only_file_is_missing
it_should_exit_2_naming_the_file_when_the_plan_is_missing
it_should_exit_2_naming_the_file_when_the_spec_is_missing
it_should_exit_2_naming_the_directory_when_the_doc_standards_sibling_is_missing
it_should_exit_2_naming_the_directory_when_the_assets_sibling_is_missing

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
