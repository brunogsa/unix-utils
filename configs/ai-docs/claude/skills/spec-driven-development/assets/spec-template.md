# Spec: [Title]

---
## Background / Context
Why this change is needed. Business context, pain point, or opportunity.

---
## Goals and Success Metrics / KPIs
What we want to achieve (outcomes, not implementation).

---
## User Stories
- As a [role], I want [capability] so that [benefit].

---
## Non-Functional and Technical Requirements
1. Performance: ...
2. Security: ...
3. Reuse module X ...

---
## Testable Acceptance Criteria

Use BDD-style scenarios (Given / When / Then). One scenario per criterion, each with a short title.

**Rule for `Given`:** include it only when removing it would make the scenario ambiguous (e.g., DB seeded with specific state, feature flag value, prior request). For simple input → output assertions on stateless endpoints, skip `Given`.

**Coverage rule:** every spec MUST include scenarios for the **happy path**, **corner cases** (empty inputs, boundary values, max sizes, combined filters, idempotency), and **failure modes** (validation errors, downstream timeouts, 4xx/5xx responses, partial failures). A spec with only happy-path ACs is incomplete.

Format:

### AC-N: <short scenario title>
- **When** <action / request>
- **Then** <observable outcome>
- **And** <additional assertion, if any>

Use **Given** when load-bearing:

### AC-N: <stateful scenario title>
- **Given** <state that must hold before the action>
- **When** <action>
- **Then** <observable outcome>

Group by category for scannability:

#### Happy path
### AC-1: ...

#### Corner cases
### AC-N: ...

#### Failure modes
### AC-N: ...

---
## Open Questions
- **QUESTION:** ... ?

---
## Functional Decisions

Chronological log. Editable during refinement. Once the user approves the plan and signals execution start, insert the divider line below and switch to append-only — revisions become new entries with `**Supersedes:**` references rather than in-place edits.

- **DECISION:** __Chose__ <approach>, __because__ <reason>
  - __Discarded__ **<alternative>**: <reason>

<!-- ── execution begins below; entries above are frozen, append-only below ── -->

- **DECISION (Task N):** __Chose__ <approach>, __because__ <reason>
  - __Supersedes__ "<first ~60 chars of prior decision>" __because__ <reason>
