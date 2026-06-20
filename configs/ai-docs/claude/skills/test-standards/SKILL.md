---
name: test-standards
description: "USE PROACTIVELY whenever you write, edit, or review tests — choosing test type (unit/integration/e2e), mocking, flakes, coverage gaps, regression tests, test titles. Any test edit, not pure reading."
user-invocable: false
words-budget: 5096
instructions-budget: 60
---

# Test Standards

Principles for any test work. Each section pairs a principle with its WHY, with paired examples co-located under the principle.

## Default to integration tests; test behaviour, not implementation

[Instruction] Black-box by nature. Mock at external/IO boundaries (DB, HTTP, queues, file system).

[Why] Integration tests survive internal refactors and exercise the path the caller actually takes.

Unit tests pinned to implementation must be refactored alongside the code they pin — the test stops protecting you the moment you most need it.

- [Instruction] Prefer fakes and localstack-style emulators to bare mocks where the cost is reasonable.
- [Instruction] **Unit tests for leaf functions/modules** (parsers, normalizers, validators, formatters) — whitebox; expect tests to change with implementation. Skip when the only "unit" is a thin glue function.
- [Instruction] **E2E tests sparingly** — slow and brittle; flakiness erodes trust in the suite. Acceptable when the specific case is cheap (existing fixture, single happy-path Playwright run, smoke test).
- [Instruction] **Manual tests** when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox). Log per `test-driven-development` format.

## Each layer independently exercises its functionality — overlap cheap, gaps not

[Instruction] **CRITICAL: Each test layer (unit / integration/router / e2e/browser) independently exercises the functionality it owns. Don't drop a layer's coverage on the grounds that another layer covers it.**

[Why] In the AI era overlapping tests are cheap; gaps justified by cross-layer reliance ship undetected when the "covering" layer diverges. Prefer visibly-redundant tests (user prunes) over quietly-uncovered layers.

## Gold rule: automate what a human would manually do to verify

[Instruction] Before writing tests, ask: "if I had to verify this change by hand, what steps would I take?" — then automate that list.

Applies to backend (API calls, payloads, DB states) and frontend (clicks, inputs, page states) equally — the human verification checklist is the same shape regardless of layer.

[Why] Coverage tools answer "is this line touched?" — they cannot answer "would a manual tester have noticed this?". The manual-verification checklist is the test checklist.

Concrete patterns this rule generates:

- [Instruction] **Cover every variant** — N variants of the same kind = N tests (directly or via parametrization). Coverage on one says nothing about the others.
  - [Examples] Variant kinds: input fields, filters, query params, tabs, entity types, view modes, browser sizes.
  - [Examples] The "one example, infer the rest" heuristic fails the moment behavior diverges.
- [Instruction] **Boundary on caps/limits** — a cap of N gets an explicit N+1 test (send N+1 of the limited thing and prove the cap engages). Happy-path-only leaves the invariant unverified.
- [Instruction] **Async safety / idempotency** — disabled-during-fetch (UI), idempotency keys (API), retry-resistant operations — the actions a manual tester would re-fire need explicit tests.
- [Instruction] **Three-branch dependency outcome** — success, error response, AND timeout/never-responds. Missing the timeout branch leaves a real production gap (UI stays loading forever; backend leaks resources).
- [Instruction] **Inverse cache branch** — when set-and-fetch is tested, test clear-and-restore (or invalidate-and-refetch). Partial cache coverage is a known footgun.
- [Instruction] **Observably-non-empty BEFORE and AFTER** — for filter/transition tests (UI or API), baseline and final state must both be non-empty.
  - [Examples] Empty-to-something only proves the filter renders/returns something — not that it changes meaningfully.

## Design test titles before implementation

[Instruction] Write titles (no bodies), review them, then run RED-GREEN.

[Why] Titles capture the contract before the code locks it in.

Writing tests AFTER you "see what works" shapes the test to whatever you ended up writing — the test stops being a contract.

- [Instruction] Applies upfront to integration tests and pre-known pure helpers, and again at each helper pulled on demand — designing them all upfront forces premature signatures.
- [Instruction] Commit tests together with their implementation — never titles alone.
- [Instruction] For scripts: usage syntax + examples in the comment header.

## Descriptive titles (BDD-like)

