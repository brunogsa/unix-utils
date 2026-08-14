#!/usr/bin/env bash
# test-extract-design-tests.sh - plain-bash test file for
# extract-design-tests.sh.
#
# Usage:
#   bash test-extract-design-tests.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.
#
# Scoped to the `--annotations` mode only (bare-title,
# breadcrumb, AC tokens, T tokens columns): the default and
# `--pairs` modes are pre-existing, unchanged behavior and
# already have no regression to pin here.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/extract-design-tests.sh"

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

# write_plan - writes a plan fixture with the caller's Test
# Design body, returning its path via stdout.
write_plan() {
  local name="$1" design_body="$2"
  local path="$work_dir/$name.md"
  printf '# Plan\n\n## Test Design\n\n%s\n' "$design_body" > "$path"
  printf '%s' "$path"
}

it_should_print_the_bare_title_breadcrumb_and_ac_and_t_tokens_for_an_annotated_it_line() {
  local plan actual
  plan=$(write_plan "single-annotation" '```
describe("AgreementSyncUseCase", () => {
  // Happy cases
  it("should persist the agreement when the payload validates");   // AC-1 T3
});
```')
  actual=$(bash "$SCRIPT" --annotations "$plan")
  assert_eq "should print the bare title, breadcrumb, AC tokens and T tokens for an annotated it() line" \
    "$(printf 'should persist the agreement when the payload validates\tAgreementSyncUseCase > happy > should persist the agreement when the payload validates\tAC-1\tT3')" \
    "$actual"
}

it_should_join_multiple_ac_and_t_tokens_space_separated_when_an_annotation_cites_several() {
  local plan actual
  plan=$(write_plan "multi-token" '```
describe("AgreementSyncUseCase", () => {
  // Happy cases
  it("should persist the agreement under either governing AC");   // AC-1 AC-2 T3 T4
});
```')
  actual=$(bash "$SCRIPT" --annotations "$plan")
  assert_eq "should space-join multiple AC and T tokens when an annotation cites several of each" \
    "$(printf 'should persist the agreement under either governing AC\tAgreementSyncUseCase > happy > should persist the agreement under either governing AC\tAC-1 AC-2\tT3 T4')" \
    "$actual"
}

it_should_ignore_the_on_demand_tag_when_extracting_ac_and_t_tokens() {
  local plan actual
  plan=$(write_plan "on-demand-tag" '```
describe("AgreementSyncUseCase", () => {
  // Failure scenarios
  it("should DLQ the message when the downstream returns 5xx");     // AC-4 T5 [on-demand]
});
```')
  actual=$(bash "$SCRIPT" --annotations "$plan")
  assert_eq "should ignore the [on-demand] tag when extracting AC and T tokens" \
    "$(printf 'should DLQ the message when the downstream returns 5xx\tAgreementSyncUseCase > failure > should DLQ the message when the downstream returns 5xx\tAC-4\tT5')" \
    "$actual"
}

it_should_print_empty_ac_and_t_columns_for_every_row_when_the_plan_uses_the_old_list_form_with_no_annotations() {
  local plan actual
  plan=$(write_plan "list-form" '```
describe("check-thing", () => {
  // Happy cases
  it("should accept a valid path");
  // Failure scenarios
  it("should reject a missing path");
});
```')
  actual=$(bash "$SCRIPT" --annotations "$plan")
  assert_eq "should print empty AC and T columns for every row when the plan uses the old list form with no annotations" \
    "$(printf 'should accept a valid path\tcheck-thing > happy > should accept a valid path\t\t\nshould reject a missing path\tcheck-thing > failure > should reject a missing path\t\t')" \
    "$actual"
}

it_should_print_the_bare_title_breadcrumb_and_ac_and_t_tokens_for_an_annotated_it_line
it_should_join_multiple_ac_and_t_tokens_space_separated_when_an_annotation_cites_several
it_should_ignore_the_on_demand_tag_when_extracting_ac_and_t_tokens
it_should_print_empty_ac_and_t_columns_for_every_row_when_the_plan_uses_the_old_list_form_with_no_annotations

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
