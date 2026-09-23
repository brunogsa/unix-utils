#!/usr/bin/env bash
# test-new-shape-fixtures.sh - a new-shape spec/plan pair still
# reads through every location-agnostic gate.

# "New-shape" means Appendix-reshaped: every AI-only section
# sits after a literal "# Appendix" line.

# These gates key off a body-side "## " heading (Task
# Breakdown, PR Breakdown, Test Design, Open Questions,
# Testable Acceptance Criteria).

# Those headings stay on the body side of the Appendix line,
# so none of these gates needed a change for the reshape.

# check-coverage-checklists.sh and check-ac-task-consistency.py
# are deliberately absent here.

# Both read fields the reshape moved into the Appendix (the
# AC-category checklists, and a task's Testable Acceptance
# criteria), so both fail on this same fixture today.

# Their own test suites carry the RED->GREEN cycle that fixes
# them.
#
# Usage:
#   bash test-new-shape-fixtures.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.

# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

sdd_scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
implement_scripts_dir="$(cd "$sdd_scripts_dir/../../implement/scripts" && pwd)"
hooks_dir="$(cd "$sdd_scripts_dir/../../../hooks" && pwd)"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
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

# assert_contains - asserts the haystack mentions the given
# substring.
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

# A realistic new-shape pair: every H2 section the templates
# prescribe, in order, with "# Appendix" splitting the human
# body from the AI-only Coverage Checklists / Task Details /
# Decisions sections.
spec_file="$work_dir/spec_widget.md"
cat > "$spec_file" <<'EOF'
# Spec: Widget export

## Background / Context

The widget export button never worked for large batches.

## Goals and Success Metrics / KPIs

Export completes for batches up to 10k rows.

## Context Diagram

N/A — no new external integration.

## User Stories

- As an operator, I want to export a large widget batch so that I can share it offline.

## Non-Functional and Technical Requirements

1. Performance: export completes under 30s for 10k rows.

## Testable Acceptance Criteria

#### Happy path

### AC-1: When the operator requests an export, the system shall stream the file
<details>
<summary>Scenario</summary>

- **Given** a batch of widgets
- **When** the operator clicks export
- **Then** the system streams a CSV file

</details>

#### Corner cases

### AC-2: When the batch is empty, the system shall return an empty file
<details>
<summary>Scenario</summary>

- **Given** an empty batch
- **When** the operator clicks export
- **Then** the system returns a header-only CSV

</details>

#### Failure modes

### AC-3: If the batch exceeds the row cap, then the system shall reject the export
<details>
<summary>Scenario</summary>

- **Given** a batch above the row cap
- **When** the operator clicks export
- **Then** the system returns a 413 error

</details>

## Open Questions

N/A — no open question; the row cap is fixed at 10k.

# Appendix

## Coverage Checklists

### Boundary checklist

**DECISION:** Skip boundary checklist because this fixture only probes section placement.

### Failure category checklist

**DECISION:** Skip failure-category checklist because this fixture only probes section placement.

## Functional Decisions

<details>
<summary><strong>DECISION:</strong> stream instead of buffer</summary>

- **DECISION:** __Chose__ `streaming CSV writer`, __because__ `bounded memory use`
  - __Discarded__ **`buffer then write`**: `unbounded memory on 10k rows`

</details>
EOF

plan_file="$work_dir/plan_widget.md"
cat > "$plan_file" <<'EOF'
# Plan: Widget export

Spec: spec_widget.md

## Technical Approach & High Level Architecture

Stream a CSV from the widgets table.

## Threat Model

- [x] permissions change (who can see/do what)

N/A — export is read-only, reuses the existing export permission.

## General Flow

Operator clicks export -> server streams CSV.

## Test Design

```
// widget-export
describe("WidgetExportUseCase", () => {
  // Happy cases
  it("should stream a CSV file when the operator requests an export");    // AC-1 T1
  // Corner cases
  it("should return a header-only CSV when the batch is empty");   // AC-2 T1
  // Failure scenarios
  it("should return a 413 when the batch exceeds the row cap");  // AC-3 T2
});
```

## Task Breakdown

### 1. Stream the CSV writer

**Depends on**: none

**Brief Description**: Add the streaming CSV writer and wire the happy/corner paths.

**Commits (sketch, minimum)**:
  1. `~/repo` — `feat(widget-export): stream CSV for a batch`

### 2. Reject over-cap batches

**Depends on**:
- Task 1

**Brief Description**: Add the row-cap check and 413 response.

**Commits (sketch, minimum)**:
  1. `~/repo` — `feat(widget-export): reject batches over the row cap`

## PR Breakdown

### PR-1. [ ] Widget export streaming

**Tasks**: 1, 2

**Depends on**: none

**Branch**: `feat/widget-export-stream`

## Open Questions

N/A — no open question; streaming covers the full range without pagination.

# Appendix

## Task Details

<details>
<summary>Task 1 — Stream the CSV writer</summary>

**Testable Acceptance criteria**:
- AC-1
- AC-2

**Verification**:
- `npm test -- widget-export`

**Files (logical order)**:
- `src/widget-export/stream.ts`

</details>

<details>
<summary>Task 2 — Reject over-cap batches</summary>

**Testable Acceptance criteria**:
- AC-3

**Verification**:
- `npm test -- widget-export`

**Files (logical order)**:
- `src/widget-export/cap-check.ts`

</details>

## Technical Decisions

<details>
<summary><strong>DECISION:</strong> row cap at 10k</summary>

- **DECISION:** __Chose__ `10k row cap`, __because__ `matches the spec's KPI`
  - __Discarded__ **`unbounded`**: `unbounded memory risk`

</details>
EOF

