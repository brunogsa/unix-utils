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
> N/A escape: for a trivial or no-flow change (one-line config, copy tweak), write "N/A — `<reason>`" and skip the diagram.
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

**Title rule:** write the title as one EARS sentence summarizing the entire Given/When/Then body, not just naming the scenario.
Readers scan titles only and open the body when they need detail, so a title that omits the outcome loses exactly what a scan-only read needs.

EARS (Easy Approach to Requirements Syntax, <https://alistairmavin.com/ears/>) fixes the keyword and the clause order, so every title states trigger, actor, and outcome in the same shape:

| Pattern | Template | Reach for it when |
|---|---|---|
| Event-driven | `When <trigger>, the <system> shall <response>` | something happens and the system responds — most happy-path ACs |
| Unwanted behaviour | `If <trigger>, then the <system> shall <response>` | the trigger is an error, a violation, or anything undesired |
| State-driven | `While <precondition>, the <system> shall <response>` | the behavior holds only during a state, with no discrete trigger |
| Ubiquitous | `The <system> shall <response>` | an always-on invariant, true with no precondition at all |
| Optional feature | `Where <feature is included>, the <system> shall <response>` | the behavior exists only when a flag or optional module is on |

Combine when both apply: `While <precondition>, when <trigger>, the <system> shall <response>`.

`<system>` is the concrete unit under test — the sync job, the `POST /agreements` handler, the retry wrapper — never a bare "the system".

- Bad: `AC-3: Expired token` — names a scenario, states no outcome, and hides whether this is the happy path or a failure.
- Good: `AC-3: If the stored token is expired, then the sync job shall refresh it once before retrying` — trigger, actor, and outcome, and `If` marks it as unwanted behaviour.

**Only the title is EARS** -- the Given/When/Then body below it keeps the concrete example values, which EARS has no slot for.

**Then rule:** the outcome must be a concrete, checkable assertion — such as a return value, status code, state change, or emitted event.
Never use subjective language like "works correctly", "behaves as expected", or "handles it properly".
A vague `Then` can't be proven false, so it can't drive a test; self-review rejects any AC whose `Then` isn't independently checkable without asking the author what they meant.

Format:

### AC-N: When `<trigger>`, the `<system>` shall `<response>`
- **When** `<action / request>`
- **Then** `<observable outcome>`
- **And** `<additional assertion, if any>`

Use **Given** when load-bearing — the state it carries is what makes the title's `While` clause load-bearing too:

### AC-N: While `<precondition>`, when `<trigger>`, the `<system>` shall `<response>`
- **Given** `<state that must hold before the action>`
- **When** `<action>`
- **Then** `<observable outcome>`

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

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist.

<details>
<summary><strong>DECISION:</strong> &lt;one-line gist of the choice&gt;</summary>

- **DECISION:** __Chose__ `<approach>`, __because__ `<reason>`
  - __Discarded__ **`<alternative>`**: `<reason>`

</details>

<!-- ── execution begins below; entries above are frozen, append-only below ── -->

<details>
<summary><strong>DECISION (Task N):</strong> &lt;one-line gist of the choice&gt;</summary>

- **DECISION (Task N):** __Chose__ `<approach>`, __because__ `<reason>`
  - __Supersedes__ "`<first ~60 chars of prior decision>`" __because__ `<reason>`

</details>
