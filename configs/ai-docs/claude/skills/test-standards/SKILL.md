---
name: test-standards
description: "USE PROACTIVELY whenever you write, edit, or review tests — choosing test type (unit/integration/e2e), mocking, flakes, coverage gaps, regression tests, test titles. Any test edit, not pure reading."
user-invocable: false
words-budget: 4096
instructions-budget: 60
---

# Test Standards

Principles for any test work. Each section pairs a principle with its WHY, with paired examples co-located under the principle.

## Test types

- [Instruction] Unit tests exercise a single function or module in isolation — especially good for stress-testing corner cases in leaf functions (parsers, normalizers, validators, formatters).
  - [Why] Fast execution shortens the code-test cycle, but isolation alone can't prove business value delivered.

- [Instruction] Integration tests exercise multiple units together with some parts mocked — typically external/IO boundaries like DB, HTTP, queues.
  - [Why] They verify units collaborate correctly without E2E's full-stack cost, while still validating real behavior.

- [Instruction] Make integration tests the most-used tier of the suite.
  - [Why] They hit the sweet spot — more real behavior than unit tests, far cheaper and less brittle than E2E.

- [Instruction] Contract tests verify the API boundary between two systems — request/response shape, status codes, error format — without running the full stack.
  - [Why] Cheaper and faster than E2E (no full-stack setup) and catches incompatibilities before they reach E2E or production.

- [Instruction] E2E tests exercise real scenarios end-to-end with no mocking — only fake or test data — validating the full system as users experience it.
  - [Why] No mocking means they catch integration bugs that narrower tests miss.

- [Instruction] Reserve E2E for a few critical paths — don't grow the E2E tier broadly.
  - [Why] E2E is slow, brittle, and costly to maintain — broad coverage there costs more than the bugs it catches.

## Choosing the test type

- [Instruction] **CRITICAL: Prefer blackbox tests over whitebox — test at the caller's boundary, not the internals.**
  - [Why] Blackbox survives refactors; whitebox couples to implementation, breaking on rename even when behavior holds.

- [Instruction] **CRITICAL: Mock only at external/IO boundaries (DB, HTTP, queues, file system); keep everything inside the boundary real.**
  - [Why] Integration tests survive internal refactors and exercise the path the caller actually takes.

- [Instruction] Prefer fakes and localstack-style emulators over bare mocks where the cost is reasonable.
  - [Why] A fake behaves like the real dependency; a mock only replays what you encoded, and keeps passing after drift.

- [Instruction] Fall back to manual tests only when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox).
  - [Why] Without a sandbox, automation costs more than the bug it would catch.

- [Instruction] **Each test layer (unit, integration/router, e2e/browser) independently exercises the functionality it owns — never drop a layer's coverage because another layer covers it.**
  - [Why] Overlapping tests are cheap; a gap justified by cross-layer reliance ships undetected when that layer diverges.

## Coverage & the manual-verification checklist

- [Instruction] **Before writing tests, ask "if I had to verify this change by hand, what steps would I take?" — then automate that list, for backend and frontend alike.**
  - [Why] Coverage tools answer "is this line touched?" not "would a tester notice this?" — that's the test checklist.

- [Instruction] **Probe corner-case and failure-mode coverage against the canonical checklists in `references/coverage-taxonomy.md`** — that file owns the category lists; other skills only recap it.
  - [Why] One canonical taxonomy keeps probes, checklists, and test design aligned; parallel copies drift and ship gaps.

Concrete patterns this rule generates:

- [Instruction] **Cover all cases** — list every case the code can take, then test each one, directly or via parametrization.
  - [Why] Testing one case says nothing about its siblings — they share a kind but can behave differently.

