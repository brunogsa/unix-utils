# Plan: Widget export

Spec: spec_widget.md

## Technical Approach & High Level Architecture

Stream a CSV from the widgets table.

## Threat Model

- [x] permissions change (who can see/do what)

N/A - export is read-only, reuses the existing export permission.

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

**Tests (planned)**: the two export tests in Test Design.

**Commits (sketch, minimum)**:
  1. `~/repo` - `feat(widget-export): stream CSV for a batch`

### 2. Add the row-cap setting

**Depends on**:
- Task 1

**Brief Description**: Add the configurable row-cap setting the export reads.

**Tests (planned)**: covered by the Task 4 cap test.

**Commits (sketch, minimum)**:
  1. `~/repo` - `feat(widget-export): add the row-cap setting`

### 3. [Gate] Prove on Stage that a 10k-row export finishes under 30s

**Depends on**: none

**Brief Description**: Run one 10k-row export on Stage and record its duration in the evidence file.

**Tests (planned)**: N/A - gate task, no code

### 4. Reject over-cap batches

**Depends on**:
- Task 2
- Task 3

**Brief Description**: Add the row-cap check and 413 response.

**Commits (sketch, minimum)**:
  1. `~/repo` - `feat(widget-export): reject batches over the row cap`

## PR Breakdown

### PR-1. [ ] Widget export streaming

**Tasks**: 1, 2

**Depends on**: none

**Branch**: `feat/widget-export-stream`

### PR-2. [ ] Widget export row cap

**Tasks**: 4

**Depends on**: PR-1

**Gates**: Task 3

**Branch**: `feat/widget-export-cap`

## Open Questions

N/A - no open question; streaming covers the full range without pagination.

# Appendix

## Task Details

<details>
<summary>Task 1 - Stream the CSV writer</summary>

**Testable Acceptance criteria**:
- AC-1
- AC-2

**Verification**:
- `npm test -- widget-export`

**Files (logical order)**:
- `src/widget-export/stream.ts`

</details>

<details>
<summary>Task 2 - Add the row-cap setting</summary>

**Testable Acceptance criteria**:
- AC-3

**Verification**:
- `npm test -- widget-export`

**Files (logical order)**:
- `src/widget-export/row-cap-setting.ts`

</details>

<details>
<summary>Task 3 - Prove on Stage that a 10k-row export finishes under 30s</summary>

**Testable Acceptance criteria**:
- one Stage export of 10k rows finishes under 30s

**Verification**:
- the evidence file holds the export's request and its duration

</details>

<details>
<summary>Task 4 - Reject over-cap batches</summary>

**Testable Acceptance criteria**:
- AC-3

**Verification**:
- `npm test -- widget-export`

**Files (logical order)**:
- `src/widget-export/cap-check.ts`

</details>

## Files to Create or Modify

<details>
<summary>Files union</summary>

- `src/widget-export/stream.ts`
- `src/widget-export/row-cap-setting.ts`
- `src/widget-export/cap-check.ts`

</details>

## Technical Decisions

<details>
<summary><strong>DECISION:</strong> row cap at 10k</summary>

- **DECISION:** __Chose__ `10k row cap`, __because__ `matches the spec's KPI`
  - __Discarded__ **`unbounded`**: `unbounded memory risk`

</details>
