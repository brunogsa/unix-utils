---
description: "Workflow examples covering a broad range of topics; headliners include designing test titles across all layers before any implementation, and RED-GREEN-REFACTOR starting with the most-forcing test case — this list is illustrative, not exhaustive. USE PROACTIVELY when planning implementation for a non-trivial task, starting a new feature, or breaking down work — the skill often has relevant guidance beyond what the headliners above suggest."
user-invocable: false
---

# Workflow Standards -- Examples & Patterns

Reference examples for the WORKFLOW rules defined in CLAUDE.md.

---

## Test Title Design (all layers, before implementation)

```javascript
// Integration test titles (outer layer)
describe("CreateOrderUseCase", () => {
  it("should unpack non-shrinked kit children as avulsos in the order payload");
  it("should passthrough kit when all children are shrinked");
  it("should throw when kit metadata fetch fails");
});

// Unit test titles (inner layer)
describe("unpackKitItems", () => {
  it("should replace kit 1:1 with single avulso");
  it("should extract non-shrinked sold children and adjust kit price");
  it("should throw when child prices sum != kit price");
});
// Review ALL titles with user → commit → then start RED-GREEN
```

## RED → GREEN, Most Forcing Case First

```
1. Design test titles (all layers) → commit
2. Pick the most forcing test case (needs the most real logic)
3. RED: write that test body
4. GREEN: implement just enough — pull in helpers only when called
5. Repeat: next case, building on what exists
6. Backfill integration tests once core logic is solid
```

Start from the controller layer and work downward. Don't write a helper
until its caller demands it — the caller shapes the helper's API.
