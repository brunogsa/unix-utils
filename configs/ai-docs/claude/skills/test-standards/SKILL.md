---
name: test-standards
description: "Test design rules and anti-pattern examples. USE PROACTIVELY whenever writing a new test, picking test type (unit vs integration vs e2e), mocking dependencies, debugging a flake, or reviewing test code — even when user just says 'add a test'."
user-invocable: false
---

# Test Standards -- Examples & Patterns

Reference examples for the TEST rules defined in CLAUDE.md.

---

## Test-type hierarchy & preferences

Default to **integration tests** for behavior coverage. They survive internal refactors and exercise the path the caller actually takes. Mock at external/IO boundaries (DB, HTTP, queues, file system); prefer fakes and localstack-style emulators to bare mocks where the cost is reasonable. Blackbox by nature.

Add **unit tests** for leaf functions/modules — pure logic with no/few dependencies (parsers, normalizers, validators, formatters). Whitebox; expect tests to change when the implementation changes. Skip when the only "unit" is a thin glue function.

**E2E tests sparingly.** Slow and brittle by nature; flakiness erodes trust in the suite. Acceptable when the specific case is cheap (existing fixture, single happy-path Playwright run, smoke test). Don't make them the default.

**Manual tests** are allowed when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox). Log every manual check in `./manual-tests-evidences.md` (see `test-driven-development` for format) so the work is verifiable.

---

## Bug fix → start with a failing regression test

Reproduce the bug as a test first, watch it fail for the right reason, then fix. The test guards against recurrence and proves the fix actually addresses the cause.

```ts
// Good — regression test before the fix
it("should reject login when password contains trailing whitespace (regression: #1234)", () => {
  expect(login("user", "secret ")).toThrow("Invalid credentials");
});
```

The test fails (the bug exists) → fix the code → the test passes. Now it's a guarded behavior.

---

## Good Test Names

Title the **observable behavior** in domain language. Bad titles describe SQL/operator mechanics (`AND`, `IN`, `JOIN`), code structure (`if-else`, `early return`), or regression history (`PR #X`, `regression after merge`). Good titles read like a contract a non-engineer could verify.

```
Bad:  "should AND fieldA IN with fieldB NOT IN when both provided"   (operator mechanics)
Bad:  "regression: PR #2034 last-spread-wins on flowCode"            (session/branch history)
Good: "should subtract excludeFlowCodes from the flowCode include set when both filters are provided"
```

Other examples:
* "should throw when params are missing"
* "should default pageSize to 10"
* "should return user info when params are valid"

---

## Use Real-Like Mock Data

```ts
const mockUser = {
    id: "123",
    name: "Alice",
    email: "alice@example.com",
};
```

---

## Parametrized Test Inputs

```ts
const testCases = [
    { input: 1, expected: 2 },
    { input: 2, expected: 3 },
];

testCases.forEach(({ input, expected }) => {
    test(`should return ${expected} for input ${input}`, () => {
        expect(fn(input)).toBe(expected);
    });
});
```

---

## Avoid Order-Dependent Assertions

Tests should not break when the implementation changes the order of items in a collection, unless order is part of the contract. Asserting on exact array order couples tests to implementation details.

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

---

## Date-derived test stability — freeze the clock

Tests that depend on "now" (date math, expiry checks, `Date.now()`-derived caps) become time-bombs: the assertion passes today and silently fails in N months when wall-clock time crosses a threshold. Pin time with fake timers whenever the system under test reads the clock — even indirectly through helpers.

```ts
// Bad — relies on real wall-clock time:
it("caps the value at min when the deadline has passed", () => {
  // Passes today; will start failing once 'now' moves past the fixture's deadline
  expect(computeCap({ deadline: '2026-01-01' })).toBe(MIN_CAP);
});

// Good — pin 'now' to a deterministic instant:
import { vi } from 'vitest';

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-05-01T00:00:00Z'));
});

afterEach(() => {
  vi.useRealTimers();
});

it("caps the value at min when the deadline has passed", () => {
  expect(computeCap({ deadline: '2026-01-01' })).toBe(MIN_CAP);
});
```

Apply to: any test that exercises a code path branching on the current date, age comparisons, "expired"/"future" booleans, or relative-time formatting. If the test name contains "past", "future", "expired", "min", "cap", "deadline" etc. and the fixture date is hardcoded, freeze.

---

## Fixtures must support every state the tests assert on

When a single fixture is reused across tests that assert on different states (idle, loading, error, edge case), the fixture's defaults must allow each test to express its state without monkey-patching internals. If a test has to mutate the fixture in surprising ways to reach a state, the fixture is too narrow.

```ts
// Bad — fixture only supports the happy path; "expired" test has to dig into internals:
const baseAgreement = { signedAt: '2025-01-01', deadline: '2025-12-31' };

it('shows expired badge when past deadline', () => {
  // Forced to mutate or rebuild from scratch — coupling test to shape
  const agreement = { ...baseAgreement, deadline: '2020-01-01' };
  // ...
});

// Good — factory with overrides; every state is one named override away:
function createAgreement(overrides: Partial<Agreement> = {}): Agreement {
  return { signedAt: '2025-01-01', deadline: '2025-12-31', ...overrides };
}

it('shows expired badge when past deadline', () => {
  const agreement = createAgreement({ deadline: '2020-01-01' });
  // ...
});
```

When you add a new test that asserts on a state the fixture didn't anticipate, **extend the factory** (add a new override key, broaden a union type) rather than constructing one-offs in the test body. The factory is the contract; tests stay declarative.

---

## Don't Reproduce Logic Under Test

```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```

---

## Regression baselines: hand-coded shape, not self-comparison

A test that asserts `f(X) === f(X)` proves only that `f` is deterministic — it can never fail unless the system is non-deterministic. Regression baselines must be hand-coded values that the implementation could plausibly fail to produce. This is distinct from "Don't reproduce logic under test" (which is about the test recomputing what the code does); self-comparison is about the test asserting against its own runtime output.

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

The bad version cannot fail because both sides come from the same code path. A genuine regression guard must encode an *expectation* the implementation might miss.
