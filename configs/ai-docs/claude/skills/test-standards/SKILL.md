---
description: "Test examples and anti-patterns covering a broad range of topics; headliners include descriptive BDD-like titles, realistic mock data, parametrized suites, order-independent assertions, and not reproducing logic under test — this list is illustrative, not exhaustive. USE PROACTIVELY when writing, reviewing, refactoring, or debugging tests — the skill often has relevant guidance beyond what the headliners above suggest."
user-invocable: false
---

# Test Standards -- Examples & Patterns

Reference examples for the TEST rules defined in CLAUDE.md.

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
