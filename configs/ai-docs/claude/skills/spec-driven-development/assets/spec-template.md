# Spec: [Title]

---
## Background / Context
Why this change is needed. Business context, pain point, or opportunity.

---
## Goals and Success Metrics / KPIs
What we want to achieve (outcomes, not implementation).

---
## Context Diagram

> **Lead with the diagram** — a C4L1 context diagram (plus sequence diagrams when a flow needs them), from the perspective of the users in the User Stories and Acceptance Criteria below.
>
> A validated picture is the fastest way for the reviewer to grasp the system boundary; add prose only for what it can't show.
>
> N/A escape: for a trivial or no-flow change (one-line config, copy tweak), write "N/A — <reason>" and skip the diagram.
>
> Follow the `mermaid-diagrams` skill for conventions.

---
## User Stories

N/A escape: when no distinct user role applies, write bare `N/A` — no reason clause needed.

- As a [role], I want [capability] so that [benefit].

---
## Non-Functional and Technical Requirements
1. Performance: ...
2. Security: ...
3. Reuse module X ...

---
## Testable Acceptance Criteria

Use BDD-style scenarios (Given / When / Then). One scenario per criterion, each with a short title.

**Rule for `Given`:** include it only when removing it would make the scenario ambiguous (e.g., DB seeded with specific state, feature flag value, prior request).

For simple input → output assertions on stateless endpoints, skip `Given`.

**Coverage rule:** happy path + corner cases + failure modes — the checklists below enforce it; a spec with only happy-path ACs is incomplete.

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

**Boundary checklist** — instantiate one row per item in the corner-cases list of the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`).

Illustrative rows (full list in the taxonomy):

- empty / single / many / max-size / overflow:
- null / undefined / missing:
- boundary numbers (0, -1, MAX_INT, off-by-one):

Mark each row either `covered (<recap of the covering AC>)` or `N/A — <one-word reason>`. An unevaluated or partially-instantiated checklist fails self-review.

Opt-out: replace the checklist with `**DECISION:** Skip boundary checklist because <reason>` when the spec is trivially scoped (e.g., one-line config change).

### AC-N: ...

#### Failure modes

**Failure category checklist** — instantiate one row per item in the failure-modes list of the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`).

Illustrative rows (full list in the taxonomy):

- validation error (4xx):
- downstream timeout / 5xx:
- partial failure (some items succeed, some fail):

Mark each row `covered (<recap of the covering AC>)` or `N/A — <one-word reason>`. An unevaluated or partially-instantiated checklist fails self-review.

Opt-out: replace with `**DECISION:** Skip failure-category checklist because <reason>` when N/A applies wholesale.

### AC-N: ...

---
## Open Questions
- **QUESTION:** ... ?

---
## Functional Decisions

Chronological log. Editable during refinement.

Once the user approves the plan and signals execution start, insert the divider line below and switch to append-only.

Revisions become new entries with `**Supersedes:**` references rather than in-place edits.

- **DECISION:** __Chose__ <approach>, __because__ <reason>
  - __Discarded__ **<alternative>**: <reason>

<!-- ── execution begins below; entries above are frozen, append-only below ── -->

- **DECISION (Task N):** __Chose__ <approach>, __because__ <reason>
  - __Supersedes__ "<first ~60 chars of prior decision>" __because__ <reason>
