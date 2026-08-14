#!/usr/bin/env bash
# test-check-ac-coverage.sh - plain-bash test file for check-ac-coverage.sh.
#
# Usage:
#   bash test-check-ac-coverage.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-ac-coverage.sh"

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

# assert_contains - passes when the haystack carries the given literal text.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  missing text: %s\n  actual:\n%s\n' "$description" "$needle" "$haystack"
  fi
}

# run_script - invokes check-ac-coverage.sh on a plan and a spec, capturing
# stderr into VERDICT_ERR and the exit code into VERDICT_EXIT.
run_script() {
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$@" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_plan - writes a plan fixture whose Test Design section is fixed and
# whose AC-coverage list is the caller's, returning its path via stdout. The
# two designed breadcrumbs it always yields are:
#   check-thing > happy > should accept a valid path
#   check-thing > failure > should reject a missing path
#
# The "plan-" prefix is what keeps a test free to pass the same name to
# write_spec - without it the second writer silently overwrites the first.
write_plan() {
  local name="$1" coverage="$2"
  local path="$work_dir/plan-$name.md"
  {
    printf '# Plan\n\n## Test Design\n\n'
    printf '```\n'
    printf 'describe("check-thing", () => {\n'
    printf '  // Happy cases\n'
    printf '  it("should accept a valid path");\n'
    printf '  // Failure scenarios\n'
    printf '  it("should reject a missing path");\n'
    printf '});\n'
    printf '```\n\n'
    printf '## AC Coverage\n\n%s\n' "$coverage"
  } > "$path"
  printf '%s' "$path"
}

# write_spec - writes a spec fixture with the caller's body under a
# `## Testable Acceptance Criteria` heading, returning its path via stdout.
# Carries a "spec-" prefix for the reason write_plan's comment gives.
write_spec() {
  local name="$1" body="$2"
  local path="$work_dir/spec-$name.md"
  printf '# Spec\n\n## Testable Acceptance Criteria\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

# write_annotated_plan - writes a plan fixture whose Test Design carries the
# new inline `// AC-N` annotations and NO separate AC Coverage list at all
# (the single-source form): completeness reads the annotations directly, so
# there is no second citation list left for the HONESTY check to police.
write_annotated_plan() {
  local name="$1" design_body="$2"
  local path="$work_dir/plan-$name.md"
  printf '# Plan\n\n## Test Design\n\n%s\n' "$design_body" > "$path"
  printf '%s' "$path"
}

it_should_pass_when_every_spec_ac_has_a_header_and_every_citation_is_a_real_design_title() {
  local plan spec
  plan=$(write_plan "complete" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"
- **AC-2** missing path rejected
  - "check-thing > failure > should reject a missing path"')
  spec=$(write_spec "complete" '### AC-1: The checker accepts a valid path

### AC-2: The checker rejects a missing path')
  run_script "$plan" "$spec"
  assert_eq "should pass when every spec AC has a header and every citation is a real design title" "0" "$VERDICT_EXIT"
}

it_should_fail_when_a_spec_ac_has_no_coverage_header_in_the_plan() {
  local plan spec
  plan=$(write_plan "missing-header" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"')
  spec=$(write_spec "missing-header" '### AC-1: The checker accepts a valid path

### AC-2: The checker rejects a missing path')
  run_script "$plan" "$spec"
  assert_eq "should fail when a spec AC has no coverage header in the plan (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should fail when a spec AC has no coverage header in the plan (names the uncovered AC)" "$VERDICT_ERR" "AC-2"
}

it_should_fail_when_a_plan_coverage_header_names_an_ac_absent_from_the_spec() {
  local plan spec
  plan=$(write_plan "invented-header" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"
- **AC-7** an AC the spec never defines
  - "check-thing > failure > should reject a missing path"')
  spec=$(write_spec "invented-header" '### AC-1: The checker accepts a valid path')
  run_script "$plan" "$spec"
  assert_eq "should fail when a plan coverage header names an AC absent from the spec (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should fail when a plan coverage header names an AC absent from the spec (names the invented AC)" "$VERDICT_ERR" "AC-7"
}

it_should_fail_when_a_cited_test_is_absent_verbatim_from_test_design() {
  local plan spec
  plan=$(write_plan "bogus-citation" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid pathway"')
  spec=$(write_spec "bogus-citation" '### AC-1: The checker accepts a valid path')
  run_script "$plan" "$spec"
  assert_eq "should fail when a cited test is absent verbatim from Test Design (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should fail when a cited test is absent verbatim from Test Design (names the bogus citation)" "$VERDICT_ERR" "should accept a valid pathway"
}

it_should_report_a_diagnostic_when_the_spec_defines_no_ac_headings_at_all() {
  local plan spec
  plan=$(write_plan "no-spec-acs" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"')
  spec=$(write_spec "no-spec-acs" 'None yet.')
  run_script "$plan" "$spec"
  assert_eq "should report a diagnostic when the spec defines no AC headings at all (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should report a diagnostic when the spec defines no AC headings at all (the caller is told why, not left with a bare exit code)" "$VERDICT_ERR" "no '### AC-N:' definitions found"
}

it_should_ignore_an_ac_heading_sitting_outside_the_specs_acceptance_criteria_section() {
  local plan spec
  plan=$(write_plan "ac-outside-section" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"')
  spec=$(write_spec "ac-outside-section" '### AC-1: The checker accepts a valid path

## Appendix

### AC-9: An example AC quoted well outside the criteria section')
  run_script "$plan" "$spec"
  assert_eq "should ignore an AC heading sitting outside the spec Acceptance Criteria section" "0" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_when_a_named_file_is_missing() {
  local plan
  plan=$(write_plan "usage-error" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"')
  run_script "$plan" "$work_dir/absent-spec.md"
  assert_eq "should report a usage error when a named file is missing" "2" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_when_given_the_wrong_argument_count() {
  local plan
  plan=$(write_plan "arg-count" '- **AC-1** valid path accepted
  - "check-thing > happy > should accept a valid path"')
  run_script "$plan"
  assert_eq "should report a usage error when given the wrong argument count" "2" "$VERDICT_EXIT"
}

it_should_pass_in_annotated_form_when_every_spec_ac_appears_in_at_least_one_annotation() {
  local plan spec
  plan=$(write_annotated_plan "annotated-complete" '```
describe("check-thing", () => {
  // Happy cases
  it("should accept a valid path");   // AC-1 T1
  // Failure scenarios
  it("should reject a missing path");   // AC-2 T2
});
```')
  spec=$(write_spec "annotated-complete" '### AC-1: The checker accepts a valid path

### AC-2: The checker rejects a missing path')
  run_script "$plan" "$spec"
  assert_eq "should pass in annotated form when every spec AC appears in at least one annotation" "0" "$VERDICT_EXIT"
}

it_should_fail_in_annotated_form_when_a_spec_ac_has_no_annotation_naming_the_uncovered_ac() {
  local plan spec
  plan=$(write_annotated_plan "annotated-incomplete" '```
describe("check-thing", () => {
  // Happy cases
  it("should accept a valid path");   // AC-1 T1
  // Failure scenarios
  it("should reject a missing path");   // T2
});
```')
  spec=$(write_spec "annotated-incomplete" '### AC-1: The checker accepts a valid path

### AC-2: The checker rejects a missing path')
  run_script "$plan" "$spec"
  assert_eq "should fail in annotated form when a spec AC has no annotation (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should fail in annotated form when a spec AC has no annotation (names the uncovered AC)" "$VERDICT_ERR" "AC-2"
}

it_should_pass_when_every_spec_ac_has_a_header_and_every_citation_is_a_real_design_title
it_should_fail_when_a_spec_ac_has_no_coverage_header_in_the_plan
it_should_fail_when_a_plan_coverage_header_names_an_ac_absent_from_the_spec
it_should_fail_when_a_cited_test_is_absent_verbatim_from_test_design
it_should_report_a_diagnostic_when_the_spec_defines_no_ac_headings_at_all
it_should_ignore_an_ac_heading_sitting_outside_the_specs_acceptance_criteria_section
it_should_report_a_usage_error_when_a_named_file_is_missing
it_should_report_a_usage_error_when_given_the_wrong_argument_count
it_should_pass_in_annotated_form_when_every_spec_ac_appears_in_at_least_one_annotation
it_should_fail_in_annotated_form_when_a_spec_ac_has_no_annotation_naming_the_uncovered_ac

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
