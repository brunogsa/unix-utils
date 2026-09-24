#!/usr/bin/env bash
# test-check-mermaid-renders.sh - plain-bash test file for
# check-mermaid-renders.sh.
#
# Usage:
#   bash test-check-mermaid-renders.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.
#
# Every fixture that reaches `mmdc` costs a real headless render
# (~1.5s), so the fixtures stay at the smallest diagram that
# still exercises the branch under test.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-mermaid-renders.sh"

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

# assert_contains - inline assert helper: passes when haystack
# holds the literal needle.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected to contain: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
  fi
}

# run_script - invokes check-mermaid-renders.sh, capturing
# stdout/stderr/exit code into VERDICT_OUT/VERDICT_ERR/
# VERDICT_EXIT.
run_script() {
  local out_file="$work_dir/stdout.txt" err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$@" >"$out_file" 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
  VERDICT_ERR=$(cat "$err_file")
}

# The valid fixture and the defective one are byte-identical
# except for the semicolon, so the failing block always opens on
# line 10 in both — which is what pins the reported line number.
write_two_block_doc() {
  local name="$1" second_message="$2"
  local path="$work_dir/$name.md"
  cat > "$path" <<MD
# Doc

\`\`\`mermaid
graph TD
  A[Start] --> B[End]
\`\`\`

Prose between the diagrams.

\`\`\`mermaid
sequenceDiagram
  participant TP
  TP->>TP: $second_message
\`\`\`
MD
  printf '%s' "$path"
}

it_should_pass_when_every_mermaid_diagram_in_the_document_renders() {
  local fixture
  fixture=$(write_two_block_doc "all-valid" 'dispatch plan-writer on session briefs (spec optional, ask before Linear)')
  run_script "$fixture"
  assert_eq "should pass when every mermaid diagram in the document renders" "0" "$VERDICT_EXIT"
  assert_contains "should name how many diagrams it checked" "2" "$VERDICT_OUT"
  assert_contains "should print its verdict on stdout with an OK prefix" "OK:" "$VERDICT_OUT"
}

it_should_fail_when_a_sequence_diagram_carries_a_semicolon_inside_a_message() {
  local fixture
  fixture=$(write_two_block_doc "semicolon-defect" 'dispatch plan-writer on session briefs (spec optional; ask before Linear)')
  run_script "$fixture"
  assert_eq "should fail when a sequence diagram message carries a semicolon (exit code)" "1" "$VERDICT_EXIT"
  assert_contains "should report the source line where the failing diagram's fence opened" "semicolon-defect.md:10" "$VERDICT_ERR"
  assert_contains "should report the parser error mmdc returned for the failing diagram" "Parse error" "$VERDICT_ERR"
  assert_eq "should keep the failure off stdout" "" "$VERDICT_OUT"
}

it_should_pass_when_the_document_holds_no_mermaid_block_at_all() {
  local fixture="$work_dir/no-diagram.md"
  printf '# Doc\n\nProse only, no diagram anywhere.\n' > "$fixture"
  run_script "$fixture"
  assert_eq "should pass when the document holds no mermaid block at all" "0" "$VERDICT_EXIT"
  assert_contains "should say there was nothing to check" "no mermaid" "$VERDICT_OUT"
}

it_should_ignore_a_mermaid_fence_quoted_inside_an_outer_tilde_fence() {
  local fixture="$work_dir/nested-sample.md"
  cat > "$fixture" <<'MD'
# Doc

The skill documents its diagram block as:

~~~markdown
```mermaid
this is not a diagram, it is sample markup
```
~~~
MD
  run_script "$fixture"
  assert_eq "should ignore a \`\`\`mermaid fence quoted inside an outer ~~~ fence (exit code)" "0" "$VERDICT_EXIT"
  assert_contains "should count no diagrams when the only mermaid fence is sample markup" "no mermaid" "$VERDICT_OUT"
}

it_should_ignore_a_tilde_mermaid_fence_quoted_inside_an_outer_backtick_fence() {
  local fixture="$work_dir/nested-tilde-sample.md"
  cat > "$fixture" <<'MD'
# Doc

The skill documents its diagram block as:

```markdown
~~~mermaid
this is not a diagram, it is sample markup
~~~
```
MD
  run_script "$fixture"
  assert_eq "should ignore a ~~~mermaid fence quoted inside an outer \`\`\` fence (exit code)" "0" "$VERDICT_EXIT"
  assert_contains "should count no diagrams when the only tilde mermaid fence is sample markup" "no mermaid" "$VERDICT_OUT"
}

it_should_render_a_diagram_written_with_a_tilde_fence() {
  local fixture="$work_dir/tilde-diagram.md"
  cat > "$fixture" <<'MD'
# Doc

~~~mermaid
graph TD
  A[Start] --> B[End]
~~~
MD
  run_script "$fixture"
  assert_eq "should render a diagram written with a ~~~mermaid fence" "0" "$VERDICT_EXIT"
  assert_contains "should count the tilde-fenced diagram" "1" "$VERDICT_OUT"
}

it_should_fail_closed_when_a_fence_is_left_open_at_eof() {
  local fixture="$work_dir/unclosed.md"
  printf '# Doc\n\n```mermaid\ngraph TD\n  A[Start] --> B[End]\n' > "$fixture"
  run_script "$fixture"
  assert_eq "should fail closed when a fence is left open at EOF (exit code)" "2" "$VERDICT_EXIT"
  assert_contains "should name the line the unclosed fence opened on" "line 3" "$VERDICT_ERR"
}

it_should_report_a_usage_error_when_no_argument_is_given() {
  run_script
  assert_eq "should report a usage error when no argument is given" "2" "$VERDICT_EXIT"
  assert_contains "should print the usage line" "usage:" "$VERDICT_ERR"
}

it_should_report_a_usage_error_when_a_second_argument_is_given() {
  local fixture="$work_dir/no-diagram.md"
  printf '# Doc\n' > "$fixture"
  run_script "$fixture" "$fixture"
  assert_eq "should report a usage error when a second argument is given" "2" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_when_the_named_file_is_missing() {
  run_script "$work_dir/absent.md"
  assert_eq "should report a usage error when the named file is missing" "2" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_when_mmdc_is_not_installed() {
  local fixture="$work_dir/no-diagram.md"
  printf '# Doc\n' > "$fixture"
  local err_file="$work_dir/stderr.txt"
  PATH=/usr/bin:/bin bash "$SCRIPT" "$fixture" >/dev/null 2>"$err_file"
  local exit_code=$?
  assert_eq "should report a usage error when mmdc is not installed (exit code)" "2" "$exit_code"
  assert_contains "should name install.sh as where mmdc comes from" "install.sh" "$(cat "$err_file")"
}

it_should_pass_when_every_mermaid_diagram_in_the_document_renders
it_should_fail_when_a_sequence_diagram_carries_a_semicolon_inside_a_message
it_should_pass_when_the_document_holds_no_mermaid_block_at_all
it_should_ignore_a_mermaid_fence_quoted_inside_an_outer_tilde_fence
it_should_ignore_a_tilde_mermaid_fence_quoted_inside_an_outer_backtick_fence
it_should_render_a_diagram_written_with_a_tilde_fence
it_should_fail_closed_when_a_fence_is_left_open_at_eof
it_should_report_a_usage_error_when_no_argument_is_given
it_should_report_a_usage_error_when_a_second_argument_is_given
it_should_report_a_usage_error_when_the_named_file_is_missing
it_should_report_a_usage_error_when_mmdc_is_not_installed

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
