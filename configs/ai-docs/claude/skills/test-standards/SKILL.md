---
name: test-standards
description: "USE PROACTIVELY whenever you write, edit, or review tests — choosing test type (unit/integration/e2e), mocking, flakes, coverage gaps, regression tests, test titles. Any test edit, not pure reading."
user-invocable: false
words-budget: 5096
instructions-budget: 60
---

# Test Standards

Principles for any test work. Each section pairs a principle with its WHY, with paired examples co-located under the principle.

## Test types

- [Instruction] Unit tests exercise a single function or module in isolation — especially good for stress-testing corner cases in leaf functions (parsers, normalizers, validators, formatters).
  - [Why] Fast execution shortens the code-test iteration cycle; but isolation means they don't prove business value is delivered — complement with integration tests.

- [Instruction] Integration tests exercise multiple units together with some parts mocked (typically external/IO boundaries like DB, HTTP, queues) and should be most used type.
  - [Why] They verify units collaborate correctly without the full-stack cost of E2E, while still exercising enough context to validate real behavior.

- [Instruction] Contract tests verify the API boundary between two systems — request/response shape, status codes, error format — without running the full stack.
  - [Why] A contract test is cheaper and faster than E2E (no browser or full-stack setup) and catches incompatibilities early, before they surface in slow E2E runs or production.

- [Instruction] E2E tests exercise real scenarios end-to-end with no mocking — only fake or test data — validating the full system as users experience it.
  - [Why] No mocking means they catch integration bugs narrower tests miss, but they're slow, brittle, and expensive to maintain — use sparingly for critical paths.

## Choosing the test type

- [Instruction] **CRITICAL: Prefer blackbox tests over whitebox — test at the caller's boundary, not the internals.**
  - [Why] Blackbox tests survive refactors and catch refactor bugs; whitebox tests couple to implementation and break on rename or restructure even when behavior is unchanged.

- [Instruction] **CRITICAL: Mock only at external/IO boundaries (DB, HTTP, queues, file system); keep everything inside the boundary real.**
  - [Why] Integration tests survive internal refactors and exercise the path the caller actually takes.

- [Instruction] Prefer fakes and localstack-style emulators over bare mocks where the cost is reasonable.
  - [Why] A fake behaves like the real dependency; a bare mock only replays the assumptions you encoded, so it keeps passing after they drift from reality.

- [Instruction] Fall back to manual tests only when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox).
  - [Why] Without a sandbox the automation cost outweighs the risk, so forcing automation there spends more than the bug it would catch.

- [Instruction] **Each test layer (unit, integration/router, e2e/browser) independently exercises the functionality it owns — never drop a layer's coverage because another layer covers it.**
  - [Why] Overlapping tests are cheap; a gap justified by cross-layer reliance ships undetected when the covering layer diverges, so visibly-redundant beats quietly-uncovered.

## Coverage & the manual-verification checklist

- [Instruction] **Before writing tests, ask "if I had to verify this change by hand, what steps would I take?" — then automate that list, for backend and frontend alike.**
  - [Why] Coverage tools answer "is this line touched?" but not "would a manual tester have noticed this?" — the manual-verification checklist is the test checklist.

Concrete patterns this rule generates:

- [Instruction] **Cover every variant** — when several things are the same kind (input fields, filters, query params, tabs, entity types, view modes), test each one, directly or via parametrization.
  - [Why] Testing one variant says nothing about the others — they share a kind but can behave differently, so each needs its own check.

[Example]
```ts
// Bad — one filter tested, the other two ship unverified
it('should filter by status', ...);

// Good — every filter variant covered
it('should filter by status', ...);
it('should filter by date range', ...);
it('should filter by assignee', ...);
```

- [Instruction] **Boundary on caps/limits** — a cap of N gets an explicit N+1 test: send N+1 of the limited thing and prove the cap engages.
  - [Why] Happy-path-only leaves the invariant unverified — the cap could be silently broken and every passing test would miss it.

