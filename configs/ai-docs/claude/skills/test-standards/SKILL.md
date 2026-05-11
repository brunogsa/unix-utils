---
name: test-standards
description: "Test principles + examples. USE PROACTIVELY on ANY test work — writing, reading, choosing test type (unit/integration/e2e), mocking, flakes, coverage gaps, regression tests, test titles, or reviewing tests."
user-invocable: false
---

# Test Standards

Principles and paired examples for any test work. Each section pairs a principle with its example (when necessary).
Principles without an example stand on their own.

## Default to integration tests for behavior coverage

Black-box by nature. Mock at external/IO boundaries (DB, HTTP, queues, file system).

Why: integration tests survive internal refactors and exercise the path the caller actually takes. Unit tests pinned to implementation details break every time the implementation moves, even when behavior is identical.

- Prefer fakes and localstack-style emulators to bare mocks where the cost is reasonable.
- Add **unit tests** for leaf functions/modules — pure logic with no/few dependencies (parsers, normalizers, validators, formatters). Whitebox; expect tests to change when the implementation changes.
- Skip unit tests when the only "unit" is a thin glue function.
- **E2E tests sparingly** — slow and brittle; flakiness erodes trust in the suite. Acceptable when the specific case is cheap (existing fixture, single happy-path Playwright run, smoke test).
- **Manual tests** when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox). Log per `test-driven-development` format.

## Test behaviour, not implementation

Black-box integration tests preferred; supplement with focused unit tests.

Why: on refactors, integration tests (behavior) keep working and serve as a guardrail.

Unit tests pinned to implementation must be refactored too — the test stops protecting you the moment you most need it.

## Design test titles before implementation

Write titles (no bodies), review them, then run RED-GREEN.

Why: titles capture the contract before the code locks it in.

Writing tests AFTER you "see what works" shapes the test to whatever you ended up writing — the test stops being a contract.

- Applies upfront to integration tests and pre-known pure helpers, and again at each helper pulled on demand — designing them all upfront forces premature signatures.
- Commit tests together with their implementation — never titles alone.
- For scripts: usage syntax + examples in the comment header.

## Descriptive titles (BDD-like)

Test titles read as the behavior documentation, in domain language.

Why: titles get scanned a hundred times more than test bodies.

```
Bad:  "should AND fieldA IN with fieldB NOT IN when both provided"   (operator mechanics)
Bad:  "regression: PR #2034 last-spread-wins on flowCode"            (session/branch history)
Good: "should subtract excludeFlowCodes from the flowCode include set when both filters are provided"
```

**Anti-pattern: spec-tracking refs in test titles**

```ts
// Bad
it('should throw INTERNAL_SERVER_ERROR when getSalesAgreements throws after retries (AC-18)', ...);
it('should emit the structured procedure-entry log per Req 21', ...);

// Good
it('should throw INTERNAL_SERVER_ERROR when getSalesAgreements throws after retries', ...);
```

AC/Req/Task/DBMA/Jira refs belong in commit messages, PR descriptions, or `spec.md` — not in test titles, which describe behavior.

## Bug fix starts with a failing regression test

See `debug-standards` for the full rule.

## Deterministic & self-contained

No shared state, no randomness, clone inputs when testing mutating functions. Pin the clock with fake timers when the system under test reads it — directly or via helpers.

Why: flaky tests erode trust.

A test that passes 9 times and fails the 10th is worse than no test — engineers learn to rerun instead of investigate, and real failures get ignored.

- Time-derived tests without a frozen clock are time-bombs — they pass today and silently fail in N months when wall-clock crosses a threshold.
- Apply when test names contain "past", "future", "expired", "min", "cap", "deadline" — wall-clock-sensitive vocabulary.

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

## Don't test log presence

Log emission is not behavior the caller observes.

Why: log assertions are brittle (change when the log format evolves), tautological (mirror the impl), and clutter the suite. Test the behavior that produced the log, not the log itself.

**Exception**: when a log is an external contract (audit log consumed by another system, structured event for analytics), test the payload shape — that's contract testing, not log presence testing.

## Cover every variant of a behavior

When a feature has N variants (tabs, entity types, query params, view modes, browser sizes), every variant must be covered — directly or via parametrization.

Why: coverage on variant A says nothing about variant B's behavior. The "one example, infer the rest" heuristic fails the moment behavior diverges across variants.

Heuristic: ask "are the other variants tested?" for every test you write.

## Group tests by intent: happy path, corner cases, failure scenarios

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

Why: readers scanning "what does this do when it works?" should not wade through error paths. Grouping by intent makes the contract scannable at a glance.

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

When you add a new test that asserts on a state the fixture didn't anticipate, **extend the factory** rather than constructing one-offs in the test body.

## Parametrized test inputs (OK when readable)

Why: parametrization reduces duplication when N tests differ only by input/expected. Stops being useful when bodies diverge — at that point, separate tests are more readable.

## Inline test helpers until reused

Keep builder/factory helpers in the test file until a second test file needs them. Centralize at 2+ callers, not speculatively.

Why: speculative centralization adds indirection without payoff.

Readers have to navigate to a shared module to understand what a test does. The 2+ caller rule keeps the abstraction grounded in real demand.

## Test body and helpers easier to read

Ensure a human can read it and understand what is happening.

Why: a test you can't read is a test you can't trust during a failure.

The body is documentation of intent — opaque tests get deleted at the first "what does this even test?" moment.

## Re-use constants in assertions

Reference the same enums/constants as production code.

Why: hardcoding the literal value in the test means a refactor that renames the enum silently breaks production while the test still passes (with the old literal). Sharing the constant catches drift.

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