[Example]
```ts
// A case is any field, filter, param, tab, entity type, view mode, union
// branch, or path a shared shape can arrive through.

// Bad — one filter tested, the other two ship unverified
it('should filter by status', ...);

// Bad — materiais[].professores[] asserted, suplementares[].professores[] not:
// the same shape arrives through two paths, so both need the assertion.

// Bad — the professor branch's accept case asserted, the student branch's
// reject case missing: a union needs every branch tested, both ways.

// Good — every case covered
it('should filter by status', ...);
it('should filter by date range', ...);
it('should filter by assignee', ...);
```

- [Instruction] **Boundary on caps/limits** — a cap of N gets an explicit N+1 test: send N+1 of the limited thing and prove the cap engages.
  - [Why] Happy-path-only leaves the invariant unverified — the cap could break silently and every test would miss it.

- [Instruction] **Fixture data must enter the guarded branch** — when the code under test has precision/rounding/division/dedup logic, build fixtures from realistic non-round, multi-element values, never round numbers or a single element.
  - [Why] A round-number, single-element fixture stays green while never executing the guarded branch, hiding the bug.
  - [Example] Price `1000` split one way never trips a rounding-reconciliation guard; `1058.33` divided across 3 shares of `33.33%` does.

- [Instruction] **Async safety / idempotency** — explicitly test disabled-during-fetch (UI), idempotency keys (API), and retry-resistant operations.
  - [Why] These are the actions a manual tester would re-fire — untested, they leave a double-submit or duplicate-write gap.

- [Instruction] **Three-branch dependency outcome** — test success, error response, AND timeout/never-responds for every dependency call.
  - [Why] Missing the timeout branch leaves a real gap — the caller hangs forever (UI stuck, backend leaking connections).

- [Instruction] **Test both cache directions** — when you test that data is cached and read back, also test that clearing or invalidating it works (value gone, refetch reloads it).
  - [Why] Testing only the populate path leaves eviction unverified — broken invalidation silently serves stale data.

- [Instruction] **Observably-non-empty BEFORE and AFTER** — for filter/transition tests (UI or API), baseline and final state must both be non-empty.
  - [Why] Empty-to-something only proves the filter renders/returns something — not that it changes the result meaningfully.

- [Instruction] After changing code, re-run the full suite across every tier the change could reach (unit, integration/contract, e2e) workspace-wide — not the diff-scoped subset — before declaring the change done.
  - [Why] A change's blast radius exceeds its diff — a rename or removed export breaks callers a scoped run never touches.

- [Instruction] Prefer the project's ci/agentic test variant when one exists over the bare test runner.
  - [Why] The ci/agentic variant exits non-zero cleanly, so automation can trust its exit code instead of scraping output.

- [Instruction] Flag a tier the change touches but the project has no suite for as `[Harness]`, rather than skipping it silently.
  - [Why] A silently-skipped tier reads as "covered" when it isn't; naming the gap scales the fix to the next caller.

- [Instruction] **After tests pass, check coverage if available.**
  - [Why] Green tests prove the cases you thought of work; coverage gaps reveal the cases you didn't think of.

## Test titles

### Design test titles before implementation

- [Instruction] **Write titles (no bodies) FIRST, review whether they properly describe the intent/behavior, then run RED-GREEN.**
  - [Why] A title that describes intent reviews fast — you catch a wrong contract before coding, not after wasting time.

- [Instruction] Never commit test titles alone — a title needs its body in the same commit.
  - [Why] A title committed without its body rots as forever-pending TDD scaffolding that never gets its implementation.