[Instruction] Test titles read as behavior documentation in domain vocabulary — observable behavior, not internal field names or implementation tokens.

[Why] Titles get scanned a hundred times more than test bodies.

A title coupled to an internal field name breaks the moment the field is renamed even when behavior is identical; a domain-language title survives.

[Instruction] **No spec/plan/AC refs in test titles** — see CLAUDE.md ("Self-describing artifacts — no context-dependent shorthand"). Same rule applies to test titles.

**Anti-pattern: generic noun when multiple instances of the same kind exist**

[Instruction] When a system has multiple instances of the same kind — two search fields, two filters, two query params, two endpoints — name the specific one in the title.

Generic nouns invite confusion.

[Examples]
```
Bad:  "should AND fieldA IN with fieldB NOT IN when both provided"   (operator mechanics)
Bad:  "regression: PR #2034 last-spread-wins on flowCode"            (session/branch history)
Good: "should subtract excludeFlowCodes from the flowCode include set when both filters are provided"
```

```ts
// Bad — spec-tracking refs in test titles
it('should throw INTERNAL_SERVER_ERROR when getSalesAgreements throws after retries (AC-18)', ...);
it('should emit the structured procedure-entry log per Req 21', ...);

// Good
it('should throw INTERNAL_SERVER_ERROR when getSalesAgreements throws after retries', ...);
```

```ts
// Bad — generic noun; page has two searches (school name + externalId); which one?
it('should NOT re-fire schoolsAgreements when search changes (cache hit)', ...);

// Good — names the specific control:
it('should NOT re-fire schoolsAgreements when externalId search changes (cache hit)', ...);
```

```ts
// Bad — implementation token in title (leaks internal field name)
it('should count agreements with errorOnSkusFetch toward Acordos carregados total', ...);

// Good — domain language, decoupled from implementation
it('should count agreements whose SKUs fetch failed toward the Acordos carregados total', ...);
```

**Anti-pattern: internal-state predicate instead of operator-language behavior**

[Instruction] Test titles describe observable behavior in operator/domain language a non-engineer (PM, QA, designer) could understand.

[Why] Internal-state predicates, codebase tokens, and clean-code assertions about names don't describe behavior — they force the reader to reconstruct the mental model the test was written against.

[Examples]
```ts
// Bad — internal-state expressed as a logical formula
it('should enable Aplicar when pending is empty but applied is non-empty (clear-to-zero is a real commit, not a no-op)', ...);

// Bad — codebase token leaks into the title
it('should render the filtered table sourced from list-with-IDs once the school batch resolves', ...);

// Bad — clean-code assertion (not behavior)
it('should keep the fast-default empty placeholder name distinct from the school-scoped one', ...);

// Good — behavior in operator/domain language
it('should enable Aplicar after the operator clears the school selection so the cleared state can be committed back to no filter', ...);
it('should filter the active-tab table by agreementIds once the school batch resolves in slow mode', ...);
```

## Test titles encode the FULL precondition, not happy-path only

[Instruction] The form `should X when Y` implies Y is the only precondition.

[Instruction] If the assertion holds only when `Y AND Z`, the title must say so — `should X when Y, only when not Z` — or split into separate tests if cleaner.

[Why] A title is a tiny spec.

An incomplete title fails to document the conjunctive constraint — readers learn the wrong contract, and the test stops being a guard for the missing precondition.

[Examples]
```ts
// Bad — incomplete precondition (only true when loading=false)
it('should enable Apply after operator toggles a school off then back on', ...);

// Good — full precondition
it('should enable Apply after operator toggles a school off then back on, only when not loading', ...);
it('should disable Apply while loading (loading dominates dirty state)', ...);
```

## Bug fix starts with a failing regression test

[Instruction] See `debug-standards` for the full rule.

## Deterministic & self-contained

[Instruction] No shared state, no randomness, clone inputs when testing mutating functions. Pin the clock with fake timers when the system under test reads it — directly or via helpers.

[Why] Flaky tests erode trust.

A test that passes 9 times and fails the 10th is worse than no test — engineers learn to rerun instead of investigate, and real failures get ignored.

- [Instruction] Time-derived tests without a frozen clock are time-bombs — they pass today and silently fail in N months when wall-clock crosses a threshold.
- [Instruction] Apply when test names contain "past", "future", "expired", "min", "cap", "deadline" — wall-clock-sensitive vocabulary.

