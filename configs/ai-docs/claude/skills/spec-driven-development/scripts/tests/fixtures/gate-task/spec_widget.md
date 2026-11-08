# Spec: Widget export

## Background / Context

The widget export button never worked for large batches.

## Goals and Success Metrics / KPIs

Export completes for batches up to 10k rows.

## Context Diagram

N/A - no new external integration.

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

N/A - no open question; the row cap is fixed at 10k.

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
