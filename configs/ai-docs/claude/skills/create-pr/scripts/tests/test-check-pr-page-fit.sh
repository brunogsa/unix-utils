#!/usr/bin/env bash
# test-check-pr-page-fit.sh - plain-bash test file for
# check-pr-page-fit.sh.
#
# Usage:
#   bash test-check-pr-page-fit.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-pr-page-fit.sh"

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

# run_script - invokes check-pr-page-fit.sh with any number of
# args, capturing stdout into VERDICT_OUT.
#
# The exit code is ignored: every assertion below reads the
# per-section breakdown, which prints under every verdict.
#
# stderr goes to a file rather than a variable: no assertion
# below reads a diagnostic's wording.
run_script() {
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$@" >"$out_file" 2>"$err_file" || true
  VERDICT_OUT=$(cat "$out_file")
}

# write_body - writes the given PR-body markdown to a fresh
# fixture under work_dir, returns its path via stdout.
write_body() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '%s\n' "$body" > "$path"
  printf '%s' "$path"
}

# section_lines - the rendered-line count the breakdown reports
# for the named section, read from VERDICT_OUT.
section_lines() {
  printf '%s\n' "$VERDICT_OUT" | awk -v name="$1" '
    /^  lines  section/ { in_breakdown = 1; next }
    in_breakdown { count = $1; $1 = ""; sub(/^ +/, ""); if ($0 == name) { print count; exit } }'
}

# text_lines - N distinct prose lines, so a fixture's hidden
# bulk is large enough that charging it would show.
text_lines() {
  local prefix="$1" n="$2" k
  for ((k = 1; k <= n; k++)); do printf '%s line %d of text\n' "$prefix" "$k"; done
}

it_should_charge_a_collapsed_block_with_a_nested_block_only_its_summary_line() {
  local fixture
  fixture=$(write_body "nested-collapsed" "## Appendix

<details>
<summary>Outer - full test run</summary>

<details>
<summary>Middle - failing suite</summary>
<details>
<summary>Inner - failing case log</summary>
$(text_lines inner 5)
</details>
$(text_lines middle 10)
</details>
$(text_lines outer 10)

</details>

## Follow-ups

One follow-up ticket filed for the retry backoff.")
  run_script "$fixture"
  assert_eq "should charge a collapsed block holding a nested block only its summary line (heading + summary)" "2" "$(section_lines "Appendix")"
  assert_eq "should resume counting visible text after the collapsed outer block closes" "2" "$(section_lines "Follow-ups")"
}

it_should_not_charge_text_after_a_nested_closer_inside_a_collapsed_block() {
  local fixture
  fixture=$(write_body "text-after-nested-closer" "## Appendix

<details>
<summary>Outer - full test run</summary>

$(text_lines before 10)
<details>
<summary>Inner - failing case log</summary>
$(text_lines inner 5)
</details>
$(text_lines after 10)

</details>")
  run_script "$fixture"
  assert_eq "should not charge text that follows a nested block's closer while the outer block is still collapsed" "2" "$(section_lines "Appendix")"
}

it_should_not_end_a_collapsed_block_early_at_a_one_line_nested_block() {
  local fixture
  fixture=$(write_body "one-line-nested" "## Appendix

<details>
<summary>Outer - full test run</summary>

<details><summary>Inner - exit code</summary>exit 0</details>
$(text_lines after 10)

</details>

Visible closing note after the appendix.")
  run_script "$fixture"
  assert_eq "should keep a collapsed block hidden past a nested block opened and closed on one line (summary + trailing visible note)" "3" "$(section_lines "Appendix")"
}

it_should_charge_a_collapsed_block_nested_in_an_open_block_only_its_summary_line() {
  local fixture
  fixture=$(write_body "collapsed-in-open" "## Evidences

<details open>
<summary>Scenario 1 - kit-less collection on stage</summary>

Ran a kit-less collection against Oracle EBS on stage.
<details>
<summary>Full response body</summary>
$(text_lines response 10)
</details>
Read back the collection total afterwards.

</details>")
  run_script "$fixture"
  assert_eq "should charge a collapsed block inside an open block only its summary, while the open block's own text still counts" "5" "$(section_lines "Evidences")"
}

it_should_keep_charging_a_single_level_collapsed_block_only_its_summary_line() {
  local fixture
  fixture=$(write_body "single-level" "## Appendix

<details>
<summary>Full test run</summary>

$(text_lines run 20)

</details>")
  run_script "$fixture"
  assert_eq "should keep charging a single-level collapsed block only its summary line (regression)" "2" "$(section_lines "Appendix")"
}

it_should_keep_charging_sibling_collapsed_blocks_one_summary_line_each() {
  local fixture
  fixture=$(write_body "siblings" "## Appendix

<details>
<summary>Unit test run</summary>
$(text_lines unit 20)
</details>

<details>
<summary>Integration test run</summary>
$(text_lines integration 20)
</details>")
  run_script "$fixture"
  assert_eq "should keep charging sibling collapsed blocks one summary line each (regression)" "3" "$(section_lines "Appendix")"
}

it_should_charge_a_top_level_one_line_block_one_line_and_keep_counting_after_it() {
  local fixture
  fixture=$(write_body "top-level-one-line" "## Evidences

<details><summary>Exit code</summary>exit 0</details>
Visible line after the one-line block.")
  run_script "$fixture"
  assert_eq "should charge a one-line collapsed block one line and still count the visible text after it (regression)" "3" "$(section_lines "Evidences")"
}

it_should_charge_a_collapsed_block_with_a_nested_block_only_its_summary_line
it_should_not_charge_text_after_a_nested_closer_inside_a_collapsed_block
it_should_not_end_a_collapsed_block_early_at_a_one_line_nested_block
it_should_charge_a_collapsed_block_nested_in_an_open_block_only_its_summary_line
it_should_keep_charging_a_single_level_collapsed_block_only_its_summary_line
it_should_keep_charging_sibling_collapsed_blocks_one_summary_line_each
it_should_charge_a_top_level_one_line_block_one_line_and_keep_counting_after_it

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