## Observed test flakes always become Scouts

[Instruction] Any observed test flake — intermittent failure, OOM, timing race — queues a Scout immediately, even when the root cause is unclear at observation time.

Uses the Scout mechanism from CLAUDE.md's Scout rule (auto-add as `[Scout]`).

[Why] Flakiness compounds — each ignored instance erodes signal in the suite, so the "next" failure can't be trusted as a real regression.

"Not my problem today" becomes "the suite stops guarding tomorrow."

## Mock sparingly

[Instruction] Justify each mock; the only mocks worth keeping are at the external/IO boundaries defined under "Default to integration tests".

[Why] Every mock is a hypothesis about what the dependency does.

If the hypothesis drifts from reality, the test passes while production breaks.

## Use real-like mock data

[Instruction] Use realistic-looking values in mock data (real-shaped names, emails, IDs, dates) — not placeholder fragments.

[Why] Cryptic mock data (`name: "x"`, `email: "a@b"`) hides bugs that show up only with realistic shapes (encoding, length, casing). Real-like data catches real-like bugs.

## Don't re-implement logic under test

[Instruction] Let the system under test do the work — the test must encode an independent expectation, not recompute what the code does.

[Why] If the test reproduces the logic, both move together: a bug in the production logic is mirrored in the test, and the test passes anyway.

[Examples]
```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```

## Remove redundant / tautological tests

[Instruction] When a new test exercises the same code path with the same inputs as an existing one, remove the duplicate or merge.

[Why] Two tests asserting the same thing don't improve safety — they slow the suite, double the maintenance burden, and create false confidence.

Schema example: if "max 10" is enforced, one test at 11 covers it; tests at 12, 15, 100 are redundant. Boundary + 1 is the contract.

## One test per distinct cause

[Instruction] Isolate each independent trigger for a behavior. Different inputs that exercise the same code path are one test, not two.

[Why] Distinct causes are the unit of safety. If two test cases hit the same production code path, the second adds maintenance with no extra coverage.

## Split tests that assert more than one behavior

[Instruction] One `it` = one assertion of behavior. A title joined by "and" or covering two independent observable behaviors splits into two tests.

[Why] Compound assertions hide which half broke when the test fails — the reader has to re-read the body to recover which.

[Why] Splitting forces sharper titles — each half names its own observable behavior; the test surface becomes a per-behavior index.

[Examples]
```ts
// Bad — compound assertion, hides which half failed
it('should render entity tabs and active-tab table on cold mount', ...);
it('should filter the table by agreementIds (or skus for the product tab)', ...);
it('should re-derive per-tab badges and the brand-selector dropdown', ...);

// Good — one observable behavior per test
it('should render the entity tabs on cold mount', ...);
it('should render the active-tab table on cold mount', ...);
it('should filter the sales-agreement tab table by agreementIds', ...);
it('should filter the product tab table by skus', ...);
it('should re-derive per-tab badges from school-scoped summary calls', ...);
it('should re-derive the brand-selector dropdown options from school-scoped summary calls', ...);
```

## When N triggers share one outcome, test the outcome

[Instruction] When multiple events produce the same outcome — different filters reset the page, different mutations invalidate one cache, different errors roll back one transaction — write ONE test asserting the outcome.

[Instruction] Don't write N tests one-per-trigger when all paths lead to the same final state.

[Why] N specific tests grow linearly with each new trigger and silently miss the next one added.

A test of the outcome itself ("any refetch resets page to 1") inherits coverage automatically when new triggers join.

- [Instruction] **vs. "Remove redundant tests"** — that rule fires on identical assertions; this rule fires when triggers differ but outcome doesn't.
- [Instruction] **vs. "One test per distinct cause"** — that rule fires when causes have independent production branches; this rule fires when triggers share one production branch.

[Examples]
```ts
// Bad — three tests, one per trigger, all asserting the same behavior:
it('should reset page to 1 when status filter changes', ...);
it('should reset page to 1 when search input changes', ...);
it('should reset page to 1 when sort order changes', ...);

// Good — one test of the underlying invariant:
it('should reset page to 1 on every refetch of the dataset', ...);
```