- [Instruction] **Async safety / idempotency** — explicitly test disabled-during-fetch (UI), idempotency keys (API), and retry-resistant operations.
  - [Why] These are the actions a manual tester would re-fire, so an untested one leaves a double-submit or duplicate-write gap in production.

- [Instruction] **Three-branch dependency outcome** — test success, error response, AND timeout/never-responds for every dependency call.
  - [Why] Missing the timeout branch leaves a real production gap — the caller hangs forever (UI stuck loading, backend leaking connections, requests, and pool slots).

- [Instruction] **Test both cache directions** — when you test that data is cached and read back, also test that clearing or invalidating it works (value gone, refetch reloads it).
  - [Why] Testing only the populate path leaves eviction unverified — a broken invalidation silently serves stale data while every passing test misses it.

- [Instruction] **Observably-non-empty BEFORE and AFTER** — for filter/transition tests (UI or API), baseline and final state must both be non-empty.
  - [Why] Empty-to-something only proves the filter renders/returns something — not that it changes the result meaningfully.

- [Instruction] **After tests pass, check coverage if available.**
  - [Why] Green tests prove the cases you thought of work; coverage gaps reveal the cases you didn't think of — corner cases hide there.

## Test titles

### Design test titles before implementation

- [Instruction] **Write titles (no bodies) FIRST, review whether they properly describe the intent/behavior, then run RED-GREEN.**
  - [Why] A title that describes intent on its own reviews fast — you catch a wrong contract before coding, and it guides the right implementation; wrong tests waste time and tokens.

- [Instruction] Never commit test titles alone — a title needs its body in the same commit.
  - [Why] A title committed without its body rots as forever-pending TDD scaffolding that never gets its implementation.

