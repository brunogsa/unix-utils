# Writing Testable Acceptance Criteria

Read alongside `spec-writing.md` while filling in the Testable Acceptance Criteria section of `assets/spec-template.md`.

## Scenario format

Use BDD-style scenarios (Given / When / Then) — one scenario per criterion, each with a short title.

- **When** `<action / request>`
- **Then** `<observable outcome>`
- **And** `<additional assertion, if any>` — optional, only when a second assertion doesn't fit in `Then`.

`Given` is optional too — see "Given/When/Then" below for when to include it.

## Given/When/Then

Include `Given` only when omitting it would make the scenario ambiguous (e.g., DB seeded with specific state, feature flag value, prior request).

Use `Given` when load-bearing — the state it carries is what makes the title's `While` clause load-bearing too; a title claiming a precondition with no `Given` backing it is unverifiable.

Skip it for simple input → output assertions on stateless endpoints.

`Then` must be a concrete, checkable assertion — a return value, status code, state change, or emitted event.

Never use subjective language like "works correctly", "behaves as expected", or "handles it properly" — a vague `Then` can't be proven false, so it can't drive a test.

Self-review rejects any AC whose `Then` isn't independently checkable without asking the author what they meant.

Coverage rule: every spec needs happy path + corner cases + failure modes. The two checklists in the Appendix enforce it — a spec with only happy-path ACs is incomplete.

Group ACs by category for scannability — Happy path / Corner cases / Failure modes — each its own subheading.

## Collapsed AC body

Each AC entry's EARS title (see below) stays visible in the body — it's what a scan-only read needs. The Given/When/Then scenario goes collapsed underneath it, inside a `<details><summary>Scenario</summary>` block, so the body stays scannable while the concrete example values remain one click away.

## EARS titles

Write each AC's title as one EARS (Easy Approach to Requirements Syntax, <https://alistairmavin.com/ears/>) sentence summarizing the entire Given/When/Then body — not just naming the scenario.

Readers scan titles only and open the body when they need detail, so a title that omits the outcome loses exactly what a scan-only read needs.

Only the title is EARS — the Given/When/Then body keeps the concrete example values, which EARS has no slot for.

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

## Coverage checklists

Both the boundary checklist (corner cases) and the failure-category checklist (failure modes) live in the Appendix, under Coverage Checklists, and share one rule, stated once here instead of twice in the template.

Instantiate one row per item in the corner-cases list (boundary checklist) or the failure-modes list (failure-category checklist) of the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`) — e.g. empty/single/many/max-size/overflow, null/undefined/missing, boundary numbers for the boundary checklist; validation error (4xx), downstream timeout/5xx, partial failure for the failure-category checklist.

Mark each row either `covered (<recap of the covering AC>)` or `N/A — <one-word reason>`.

An unevaluated or partially-instantiated checklist fails self-review.

Opt-out: replace either checklist with `**DECISION:** Skip <boundary|failure-category> checklist because <reason>` when the spec is trivially scoped (e.g., one-line config change) or N/A applies wholesale.