- [Instruction] For scripts (where we usually don't write tests), start with the usage syntax + examples in the comment header — the contract, written before the code.
  - [Why] A script has no `it()` titles to design first, so its comment-header usage line plays that same contract role.

- [Instruction] Before rewriting a `.sh` script, capture its behavior with `scripts/capture-script-behavior.py` — every row's stdout/stderr/exit code and fixture post-state as golden — then replay the table against the rewrite.
  - [Why] A script has no test suite to lean on, so capture-then-replay is the only way to prove the rewrite is equivalent.

### Descriptive titles (BDD-like)

- [Instruction] **CRITICAL: Write test titles in domain language a non-engineer (PM, QA, designer) could understand — observable behavior, not internal field names or implementation tokens.**
  - [Why] Titles get scanned more than bodies; one tied to an internal field name breaks on rename even when behavior holds.

**Anti-pattern: generic noun when multiple instances of the same kind exist**

- [Instruction] When a system has multiple instances of the same kind — two search fields, two filters, two query params, two endpoints — name the specific one in the title.
  - [Why] A generic noun invites confusion when two of the same kind exist — the reader can't tell which one is pinned.

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
  - [Why] A title is a tiny spec; an incomplete one documents the wrong contract and stops guarding the missing precondition.

[Example]
```ts
// Bad — incomplete precondition (only true when loading=false)
it('should enable Apply after operator toggles a school off then back on', ...);

// Good — full precondition
it('should enable Apply after operator toggles a school off then back on, only when not loading', ...);
it('should disable Apply while loading (loading dominates dirty state)', ...);
```

## Splitting & pruning tests

### Tests that should not exist

Whether a change owes a test at all is settled by CLAUDE.md → "Execution lanes". This section covers the case that passes that gate and is still not worth writing.

- [Instruction] Never write a test whose system under test is prose in a committed `.md` — its heading order, its wording, its section list, its frontmatter values.
  - [Why] It can only catch an edit to the prose, never the behavior the prose asks for, because the actor reading it is an LLM.

A fixture-driven suite is not in this class: feeding a checker a temp-dir `.md` the test itself wrote exercises the checker, and the checker is real code.

The tell is which file the assertion reads. A path into the repo's own committed docs is a doc-content contract test; a `mktemp`/`TemporaryDirectory` path is a behavior test.

When a committed doc really must hold a shape, encode that shape as a checker running over every file of its kind, and test the checker on fixtures.

### One test per distinct cause

- [Instruction] **CRITICAL: When a new test exercises the same code path with the same inputs as an existing one, remove the duplicate or merge.**
  - [Why] Two tests asserting the same thing don't improve safety — they slow the suite and double the maintenance burden.
  - [Example] If "max 10" is enforced, one test at 11 covers it; tests at 12, 15, 100 are redundant — boundary + 1 is the contract.

- [Instruction] Isolate each independent trigger for a behavior; different inputs that exercise the same code path are one test, not two.
  - [Why] Distinct causes are the unit of safety — two cases on the same code path add upkeep with no coverage gain.

- [Instruction] When multiple events produce the same outcome (different filters reset the page, different errors roll back one transaction), write ONE test on the outcome, not N one-per-trigger.
  - [Why] One-per-trigger tests miss the next trigger someone adds; a test on the shared outcome covers new triggers too.

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
  - [Why] A compound assertion hides which half broke — you re-read the body to find out, instead of scanning the title.

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
  - [Why] Readers scanning "what does this do when it works?" shouldn't wade through error paths to find out.

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
  - [Why] Shared state makes outcome depend on run order — pass 9 times, fail the 10th, and rerun replaces investigate.

- [Instruction] **No randomness in test inputs or assertions — use fixed values.**
  - [Why] A random input means a failure may not reproduce, so the signal is unactionable and erodes trust in the suite.

- [Instruction] Clone inputs before passing them to mutating functions.
  - [Why] A function that mutates its argument corrupts the shared fixture, so the next test silently inherits it.

- [Instruction] **Pin the clock with fake timers whenever the system under test reads it (directly or via helpers); test names like "expired", "deadline", "min", "cap" are the tell.**
  - [Why] Without a frozen clock, a time-derived test passes today and silently fails once the wall-clock crosses its threshold.

- [Instruction] **File a `[Scout]` for any observed test flake (intermittent failure, OOM, timing race) immediately, even before the cause is clear.**
  - [Why] A flake wastes time chasing bugs that aren't there; left unfiled, flakes pile up until the suite guards nothing.

- [Instruction] Tests should not break when the implementation changes the order of items in a collection, unless order is part of the contract.
  - [Why] Asserting exact array order couples tests to implementation — changed iteration order shouldn't break behavior.

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
  - [Why] Cryptic mock data (`name: "x"`) hides bugs that surface only with realistic shapes (encoding, length, casing).

- [Instruction] Reach any test state by extending the shared factory with overrides — never monkey-patch fixture internals or build one-offs in the test body.
  - [Why] A one-off or monkey-patch drifts from the shared fixture and hides setup from the next reader.

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
  - [Why] Hardcoding the literal means an enum rename silently breaks production while the test still passes on the old value.

  - [Example] A mock factory that hardcodes `'PLENO'` while production uses `BrandSlugs.PLENO = 'pleno'` passes against its own mock but never matches production's shape — and TypeScript can't catch it.

- [Instruction] Never use an `as` cast in a test to inject a value the type or contract forbids; pass a valid domain value instead.
  - [Why] A forced cast fabricates an input production can never receive, so the test guards a case that can't happen.

- [Instruction] When a test deliberately exercises an out-of-domain or otherwise-unexpected value, name that intent in its title.
  - [Why] Without it a reader takes the odd value for a mistake instead of an intentional case.

- [Instruction] Parametrize inputs only when it keeps tests readable, or when writing them one-by-one doesn't scale; split back to separate tests once bodies diverge.
  - [Why] Parametrization's only payoff is dedup; once bodies diverge, the shared harness obscures what each case asserts.

- [Instruction] Keep test-file helpers inline until a second file needs them — and even at 2+ callers, stay inline when a helper would hide what's being asserted.
  - [Why] Grasp-at-a-glance beats DRY in tests — the body stays readable as documentation, and dedup isn't worth losing that.

## Test integrity & maintenance

### Assert real behavior, not implementation

- [Instruction] **CRITICAL: Let the system under test do the work — the test must encode an independent expectation, not recompute what the code does.**
  - [Why] If the test reproduces the logic, both move together: a production bug gets mirrored in the test and still passes.

[Example]
```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```

- [Instruction] Hand-code regression baselines as explicit expected values — never `f(X) === f(X)`, which only proves `f` is deterministic and can never fail.
  - [Why] A real regression guard needs a value you wrote down that the code might get wrong — self-comparison checks nothing.

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
  - [Why] Log assertions are brittle, tautological, and clutter the suite — the behavior test carries the same signal.

### Durable regression coverage

- [Instruction] **CRITICAL: Write a failing regression test that reproduces the bug before the fix lands; `debug-standards` holds the full rule.**
  - [Why] The failing test proves you've reproduced the real bug and turns into the guard that stops it from regressing.

- [Instruction] When you move code, move its tests too (if they exist) — adapt them to the new path, don't drop the coverage.
  - [Why] Leaving tests behind during a move is silent regression risk — the next bug in that area has no test to catch it.

- [Instruction] Prefer durable debugging artifacts — a failing test or committed debug script — over throwaway scratchpads.
  - [Why] A scratchpad vanishes when the session ends, leaving the next person who hits the bug no signal to find.

### Question every skipped test

- [Instruction] **Every `.skip` — yours or someone else's, old or new — owes a written justification (inline comment or linked ticket).**
  - [Why] Skipped tests are silent debt that grows quietly, and a tell for AI slop — scaffolding that never lands.

- [Instruction] Delete dead skips — a stale one (old, no follow-up commits, referenced code gone or changed), or the whole file when 100% of its tests are skipped.
  - [Why] A stale skip pads the count with tests mapping to no real code; a fully-skipped file adds only audit cost.

- [Instruction] Un-skip and run when the condition that justified the skip may have lifted.
  - [Why] If it passes, the skip outlived its purpose; if it fails meaningfully, it just caught a real gap.

- [Instruction] When the answer is "delete," capture the investigation (what was tried, why the skip is dead, what code it would have guarded) in the commit body.
  - [Why] The next reader who wonders why that coverage vanished needs the reasoning, or they re-litigate the same dead skip.
