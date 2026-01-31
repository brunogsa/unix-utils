---
description: "Test standards with examples for naming, mock data, parametrized tests, and avoiding logic reproduction"
user-invocable: false
---

# Test Standards -- Examples & Patterns

Reference examples for the testing rules defined in CLAUDE.md.

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

## Don't Reproduce Logic Under Test

```ts
// Bad -- reproduces filtering logic:
const filtered = items.filter(...);
expect(myFunc(filtered)).toEqual(...);

// Good -- let the system under test do the work:
expect(myFunc(items)).toEqual(expectedFiltered);
```