it_should_pass_open_questions_on_both_new_shape_docs() {
  local out rc
  out=$(bash "$sdd_scripts_dir/check-open-questions.sh" "$plan_file" "$spec_file" 2>&1)
  rc=$?
  assert_eq "check-open-questions.sh should pass on the settled new-shape pair" "0" "$rc"
}

it_should_pass_ac_coverage_on_the_new_shape_pair() {
  local out rc
  out=$(bash "$sdd_scripts_dir/check-ac-coverage.sh" "$plan_file" "$spec_file" 2>&1)
  rc=$?
  assert_eq "check-ac-coverage.sh should pass on the new-shape pair (exit code)" "0" "$rc"
  assert_contains "check-ac-coverage.sh should confirm all 3 ACs annotated" "all 3 spec ACs are annotated" "$out"
}

it_should_pass_tasks_dag_on_the_new_shape_plan() {
  local out rc
  out=$(bash "$sdd_scripts_dir/check-tasks-dag.sh" "$plan_file" 2>&1)
  rc=$?
  assert_eq "check-tasks-dag.sh should pass on the new-shape plan's Task Breakdown" "0" "$rc"
}

it_should_pass_pr_dag_on_the_new_shape_plan() {
  local out rc
  out=$(bash "$sdd_scripts_dir/check-pr-dag.sh" "$plan_file" 2>&1)
  rc=$?
  assert_eq "check-pr-dag.sh should pass on the new-shape plan's PR Breakdown" "0" "$rc"
}

it_should_pass_test_distribution_on_the_new_shape_plan() {
  local out rc
  out=$(bash "$sdd_scripts_dir/check-test-distribution.sh" "$plan_file" 2>&1)
  rc=$?
  assert_eq "check-test-distribution.sh should pass on the new-shape plan" "0" "$rc"
}

it_should_resolve_task_order_from_the_new_shape_task_breakdown() {
  local out rc
  out=$(bash "$implement_scripts_dir/resolve-task-order.sh" "$plan_file" "1,2" 2>&1)
  rc=$?
  assert_eq "resolve-task-order.sh should read the new-shape Task Breakdown (exit code)" "0" "$rc"
  assert_eq "resolve-task-order.sh should return the requested task order" "1, 2" "$out"
}

it_should_pass_pr_dependencies_ready_on_a_root_pr_in_the_new_shape_plan() {
  local out rc
  out=$(bash "$implement_scripts_dir/check-pr-dependencies-ready.sh" "$plan_file" PR-1 "$work_dir" 2>&1)
  rc=$?
  assert_eq "check-pr-dependencies-ready.sh should pass on a root PR (no parents)" "0" "$rc"
}

it_should_parse_the_new_shape_pr_breakdown_row() {
  local out rc
  out=$(bash "$implement_scripts_dir/parse-pr-breakdown.sh" "$plan_file" 2>&1)
  rc=$?
  assert_eq "parse-pr-breakdown.sh should parse the new-shape PR Breakdown (exit code)" "0" "$rc"
  assert_contains "parse-pr-breakdown.sh should emit the PR-1 row with its Tasks and Branch" "PR-1	1, 2" "$out"
}

it_should_not_block_the_stop_hook_on_a_clean_new_shape_pair() {
  local stop_hook_work rc
  stop_hook_work="$work_dir/stop-hook-clean"
  mkdir -p "$stop_hook_work"
  cp "$spec_file" "$stop_hook_work/spec_widget.md"
  cp "$plan_file" "$stop_hook_work/plan_widget.md"
  out=$(cd "$stop_hook_work" && printf '{}' | bash "$hooks_dir/claude-sdd-stop-hook.sh" 2>&1)
  rc=$?
  assert_eq "claude-sdd-stop-hook.sh should exit 0 on a clean new-shape pair" "0" "$rc"
  assert_eq "claude-sdd-stop-hook.sh should emit nothing on a clean new-shape pair" "" "$out"
}

it_should_block_the_stop_hook_when_an_ac_loses_its_test_design_annotation() {
  local stop_hook_work drifted_plan out decision
  stop_hook_work="$work_dir/stop-hook-drift"
  mkdir -p "$stop_hook_work"
  cp "$spec_file" "$stop_hook_work/spec_widget.md"
  drifted_plan="$stop_hook_work/plan_widget.md"

  # Drop AC-3's annotation so the spec's "### AC-3:" heading
  # (sniffed the same way as before the reshape) has no Test
  # Design citation left.
  sed 's#// AC-3 T2#// T2#' "$plan_file" > "$drifted_plan"
  out=$(cd "$stop_hook_work" && printf '{}' | bash "$hooks_dir/claude-sdd-stop-hook.sh" 2>&1)
  decision=$(printf '%s' "$out" | python3 -c 'import json, sys; print(json.load(sys.stdin)["decision"])' 2>/dev/null)
  assert_eq "claude-sdd-stop-hook.sh should block when a new-shape spec AC loses its Test Design annotation" "block" "$decision"
}

it_should_pass_open_questions_on_both_new_shape_docs
it_should_pass_ac_coverage_on_the_new_shape_pair
it_should_pass_tasks_dag_on_the_new_shape_plan
it_should_pass_pr_dag_on_the_new_shape_plan
it_should_pass_test_distribution_on_the_new_shape_plan
it_should_resolve_task_order_from_the_new_shape_task_breakdown
it_should_pass_pr_dependencies_ready_on_a_root_pr_in_the_new_shape_plan
it_should_parse_the_new_shape_pr_breakdown_row
it_should_not_block_the_stop_hook_on_a_clean_new_shape_pair
it_should_block_the_stop_hook_when_an_ac_loses_its_test_design_annotation

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
