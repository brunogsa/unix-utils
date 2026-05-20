---
name: test-standards
description: "Test principles + examples. USE PROACTIVELY on ANY test work — writing, reading, choosing test type (unit/integration/e2e), mocking, flakes, coverage gaps, regression tests, test titles, or reviewing tests."
user-invocable: false
words-budget: 5096
---

# Test Standards

Principles for any test work. Each section pairs a principle with its WHY, with paired examples co-located under the principle.

## Default to integration tests; test behaviour, not implementation

Black-box by nature. Mock at external/IO boundaries (DB, HTTP, queues, file system).

Why: integration tests survive internal refactors and exercise the path the caller actually takes.

Unit tests pinned to implementation must be refactored alongside the code they pin — the test stops protecting you the moment you most need it.

- Prefer fakes and localstack-style emulators to bare mocks where the cost is reasonable.
- Add **unit tests** for leaf functions/modules — pure logic with no/few dependencies (parsers, normalizers, validators, formatters). Whitebox; expect tests to change when the implementation changes.
- Skip unit tests when the only "unit" is a thin glue function.
- **E2E tests sparingly** — slow and brittle; flakiness erodes trust in the suite. Acceptable when the specific case is cheap (existing fixture, single happy-path Playwright run, smoke test).
- **Manual tests** when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox). Log per `test-driven-development` format.

## Gold rule: automate what a human would manually do to verify

Before writing tests, ask: "if I had to verify this change by hand, what steps would I take?" — then automate that list.

Applies to backend (API calls, payloads, DB states) and frontend (clicks, inputs, page states) equally — the human verification checklist is the same shape regardless of layer.

Why: coverage tools answer "is this line touched?" — they cannot answer "would a manual tester have noticed this?". The manual-verification checklist is the test checklist.

Concrete patterns this rule generates:

- **Cover every variant** — N variants of the same kind = N tests (directly or via parametrization). Coverage on one says nothing about the others.
  - Variant kinds: input fields, filters, query params, tabs, entity types, view modes, browser sizes.
  - The "one example, infer the rest" heuristic fails the moment behavior diverges.
- **Boundary on caps/limits** — a cap of N gets an explicit N+1 test (send N+1 of the limited thing and prove the cap engages). Happy-path-only leaves the invariant unverified.
- **Async safety / idempotency** — disabled-during-fetch (UI), idempotency keys (API), retry-resistant operations — the actions a manual tester would re-fire need explicit tests.
- **Three-branch dependency outcome** — success, error response, AND timeout/never-responds. Missing the timeout branch leaves a real production gap (UI stays loading forever; backend leaks resources).
- **Inverse cache branch** — when set-and-fetch is tested, test clear-and-restore (or invalidate-and-refetch). Partial cache coverage is a known footgun.
- **Observably-non-empty BEFORE and AFTER** — for filter/transition tests (UI or API), baseline and final state must both be non-empty.
  - Empty-to-something only proves the filter renders/returns something — not that it changes meaningfully.

## Design test titles before implementation

Write titles (no bodies), review them, then run RED-GREEN.

Why: titles capture the contract before the code locks it in.

Writing tests AFTER you "see what works" shapes the test to whatever you ended up writing — the test stops being a contract.

- Applies upfront to integration tests and pre-known pure helpers, and again at each helper pulled on demand — designing them all upfront forces premature signatures.
- Commit tests together with their implementation — never titles alone.
- For scripts: usage syntax + examples in the comment header.

## Descriptive titles (BDD-like)

Test titles read as the behavior documentation, in domain language.

Title content describes observable behavior in domain vocabulary, not internal field names or implementation tokens.

Why: titles get scanned a hundred times more than test bodies.

A title coupled to an internal field name breaks the moment the field is renamed even when the behavior is identical; a title in domain language survives.

**No spec/plan/AC refs in test titles** — see CLAUDE.md ("Self-describing artifacts — no context-dependent shorthand"). Same rule applies to test titles.

**Anti-pattern: generic noun when multiple instances of the same kind exist**

When a system has multiple instances of the same kind — two search fields, two filters, two query params, two endpoints — name the specific one in the title.

Generic nouns invite confusion.

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

## Test titles encode the FULL precondition, not happy-path only

The form `should X when Y` implies Y is the only precondition.

If the assertion holds only when `Y AND Z`, the title must say so — `should X when Y, only when not Z` — or split into separate tests if cleaner.

Why: a title is a tiny spec.

