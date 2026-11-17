# More examples

Worked bad/good contrasts moved out of `SKILL.md`, grouped by the section whose rule each one illustrates.

## Descriptive titles (BDD-like)

- [Example]
```
Bad:  "should AND fieldA IN with fieldB NOT IN when both provided"   (operator mechanics)
Bad:  "regression: PR #2034 last-spread-wins on flowCode"            (session/branch history)
Good: "should subtract excludeFlowCodes from the flowCode include set when both filters are provided"
```

## One test per distinct cause

- [Example]
```ts
// Bad - three tests, one per trigger, all asserting the same behavior:
it('should reset page to 1 when status filter changes', ...);
it('should reset page to 1 when search input changes', ...);
it('should reset page to 1 when sort order changes', ...);

// Good - one test of the underlying invariant:
it('should reset page to 1 on every refetch of the dataset', ...);
```
