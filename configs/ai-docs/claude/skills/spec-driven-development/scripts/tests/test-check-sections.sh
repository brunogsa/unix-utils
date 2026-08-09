#!/usr/bin/env bash
# test-check-sections.sh - plain-bash test file for check-sections.sh.
#
# Usage:
#   bash test-check-sections.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-sections.sh"

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

# assert_contains - asserts the captured stderr mentions the given substring.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to contain: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

# run_script - invokes check-sections.sh against a doc/template fixture pair,
# capturing stderr/exit code into VERDICT_ERR/VERDICT_EXIT (stdout is discarded —
# these tests assert on exit code and diagnostic presence only).
run_script() {
  bash "$SCRIPT" "$@" >/dev/null 2>"$work_dir/stderr.txt"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$work_dir/stderr.txt")
}

# write_fixture - writes the given markdown body to a fresh file under work_dir,
# returns its path via stdout.
write_fixture() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '%s\n' "$body" > "$path"
  printf '%s' "$path"
}

TEMPLATE_BODY='# Plan: [Title]

## Technical Approach

## Threat Model

## Task Breakdown'

it_should_pass_when_the_doc_carries_every_template_section() {
  local template doc
  template=$(write_fixture "happy-template" "$TEMPLATE_BODY")
  doc=$(write_fixture "happy-doc" '# Plan: Parallel sessions

## Technical Approach

One worker per session.

## Threat Model

## Task Breakdown

1. Do the thing.')
  run_script "$doc" "$template"
  assert_eq "should pass when the doc carries every template section" "0" "$VERDICT_EXIT"
}

it_should_fail_and_name_the_section_when_one_is_missing() {
  local template doc
  template=$(write_fixture "missing-template" "$TEMPLATE_BODY")
  doc=$(write_fixture "missing-doc" '# Plan: Parallel sessions

## Technical Approach

## Task Breakdown')
  run_script "$doc" "$template"
  assert_eq "should fail when a template section is missing from the doc" "1" "$VERDICT_EXIT"
  assert_contains "should name the missing section in the failure output" "## Threat Model" "$VERDICT_ERR"
}

it_should_pass_when_a_section_body_is_only_an_na_line() {
  local template doc
  template=$(write_fixture "na-template" "$TEMPLATE_BODY")
  doc=$(write_fixture "na-doc" '# Plan: Parallel sessions

## Technical Approach

## Threat Model

N/A — no new attack surface; the change is local to the planner.

## Task Breakdown')
  run_script "$doc" "$template"
  assert_eq "should pass when a section carries only its N/A escape line, since the heading is what this checks" "0" "$VERDICT_EXIT"
}

it_should_not_let_a_fenced_heading_in_the_doc_satisfy_a_missing_section() {
  local template doc
  template=$(write_fixture "docfence-template" "$TEMPLATE_BODY")
  doc=$(write_fixture "docfence-doc" '# Plan: Parallel sessions

## Technical Approach

```markdown
## Threat Model
```

## Task Breakdown')
  run_script "$doc" "$template"
  assert_eq "should fail when the only occurrence of a section heading sits inside a fenced block" "1" "$VERDICT_EXIT"
  assert_contains "should still name the section that exists only inside a fence" "## Threat Model" "$VERDICT_ERR"
}

it_should_ignore_a_fenced_heading_in_the_template() {
  local template doc
  template=$(write_fixture "tplfence-template" '# Plan: [Title]

## Technical Approach

```markdown
## Illustrative Example Only
```

## Task Breakdown')
  doc=$(write_fixture "tplfence-doc" '# Plan: Parallel sessions

## Technical Approach

## Task Breakdown')
  run_script "$doc" "$template"
  assert_eq "should not require a heading the template only shows inside a fenced sample" "0" "$VERDICT_EXIT"
}

it_should_pass_when_the_doc_adds_a_section_the_template_lacks() {
  local template doc
  template=$(write_fixture "extra-template" "$TEMPLATE_BODY")
  doc=$(write_fixture "extra-doc" '# Plan: Parallel sessions

## Technical Approach

## Threat Model

## Task Breakdown

## Rollout Notes')
  run_script "$doc" "$template"
  assert_eq "should pass on an author-added section, which the fixed-section-set rule never forbids" "0" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_on_the_wrong_argument_count() {
  local template
  template=$(write_fixture "args-template" "$TEMPLATE_BODY")
  run_script "$template"
  assert_eq "should exit 2 when given one argument instead of two" "2" "$VERDICT_EXIT"
  assert_contains "should print the usage line on a wrong argument count" "usage:" "$VERDICT_ERR"
}

it_should_report_a_usage_error_when_a_file_is_missing() {
  local template
  template=$(write_fixture "nofile-template" "$TEMPLATE_BODY")
  run_script "$work_dir/does-not-exist.md" "$template"
  assert_eq "should exit 2 when the doc path does not exist" "2" "$VERDICT_EXIT"
  assert_contains "should name the unreadable path" "file not found" "$VERDICT_ERR"
}

it_should_report_a_usage_error_when_the_template_defines_no_sections() {
  local template doc
  template=$(write_fixture "empty-template" '# Plan: [Title]

No sections here at all.')
  doc=$(write_fixture "empty-doc" '# Plan: Parallel sessions

## Technical Approach')
  run_script "$doc" "$template"
  assert_eq "should exit 2 rather than vacuously pass when the template defines no sections" "2" "$VERDICT_EXIT"
  assert_contains "should say the template defines no sections" "no '## ' sections" "$VERDICT_ERR"
}

it_should_pass_when_the_doc_carries_every_template_section
it_should_fail_and_name_the_section_when_one_is_missing
it_should_pass_when_a_section_body_is_only_an_na_line
it_should_not_let_a_fenced_heading_in_the_doc_satisfy_a_missing_section
it_should_ignore_a_fenced_heading_in_the_template
it_should_pass_when_the_doc_adds_a_section_the_template_lacks
it_should_report_a_usage_error_on_the_wrong_argument_count
it_should_report_a_usage_error_when_a_file_is_missing
it_should_report_a_usage_error_when_the_template_defines_no_sections

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
