# Writing acceptance criteria

Read once by the authoring agent while filling in `assets/spec-template.md`'s Testable Acceptance Criteria section. Rules only — the copyable skeleton carries no rules, so they live here.

## Given/When/Then

Include `Given` only when omitting it would make the scenario ambiguous (e.g., DB seeded with specific state, feature flag value, prior request).

Skip it for simple input → output assertions on stateless endpoints.

`Then` must be a concrete, checkable assertion — a return value, status code, state change, or emitted event.

Never use subjective language like "works correctly", "behaves as expected", or "handles it properly" — a vague `Then` can't be proven false, so it can't drive a test.

Self-review rejects any AC whose `Then` isn't independently checkable without asking the author what they meant.

Coverage rule: every spec needs happy path + corner cases + failure modes. The two checklists below enforce it — a spec with only happy-path ACs is incomplete.

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

## Size guide

Keep each AC's Given/When/Then body to ≤128 words — roughly the 70th percentile of what specs already write, so this tightens existing practice instead of inventing new discipline.

A flat file-wide cap either punishes a legitimate 44-criterion spec or sits meaningless on a 5-criterion one.

A per-AC cap scales with the feature instead, and still catches one bloated AC hiding inside an otherwise-compliant file.

Total spec body word count — everything except the appendix, the Functional/Technical Decisions log, and the fenced Test Design block — is a split signal, not a gate, at 4,096 words.

Past it, open a PR-split conversation — it's a signal to split, never a hard fail.

## Coverage checklists

Both the boundary checklist (corner cases) and the failure-category checklist (failure modes) share one rule, stated once here instead of twice in the template.

Mark each row either `covered (<recap of the covering AC>)` or `N/A — <one-word reason>`.

An unevaluated or partially-instantiated checklist fails self-review.

Opt-out: replace either checklist with `**DECISION:** Skip <boundary|failure-category> checklist because <reason>` when the spec is trivially scoped (e.g., one-line config change) or N/A applies wholesale.
