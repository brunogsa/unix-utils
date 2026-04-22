---
description: "Workflow examples covering a broad range of topics; headliners include designing test titles across all layers before any implementation, and RED-GREEN-REFACTOR starting with the most-forcing test case — this list is illustrative, not exhaustive. USE PROACTIVELY when planning implementation for a non-trivial task, starting a new feature, or breaking down work — the skill often has relevant guidance beyond what the headliners above suggest."
user-invocable: false
---

# Workflow Standards -- Examples & Patterns

Reference examples for the WORKFLOW rules defined in CLAUDE.md.

---

## Test Title Design (integration up front; unit tests only for pre-known pure helpers)

```javascript
// Integration test titles (outer layer) — all designed upfront
describe("CreateOrderUseCase", () => {
  it("should unpack non-shrinked kit children as avulsos in the order payload");
  it("should passthrough kit when all children are shrinked");
  it("should throw when kit metadata fetch fails");
});

// Unit test titles — ONLY for helpers known upfront regardless of design
// or implementation choices (e.g., pure normalizers, parsers, validators).
describe("normalizeProductPrice", () => {
  it("should return zero for bonus items");
  it("should apply discount when provided");
});
// Do NOT eagerly design tests for helpers pulled on demand during
// RED-GREEN — their tests are written test-first at the moment the
// caller first demands them, so the caller shapes the helper's API.
```

Review titles with user, then start RED-GREEN.

## RED → GREEN, Most Forcing Case First

```
1. Design upfront test titles (integration + any pre-known pure helpers) → review
2. Pick the most forcing integration test case (needs the most real logic)
3. RED: write that test body
4. GREEN: implement just enough to pass. When a helper is needed:
   - write its test first (RED for helper)
   - implement it (GREEN for helper)
5. Commit: test + impl (+ any pulled helper tests/impl) as one logical unit
6. Repeat for the next case, building on what exists
7. Backfill remaining integration test bodies once core logic is solid
```
