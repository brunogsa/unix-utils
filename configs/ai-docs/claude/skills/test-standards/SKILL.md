---
name: test-standards
description: "Test guidelines and anti-patterns. USE PROACTIVELY when writing, reviewing, refactoring, or debugging tests."
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

## Don't Reproduce Logic Under Test

```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```