## Don't test log presence

[Instruction] Log emission is not behavior the caller observes.

[Why] Log assertions are brittle (break when format evolves), tautological (mirror impl), and clutter the suite.

Testing the behavior that produced the log carries the same signal without the brittleness.

[Instruction] **Exception**: when a log is an external contract (audit log consumed by another system, structured event for analytics), test the payload shape — that's contract testing, not log presence testing.

## Group tests by intent: happy path, corner cases, failure scenarios

[Instruction] Group tests by intent — happy path, corner cases, failure scenarios — using nested describe blocks.

[Why] Readers scanning "what does this do when it works?" should not wade through error paths. Grouping by intent makes the contract scannable at a glance.

[Examples]
```ts
// Bad — mixed
describe('contractValidation.getSchoolsAgreementsAndSkus', () => {
  it('returns agreements + SKUs for valid input', ...);
  it('throws BAD_REQUEST when no schools provided', ...);
  it('attaches SKU codes returned by getSKUs', ...);
  it('throws INTERNAL_SERVER_ERROR after retries', ...);
});

// Good — split
describe('contractValidation.getSchoolsAgreementsAndSkus', () => {
  describe('happy path', () => {
    it('returns agreements + SKUs for valid input', ...);
    it('attaches SKU codes returned by getSKUs', ...);
  });

  describe('failure scenarios', () => {
    it('throws BAD_REQUEST when no schools provided', ...);
    it('throws INTERNAL_SERVER_ERROR after retries', ...);
  });
});
```

## Avoid order-dependent assertions

[Instruction] Tests should not break when the implementation changes the order of items in a collection, unless order is part of the contract.

[Why] Asserting on exact array order couples tests to implementation details. A refactor that changes iteration order shouldn't break a behavior test.

[Examples]
```ts
// Bad -- breaks if implementation reorders items:
expect(result).toEqual([
    { sku: 'CHILD-1', price: 100 },
    { sku: 'KIT-1', price: 300 },
]);

// Good -- asserts membership and count, order-independent:
expect(result).toHaveLength(2);
expect(result).toEqual(expect.arrayContaining([
    expect.objectContaining({ sku: 'CHILD-1', price: 100 }),
    expect.objectContaining({ sku: 'KIT-1', price: 300 }),
]));
```

## Fixtures must support every state the tests assert on

[Instruction] When a single fixture is reused across tests asserting on different states (idle, loading, error, edge case), its defaults must let each test express its state without monkey-patching internals.

[Why] If a test has to mutate the fixture in surprising ways to reach a state, the fixture is too narrow. Extending the factory is the contract; tests stay declarative.

[Instruction] When you add a new test that asserts on a state the fixture didn't anticipate, **extend the factory** rather than constructing one-offs in the test body.

[Examples]
```ts
// Bad — fixture only supports the happy path; "expired" test has to dig into internals:
const baseAgreement = { signedAt: '2025-01-01', deadline: '2025-12-31' };

it('shows expired badge when past deadline', () => {
  const agreement = { ...baseAgreement, deadline: '2020-01-01' };
});

// Good — factory with overrides; every state is one named override away:
function createAgreement(overrides: Partial<Agreement> = {}): Agreement {
  return { signedAt: '2025-01-01', deadline: '2025-12-31', ...overrides };
}

it('shows expired badge when past deadline', () => {
  const agreement = createAgreement({ deadline: '2020-01-01' });
});
```

## Parametrized test inputs (OK when readable)

[Instruction] Use parametrized inputs when N tests differ only by input/expected; switch back to separate tests when bodies diverge.

[Why] Parametrization reduces duplication when N tests differ only by input/expected. Stops being useful when bodies diverge — at that point, separate tests are more readable.

## Inline test helpers until reused

[Instruction] Keep test-file helpers inline until a second file needs them (centralize at 2+ callers, not speculatively) — grasp-at-a-glance beats DRY, body stays human-readable as documentation of intent.

- [Examples] Inline narrative often wins when the duplicated block is byte-identical and the helper would hide what's being asserted.
- [Examples] Helper-required tests lose their narrative. Duplication cost is mechanical; grasp cost compounds on every read.
- [Examples] A test you can't read is a test you can't trust during a failure.
- [Examples] Opaque tests get deleted at the first "what does this even test?" moment.