- [Instruction] For scripts (where we usually don't write tests), start with the usage syntax + examples in the comment header — the contract, written before the code.
  - [Why] A script has no `it()` titles to design first, so its comment-header usage line is the contract you write before coding — the same role test titles play.

### Descriptive titles (BDD-like)

- [Instruction] **CRITICAL: Write test titles in domain language a non-engineer (PM, QA, designer) could understand — observable behavior, not internal field names or implementation tokens.**
  - [Why] Titles get scanned more than bodies, and one tied to an internal field name breaks on rename even when behavior is unchanged — domain-language titles survive.

**Anti-pattern: generic noun when multiple instances of the same kind exist**

- [Instruction] When a system has multiple instances of the same kind — two search fields, two filters, two query params, two endpoints — name the specific one in the title.
  - [Why] A generic noun invites confusion when two of the same kind exist — the reader can't tell which control the test pins.

[Example]
```
Bad:  "should AND fieldA IN with fieldB NOT IN when both provided"   (operator mechanics)
Bad:  "regression: PR #2034 last-spread-wins on flowCode"            (session/branch history)
Good: "should subtract excludeFlowCodes from the flowCode include set when both filters are provided"
```

[Example]
```ts
// Bad — generic noun; page has two searches (school name + externalId); which one?
it('should NOT re-fire schoolsAgreements when search changes (cache hit)', ...);

// Good — names the specific control:
it('should NOT re-fire schoolsAgreements when externalId search changes (cache hit)', ...);
```

**Anti-pattern: internal-state predicate instead of operator-language behavior**

[Example]
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

The form `should X when Y` implies Y is the only precondition.

- [Instruction] If the assertion holds only when `Y AND Z`, the title must encode the conjunction — or split into separate tests if cleaner.
  - [Why] A title is a tiny spec; an incomplete one documents the wrong contract, so readers learn the wrong precondition and the test stops guarding the missing one.

[Example]
```ts
// Bad — incomplete precondition (only true when loading=false)
it('should enable Apply after operator toggles a school off then back on', ...);

// Good — full precondition
it('should enable Apply after operator toggles a school off then back on, only when not loading', ...);
it('should disable Apply while loading (loading dominates dirty state)', ...);
```

## Splitting & pruning tests

### One test per distinct cause

- [Instruction] **CRITICAL: When a new test exercises the same code path with the same inputs as an existing one, remove the duplicate or merge.**
  - [Why] Two tests asserting the same thing don't improve safety — they slow the suite, double the maintenance burden, and create false confidence.
  - [Example] If "max 10" is enforced, one test at 11 covers it; tests at 12, 15, 100 are redundant — boundary + 1 is the contract.

- [Instruction] Isolate each independent trigger for a behavior; different inputs that exercise the same code path are one test, not two.
  - [Why] Distinct causes are the unit of safety — if two test cases hit the same production code path, the second adds maintenance with no extra coverage.

- [Instruction] When multiple events produce the same outcome (different filters reset the page, different errors roll back one transaction), write ONE test on the outcome, not N one-per-trigger.
  - [Why] One-per-trigger tests miss the next trigger someone adds; a test on the shared outcome automatically covers new triggers too.

Distinguish from neighbors: "Remove redundant tests" fires on identical assertions; "One test per distinct cause" fires when causes have independent production branches; this rule fires when triggers differ but share one branch.

[Example]
```ts
// Bad — three tests, one per trigger, all asserting the same behavior:
it('should reset page to 1 when status filter changes', ...);
it('should reset page to 1 when search input changes', ...);
it('should reset page to 1 when sort order changes', ...);

// Good — one test of the underlying invariant:
it('should reset page to 1 on every refetch of the dataset', ...);
```

### Splitting & grouping by behavior

- [Instruction] One test = one behavior asserted; a title joined by "and" (or covering two independent behaviors) splits into two tests.
  - [Why] A compound assertion hides which half broke — you re-read the body to find out; splitting forces sharper per-behavior titles, making the test list an index.

[Example]
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

- [Instruction] Group tests by intent — happy path, corner cases, failure scenarios — using nested describe blocks.
  - [Why] Readers scanning "what does this do when it works?" should not wade through error paths — grouping by intent makes the contract scannable at a glance.

[Example]
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

## Determinism & flakes

- [Instruction] **No shared state between tests — each test sets up and tears down its own.**
  - [Why] Shared state makes outcome depend on run order: a test that passes 9 times and fails the 10th teaches engineers to rerun instead of investigate, so real failures get ignored.

- [Instruction] **No randomness in test inputs or assertions — use fixed values.**
  - [Why] A random input means a failure may not reproduce, so the signal is unactionable and the flake erodes trust in the suite.

- [Instruction] Clone inputs before passing them to mutating functions.
  - [Why] A function that mutates its argument corrupts the shared fixture, so the next test in the file silently inherits the mutation.

- [Instruction] **Pin the clock with fake timers whenever the system under test reads it (directly or via helpers); test names like "expired", "deadline", "min", "cap" are the tell.**
  - [Why] Without a frozen clock, a time-derived test passes today and silently fails in N months when the wall-clock crosses the threshold it depends on.

- [Instruction] **File a `[Scout]` for any observed test flake (intermittent failure, OOM, timing race) immediately, even before the cause is clear.**
  - [Why] A flake wastes your time chasing bugs that aren't there and erodes trust in the suite; left unfiled, flakes pile up until it guards nothing.

- [Instruction] Tests should not break when the implementation changes the order of items in a collection, unless order is part of the contract.
  - [Why] Asserting on exact array order couples tests to implementation details — a refactor that changes iteration order shouldn't break a behavior test.

[Example]
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

## Mocking, fixtures & test data

- [Instruction] Use realistic-looking values in mock data (real-shaped names, emails, IDs, dates) — not placeholder fragments.
  - [Why] Cryptic mock data (`name: "x"`, `email: "a@b"`) hides bugs that show up only with realistic shapes (encoding, length, casing) — real-like data catches real-like bugs.

- [Instruction] Reach any test state by extending the shared factory with overrides — never monkey-patch fixture internals or build one-offs in the test body.
  - [Why] A one-off or monkey-patch drifts from the shared fixture and hides setup from the next reader; a factory override keeps every state declarative.

[Example]
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

- [Instruction] **CRITICAL: Reference the same enums/constants as production code — in assertions, in mock factory bodies, and in fixture defaults.**
  - [Why] Hardcoding the literal means a refactor that renames the enum silently breaks production while the test still passes on the old literal — sharing the constant catches the drift.
  - [Example] A mock factory that hardcodes `'PLENO'` while production uses `BrandSlugs.PLENO = 'pleno'` passes against its own mock but never matches production's shape — and TypeScript can't catch it.

- [Instruction] Parametrize inputs only when it keeps tests readable, or when writing them one-by-one doesn't scale; split back to separate tests once bodies diverge.
  - [Why] Parametrization's only payoff is dedup; once bodies diverge, the shared harness obscures what each case actually asserts, and that readability cost outweighs the dedup.

- [Instruction] Keep test-file helpers inline until a second file needs them — and even at 2+ callers, stay inline when a helper would hide what's being asserted.
  - [Why] Grasp-at-a-glance beats DRY in tests — the body stays readable as documentation of intent, and a helper's mechanical dedup isn't worth the grasp cost on every read.

## Test integrity & maintenance

### Assert real behavior, not implementation

- [Instruction] **CRITICAL: Let the system under test do the work — the test must encode an independent expectation, not recompute what the code does.**
  - [Why] If the test reproduces the logic, both move together: a bug in the production logic is mirrored in the test, and the test passes anyway.

[Example]
```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```

- [Instruction] Hand-code regression baselines as explicit expected values — never `f(X) === f(X)`, which only proves `f` is deterministic and can never fail.
  - [Why] A real regression guard needs a value you wrote down that the code might get wrong; comparing the code's output to itself checks nothing.

Distinct from "Don't reproduce logic under test": that rule is about the test recomputing what the code does, this one is about the test asserting against its own runtime output.

[Example]
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

- [Instruction] Don't assert that a log was emitted — log emission is not behavior the caller observes.
  - [Why] Log assertions are brittle (break when format evolves), tautological (mirror impl), and clutter the suite — testing the behavior that produced the log carries the same signal without the brittleness.

### Durable regression coverage

- [Instruction] **CRITICAL: Write a failing regression test that reproduces the bug before the fix lands; `debug-standards` holds the full rule.**
  - [Why] The failing test proves you've reproduced the real bug and turns into the guard that stops it from regressing.

- [Instruction] When you move code, move its tests too (if they exist) — adapt them to the new path, don't drop the coverage.
  - [Why] Leaving tests behind during a move is silent regression risk: the behavior still ships, but the next bug in that area has no test to catch it.

- [Instruction] Prefer durable debugging artifacts — a failing test or committed debug script — over throwaway scratchpads.
  - [Why] A scratchpad vanishes when the session ends, leaving the next person who hits the bug no signal; a test or committed script survives.

### Question every skipped test

- [Instruction] **Every `.skip` — yours or someone else's, old or new — owes a written justification (inline comment or linked ticket).**
  - [Why] Skipped tests are silent debt whose count grows quietly, and a tell for AI slop — `it.skip()` scaffolds whose implementation never lands and the file rots as forever-pending TDD.

- [Instruction] Delete dead skips — a stale one (old, no follow-up commits, referenced code gone or changed), or the whole file when 100% of its tests are skipped.
  - [Why] A stale skip pads the count with tests that map to no real code; a fully-skipped file adds zero coverage and a standing audit cost — both dead weight.

- [Instruction] Un-skip and run when the condition that justified the skip may have lifted.
  - [Why] If it passes, the skip outlived its purpose; if it fails meaningfully, it just caught a real gap — the blocking condition often lifts silently.

- [Instruction] When the answer is "delete," capture the investigation (what was tried, why the skip is dead, what code it would have guarded) in the commit body.
  - [Why] The next reader who wonders why that coverage vanished needs the reasoning, or they re-litigate the same dead skip.