An incomplete title fails to document the conjunctive constraint — readers learn the wrong contract, and the test stops being a guard for the missing precondition.

```ts
// Bad — incomplete precondition (only true when loading=false)
it('should enable Apply after operator toggles a school off then back on', ...);

// Good — full precondition
it('should enable Apply after operator toggles a school off then back on, only when not loading', ...);
it('should disable Apply while loading (loading dominates dirty state)', ...);
```

## Bug fix starts with a failing regression test

See `debug-standards` for the full rule.

## Deterministic & self-contained

No shared state, no randomness, clone inputs when testing mutating functions. Pin the clock with fake timers when the system under test reads it — directly or via helpers.

Why: flaky tests erode trust.

A test that passes 9 times and fails the 10th is worse than no test — engineers learn to rerun instead of investigate, and real failures get ignored.

- Time-derived tests without a frozen clock are time-bombs — they pass today and silently fail in N months when wall-clock crosses a threshold.
- Apply when test names contain "past", "future", "expired", "min", "cap", "deadline" — wall-clock-sensitive vocabulary.

## Observed test flakes always become Scouts

Any observed test flake — intermittent failure, OOM, timing race — queues a Scout immediately, even when the root cause is unclear at observation time.

Uses the Scout mechanism from CLAUDE.md's Scout rule (auto-add as `[Scout]`).

Why: flakiness compounds — each ignored instance erodes signal in the suite, so the "next" failure can't be trusted as a real regression.

"Not my problem today" becomes "the suite stops guarding tomorrow."

## Mock sparingly

Only external dependencies (file I/O, network, external processes).

Why: every mock is a hypothesis about what the dependency does.

If the hypothesis drifts from reality, the test passes while production breaks. Mock at the system boundary, not in the middle.

## Use real-like mock data

Why: cryptic mock data (`name: "x"`, `email: "a@b"`) hides bugs that show up only with realistic shapes (encoding, length, casing). Real-like data catches real-like bugs.

## Don't re-implement logic under test

Let the system under test do the work.

Why: if the test reproduces the logic, both move together.

A bug in the production logic is mirrored in the test, and the test passes anyway. The test must encode an independent expectation.

```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```

## Remove redundant / tautological tests

When a new test exercises the same code path with the same inputs as an existing one, remove the duplicate or merge.

Why: two tests asserting the same thing don't improve safety — they slow the suite, double the maintenance burden, and create false confidence.

Schema example: if "max 10" is enforced, one test at 11 covers it; tests at 12, 15, 100 are redundant. Boundary + 1 is the contract.

## One test per distinct cause

Isolate each independent trigger for a behavior. Different inputs that exercise the same code path are one test, not two.

Why: distinct causes are the unit of safety. If two test cases hit the same production code path, the second adds maintenance with no extra coverage.

## When N triggers share one outcome, test the outcome

When multiple events produce the same outcome — different filters reset the page, different mutations invalidate one cache, different errors roll back one transaction — write ONE test asserting the outcome.

Don't write N tests one-per-trigger when all paths lead to the same final state.

Why: N specific tests grow linearly with each new trigger and silently miss the next one added.

A test of the outcome itself ("any refetch resets page to 1") inherits coverage automatically when new triggers join.

- **vs. "Remove redundant tests"** — that rule fires on identical assertions; this rule fires when triggers differ but outcome doesn't.
- **vs. "One test per distinct cause"** — that rule fires when causes have independent production branches; this rule fires when triggers share one production branch.

```ts
// Bad — three tests, one per trigger, all asserting the same behavior:
it('should reset page to 1 when status filter changes', ...);
it('should reset page to 1 when search input changes', ...);
it('should reset page to 1 when sort order changes', ...);

// Good — one test of the underlying invariant:
it('should reset page to 1 on every refetch of the dataset', ...);
```

## Don't test log presence

Log emission is not behavior the caller observes.

Why: log assertions are brittle (change when the log format evolves), tautological (mirror the impl), and clutter the suite. Test the behavior that produced the log, not the log itself.

**Exception**: when a log is an external contract (audit log consumed by another system, structured event for analytics), test the payload shape — that's contract testing, not log presence testing.

## Group tests by intent: happy path, corner cases, failure scenarios

Why: readers scanning "what does this do when it works?" should not wade through error paths. Grouping by intent makes the contract scannable at a glance.

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

Tests should not break when the implementation changes the order of items in a collection, unless order is part of the contract.

Why: asserting on exact array order couples tests to implementation details. A refactor that changes iteration order shouldn't break a behavior test.

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