## Re-use constants in assertions AND in mock data

[Instruction] Reference the same enums/constants as production code — in assertions, in mock factory bodies, and in fixture defaults.

[Why] Hardcoding the literal value in the test means a refactor that renames the enum silently breaks production while the test still passes (with the old literal). Sharing the constant catches drift.

Mock factories are the silent killer here: a factory that hardcodes `'PLENO'` while production uses `BrandSlugs.PLENO = 'pleno'` (uppercase vs lowercase) lets drift compound.

The test passes against its own mock but never matches the shape production actually emits.

TypeScript can't catch it (string literal narrows but doesn't enforce equivalence with the enum).

The fix is mechanical: every domain identifier in a mock body refers to the production constant, not a copy.

## Debug with code and tests, not temp files

[Instruction] Debug with code and tests, not temp scratchpad files.

[Why] Temp files (scratchpads, throwaway scripts) vanish when the session ends. The next person who hits the same bug has no signal. A failing test or a committed debug script survives.

## Leverage coverage to find untested flows

[Instruction] After tests pass, check coverage if available; uncovered branches reveal corner cases the tests didn't actually exercise.

[Why] Green tests prove the cases you thought of work. Coverage gaps reveal the cases you didn't think of — corner cases hide there.

- [Instruction] Source order: repo's existing coverage script first; else run coverage directly; else read existing artifacts (lcov, coverage.xml).
- [Instruction] Skip silently if none work.

## Tests follow migrated code

[Instruction] When moving logic to a new location, adapt existing tests to the new path. Don't delete behavior coverage.

[Why] Deleting tests during a migration is silent regression risk. The behavior they protected is still being shipped — without the test, the next bug in that area has no signal.

## Question every skipped test

[Instruction] Every `.skip` you encounter — yours or someone else's, old or new — owes the suite a justification. Stop and ask three questions:

1. [Instruction] **Should this be skipped at all?** A skip without a written reason (inline comment or linked ticket explaining what blocks it) is dead weight, not deferred work.
2. [Instruction] **Is it stale?** Old `.skip` + no follow-up commits + production code the test references is missing or changed = abandoned scaffolding.
   - [Examples] Delete (and the file, if 100% of its tests were skipped).
3. [Instruction] **Should it actually be un-skipped now?** The condition that justified the skip may have lifted.
   - [Examples] Un-skip and run — if it passes, the skip outlived its purpose; if it fails meaningfully, the test just caught a real gap.

[Why] Skipped tests are silent debt — the skip count grows quietly, and `skipped` loses meaning when half the entries are forever-deferred.

Skipped tests are also a tell for AI slop: agents readily generate `it.skip(...)` scaffolds claiming TDD intent.

But the implementation that would un-skip them never lands, and the file rots as forever-pending TDD.

Treating each skip as a decision-point keeps the suite honest about what it actually guards — and catches the slop pattern early.

When the answer is "delete," capture the investigation (what was tried, why the skip is dead, what production code it would have guarded) in the commit body.

## Regression baselines: hand-coded shape, not self-comparison

[Instruction] A test that asserts `f(X) === f(X)` proves only that `f` is deterministic — it can never fail unless the system is non-deterministic. Use hand-coded expected values instead.

[Why] A genuine regression guard must encode an *expectation* the implementation might miss. Self-comparison guards nothing.

- [Instruction] Regression baselines must be hand-coded values that the implementation could plausibly fail to produce.
- [Instruction] This is distinct from "Don't reproduce logic under test" (which is about the test recomputing what the code does).
- [Instruction] Self-comparison is about the test asserting against its own runtime output.

[Examples]
```ts
// Bad -- two identical requests, asserting equal proves nothing:
const [a, b] = await Promise.all([
  request(app).get('/v1/things?resolved=false'),
  request(app).get('/v1/things?resolved=false'),
]);
expect(a.body).toEqual(b.body);

// Good -- single request + explicit hand-coded shape:
const response = await request(app).get('/v1/things?resolved=false');
expect(response.body.data).toHaveLength(1);
expect(response.body.data[0].entity).toBe('order');
expect(response.body.pagination).toEqual({ page: 1, pageSize: 20, totalItems: 1, totalPages: 1 });
```
