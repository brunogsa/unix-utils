# Writing acceptance criteria

Read once by the authoring agent while filling in `assets/spec-template.md`. Rules only — the skeleton carries none, so they live here.

Never copy guidance text from this or the template into the written doc — the doc holds content only.

## Body/appendix contract

The human body is everything above the literal `# Appendix` heading. It ends there, and every section below is AI-only.

Appendix `## ` headings come heading-first, with a `<details>` collapsible inside — never wrapping an entire heading. Every heading keeps its exact text and level, so grepping `## ` still finds each section.

## Size guideline

Keep the human body (everything above `# Appendix`) to 1–6 pages (~500–3,000 words) depending on the problem; simpler and shorter is better. This is a soft guideline, never a gate.

Keep each AC's Given/When/Then body to ≤128 words — roughly the 70th percentile of what specs already write, so this tightens existing practice instead of inventing new discipline.

A flat file-wide cap punishes a large spec or sits meaningless on a small one; a per-AC cap scales with the feature and still catches one bloated AC in an otherwise-compliant file.

## User Stories

Pattern: `As a <role>, I want <capability> so that <benefit>.` — one per bullet.

## Non-Functional and Technical Requirements

Prompt: performance, security, module reuse. Instantiate what applies, skip the rest.

## Given/When/Then

Include `Given` only when omitting it would make the scenario ambiguous (e.g., DB seeded with specific state, feature flag value, prior request).

Skip it for simple input → output assertions on stateless endpoints.

`Then` must be a concrete, checkable assertion — a return value, status code, state change, or emitted event.

Never use subjective language like "works correctly", "behaves as expected", or "handles it properly" — a vague `Then` can't be proven false, so it can't drive a test.

Self-review rejects any AC whose `Then` isn't independently checkable without asking the author what they meant.

Coverage rule: every spec needs happy path + corner cases + failure modes. The two checklists in the Appendix enforce it — a spec with only happy-path ACs is incomplete.

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

## N/A escapes

Every section keeps its heading even when it doesn't apply — write `N/A — <reason>` as the body instead of deleting the section:

- Context Diagram: for a trivial or no-flow change (one-line config, copy tweak).
- User Stories: when no distinct user role applies, bare `N/A` with no reason clause needed.

Follow the `mermaid-diagrams` skill for the Context Diagram's conventions — lead with a C4L1 context diagram (plus sequence diagrams when a flow needs them), from the perspective of the users in the User Stories and Acceptance Criteria. A validated picture is the fastest way for the reviewer to grasp the system boundary; add prose only for what it can't show.

## Functional Decisions log

Lives in the Appendix. Chronological log, editable during refinement.

Once the user approves the plan and signals execution start, insert the divider line already present in the template and switch to append-only — revisions become new entries with `**Supersedes:**` references rather than in-place edits.

Entries above the divider stay editable until execution starts; afterwards, append below it only.

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist of the choice.

`__Chose__`: approach. `__because__`: reason. `__Discarded__`: alternative plus why it lost. `__Supersedes__`: first ~60 chars of prior entry replaced.
