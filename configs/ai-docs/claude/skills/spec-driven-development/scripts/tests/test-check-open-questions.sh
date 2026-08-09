#!/usr/bin/env bash
# test-check-open-questions.sh - plain-bash test file for check-open-questions.sh.
#
# Usage:
#   bash test-check-open-questions.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design, matching the other scripts in this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-open-questions.sh"

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

# run_script - invokes check-open-questions.sh against one or two fixtures,
# capturing stderr/exit code into VERDICT_ERR/VERDICT_EXIT (stdout is
# discarded — these tests assert on exit code and diagnostic presence only).
run_script() {
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$@" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_doc - writes the given Open-Questions-section body to a fresh fixture
# under work_dir, returns its path via stdout. A body of "-" writes a doc with
# no Open Questions section at all.
write_doc() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  if [ "$body" = "-" ]; then
    printf '## Some Other Section\n\nbody\n' > "$path"
  else
    printf '## Open Questions\n\n%s\n' "$body" > "$path"
  fi
  printf '%s' "$path"
}

it_should_pass_when_the_plans_open_questions_section_reads_none() {
  local fixture
  fixture=$(write_doc "settled" 'None')
  run_script "$fixture"
  assert_eq "should pass when the plan's Open Questions section reads None" "0" "$VERDICT_EXIT"
}

it_should_fail_when_a_question_marker_survives_in_the_plan() {
  local fixture
  fixture=$(write_doc "unsettled" '- **QUESTION:** which cache backend? ?')
  run_script "$fixture"
  assert_eq "should fail when a QUESTION marker survives in the plan (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should fail when a QUESTION marker survives in the plan (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should fail when a QUESTION marker survives in the plan (diagnostic present)\n'
  fi
}

it_should_fail_when_the_plan_is_settled_but_the_spec_still_holds_a_question() {
  local plan spec
  plan=$(write_doc "plan-settled" 'None')
  spec=$(write_doc "spec-unsettled" '- **QUESTION:** is the retry budget per call or per request? ?')
  run_script "$plan" "$spec"
  assert_eq "should fail when the plan is settled but the spec still holds a question" "1" "$VERDICT_EXIT"
}

it_should_ignore_a_question_marker_quoted_inside_a_fenced_code_block() {
  local fixture
  fixture=$(write_doc "fenced-example" 'None

The template writes its placeholder as:

```markdown
- **QUESTION:** ... ?
```')
  run_script "$fixture"
  assert_eq "should ignore a QUESTION marker quoted inside a fenced code block" "0" "$VERDICT_EXIT"
}

it_should_pass_trivially_when_the_document_has_no_open_questions_section() {
  local fixture
  fixture=$(write_doc "no-section" '-')
  run_script "$fixture"
  assert_eq "should pass trivially when the document has no Open Questions section" "0" "$VERDICT_EXIT"
}

it_should_not_read_a_question_marker_from_a_later_section() {
  local fixture="$work_dir/later-section.md"
  printf '## Open Questions\n\nNone\n\n## Risks\n\n- **QUESTION:** stray marker outside the section ?\n' > "$fixture"
  run_script "$fixture"
  assert_eq "should not read a QUESTION marker from a section after Open Questions" "0" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_when_the_named_file_is_missing() {
  run_script "$work_dir/absent.md"
  assert_eq "should report a usage error when the named file is missing" "2" "$VERDICT_EXIT"
}

it_should_pass_when_the_plans_open_questions_section_reads_none
it_should_fail_when_a_question_marker_survives_in_the_plan
it_should_fail_when_the_plan_is_settled_but_the_spec_still_holds_a_question
it_should_ignore_a_question_marker_quoted_inside_a_fenced_code_block
it_should_pass_trivially_when_the_document_has_no_open_questions_section
it_should_not_read_a_question_marker_from_a_later_section
it_should_report_a_usage_error_when_the_named_file_is_missing

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