When a single fixture is reused across tests that assert on different states (idle, loading, error, edge case), the fixture's defaults must allow each test to express its state without monkey-patching internals.

Why: if a test has to mutate the fixture in surprising ways to reach a state, the fixture is too narrow. Extending the factory is the contract; tests stay declarative.

When you add a new test that asserts on a state the fixture didn't anticipate, **extend the factory** rather than constructing one-offs in the test body.

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

Why: parametrization reduces duplication when N tests differ only by input/expected. Stops being useful when bodies diverge — at that point, separate tests are more readable.

## Inline test helpers until reused

Keep builder/factory helpers in the test file until a second test file needs them. Centralize at 2+ callers, not speculatively.

- **Grasp-at-a-glance beats DRY in tests** -- before extracting a helper across N files, ask: does the extraction force the reader to chase indirection?
  - Inline narrative often wins when the duplicated block is byte-identical and the helper would hide what's being asserted.
  - Why: helper-required tests lose their narrative. Duplication cost is mechanical; grasp cost compounds on every read.
- **Body must be human-readable** — the body is documentation of intent.
  - A test you can't read is a test you can't trust during a failure.
  - Opaque tests get deleted at the first "what does this even test?" moment.

## Re-use constants in assertions AND in mock data

Reference the same enums/constants as production code — in assertions, in mock factory bodies, and in fixture defaults.

Why: hardcoding the literal value in the test means a refactor that renames the enum silently breaks production while the test still passes (with the old literal). Sharing the constant catches drift.

Mock factories are the silent killer here: a factory that hardcodes `'PLENO'` while production uses `BrandSlugs.PLENO = 'pleno'` (uppercase vs lowercase) lets drift compound.

The test passes against its own mock but never matches the shape production actually emits.

TypeScript can't catch it (string literal narrows but doesn't enforce equivalence with the enum).

The fix is mechanical: every domain identifier in a mock body refers to the production constant, not a copy.

## Debug with code and tests, not temp files

Why: temp files (scratchpads, throwaway scripts) vanish when the session ends. The next person who hits the same bug has no signal. A failing test or a committed debug script survives.

## Leverage coverage to find untested flows

After tests pass, check coverage if available; uncovered branches reveal corner cases the tests didn't actually exercise.

Why: green tests prove the cases you thought of work. Coverage gaps reveal the cases you didn't think of — corner cases hide there.

- Source order: repo's existing coverage script first; else run coverage directly; else read existing artifacts (lcov, coverage.xml).
- Skip silently if none work.

## Tests follow migrated code

When moving logic to a new location, adapt existing tests to the new path. Don't delete behavior coverage.

Why: deleting tests during a migration is silent regression risk. The behavior they protected is still being shipped — without the test, the next bug in that area has no signal.

## Question every skipped test

Every `.skip` you encounter — yours or someone else's, old or new — owes the suite a justification. Stop and ask three questions:

1. **Should this be skipped at all?** A skip without a written reason (inline comment or linked ticket explaining what blocks it) is dead weight, not deferred work.
2. **Is it stale?** Old `.skip` + no follow-up commits + production code the test references is missing or changed = abandoned scaffolding.
   - Delete (and the file, if 100% of its tests were skipped).
3. **Should it actually be un-skipped now?** The condition that justified the skip may have lifted.
   - Un-skip and run — if it passes, the skip outlived its purpose; if it fails meaningfully, the test just caught a real gap.

Why: skipped tests are silent debt — the skip count grows quietly, and `skipped` loses meaning when half the entries are forever-deferred.

Skipped tests are also a tell for AI slop: agents readily generate `it.skip(...)` scaffolds claiming TDD intent.

But the implementation that would un-skip them never lands, and the file rots as forever-pending TDD.

Treating each skip as a decision-point keeps the suite honest about what it actually guards — and catches the slop pattern early.

When the answer is "delete," cross-reference the three-evidence checklist in CLAUDE.md ("Destructive cleanup needs 3 evidence types") and capture the investigation in the commit body.

## Regression baselines: hand-coded shape, not self-comparison

A test that asserts `f(X) === f(X)` proves only that `f` is deterministic — it can never fail unless the system is non-deterministic.

Why: a genuine regression guard must encode an *expectation* the implementation might miss. Self-comparison guards nothing.

- Regression baselines must be hand-coded values that the implementation could plausibly fail to produce.
- This is distinct from "Don't reproduce logic under test" (which is about the test recomputing what the code does).
- Self-comparison is about the test asserting against its own runtime output.

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
