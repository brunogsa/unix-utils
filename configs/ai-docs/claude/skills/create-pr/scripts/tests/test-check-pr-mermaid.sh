#!/usr/bin/env bash
# test-check-pr-mermaid.sh - plain-bash test file for
# check-pr-mermaid.sh.
#
# Usage:
#   bash test-check-pr-mermaid.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.
#
# Needs `mmdc` on PATH: every render case runs the real
# mermaid-cli, since a stubbed renderer would pass a diagram
# GitHub still rejects.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-pr-mermaid.sh"

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

# assert_contains - passes when needle occurs in haystack.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected to contain: %s\n  actual: %s\n' "$description" "$needle" "$haystack"
  fi
}

# run_script - invokes check-pr-mermaid.sh with any number of
# args, capturing stderr and the exit code into VERDICT_ERR and
# VERDICT_EXIT. stderr is what the caller reads to learn which
# diagram broke, so it is the stream the failure cases assert.
run_script() {
  local err_file="$work_dir/stderr.txt"
  VERDICT_EXIT=0
  bash "$SCRIPT" "$@" >"$work_dir/stdout.txt" 2>"$err_file" || VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_body - writes the given markdown to a fresh fixture
# under work_dir, returns its path via stdout.
write_body() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '%s\n' "$body" > "$path"
  printf '%s' "$path"
}

# The defect this gate exists for: four real PR bodies shipped
# a sequenceDiagram whose message held a `;`, which mermaid's
# sequence parser reads as the end of the statement.
it_should_fail_a_sequence_diagram_whose_message_holds_a_semicolon() {
  local fixture
  fixture=$(write_body "semicolon-in-message" '## Architecture

```mermaid
sequenceDiagram
    participant Q as SQS consumer
    participant B as School sync handler
    Q->>B: deliver school event
    B-->>Q: rethrown as is; the SQS consumer deletes it
```')
  run_script "$fixture"
  assert_eq "should fail a sequence diagram whose message holds a semicolon (exit code)" "3" "$VERDICT_EXIT"
  assert_contains "should name the broken diagram line on stderr" "Parse error on line 5" "$VERDICT_ERR"
  assert_contains "should quote the broken message text on stderr" "consumer deletes it" "$VERDICT_ERR"
}

it_should_pass_a_valid_flowchart() {
  local fixture
  fixture=$(write_body "valid-flowchart" '## Architecture

```mermaid
flowchart LR
    crm["CRM school event"] --> router["PIC brands router"]
    router -->|"routed"| erp["ERP hub consumer"]
```')
  run_script "$fixture"
  assert_eq "should pass a valid flowchart" "0" "$VERDICT_EXIT"
}

it_should_pass_a_valid_sequence_diagram() {
  local fixture
  fixture=$(write_body "valid-sequence" '## Architecture

```mermaid
sequenceDiagram
    participant Q as SQS consumer
    participant B as School sync handler
    Q->>B: deliver school event
    B-->>Q: rethrown as is (the SQS consumer deletes it)
```')
  run_script "$fixture"
  assert_eq "should pass a valid sequence diagram" "0" "$VERDICT_EXIT"
}

it_should_pass_a_body_with_no_mermaid_diagram() {
  local fixture
  fixture=$(write_body "no-mermaid" '## Context

Routes CRM school-state errors to the error monitor.

```json
{ "schoolDocNumber": "12345678000195" }
```')
  run_script "$fixture"
  assert_eq "should pass a body with no mermaid diagram" "0" "$VERDICT_EXIT"
}

# The valid block sits first, so a gate that only rendered the
# leading diagram would wrongly pass this file.
it_should_fail_a_body_whose_second_diagram_is_broken_after_a_valid_first_one() {
  local fixture
  fixture=$(write_body "valid-then-broken" '## Architecture

```mermaid
flowchart LR
    crm["CRM school event"] --> router["PIC brands router"]
```

## Sequence

```mermaid
sequenceDiagram
    participant Q as SQS consumer
    participant B as School sync handler
    B-->>Q: ack; message deleted
```')
  run_script "$fixture"
  assert_eq "should fail a body whose second diagram is broken after a valid first one" "3" "$VERDICT_EXIT"
}

# A skipped gate is what let the broken bodies ship, so a
# missing renderer must fail loudly, never pass. PATH drops
# /usr/local/bin, where mmdc lives, but keeps the coreutils.
it_should_fail_with_an_install_hint_when_mmdc_is_not_installed() {
  local fixture err_file="$work_dir/stderr.txt"
  fixture=$(write_body "mmdc-missing" '```mermaid
flowchart LR
    a["start"] --> b["end"]
```')
  VERDICT_EXIT=0
  env PATH=/usr/bin:/bin /bin/bash "$SCRIPT" "$fixture" >/dev/null 2>"$err_file" || VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
  assert_eq "should fail with exit 4 when mmdc is not installed" "4" "$VERDICT_EXIT"
  assert_contains "should name the mermaid-cli install command when mmdc is not installed" "npm install -g @mermaid-js/mermaid-cli" "$VERDICT_ERR"
}

it_should_exit_1_when_the_file_does_not_exist() {
  run_script "$work_dir/does-not-exist.md"
  assert_eq "should exit 1 when the file does not exist" "1" "$VERDICT_EXIT"
}

it_should_exit_1_when_called_with_no_argument() {
  run_script
  assert_eq "should exit 1 when called with no argument" "1" "$VERDICT_EXIT"
}

it_should_fail_a_sequence_diagram_whose_message_holds_a_semicolon
it_should_pass_a_valid_flowchart
it_should_pass_a_valid_sequence_diagram
it_should_pass_a_body_with_no_mermaid_diagram
it_should_fail_a_body_whose_second_diagram_is_broken_after_a_valid_first_one
it_should_fail_with_an_install_hint_when_mmdc_is_not_installed
it_should_exit_1_when_the_file_does_not_exist
it_should_exit_1_when_called_with_no_argument

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
