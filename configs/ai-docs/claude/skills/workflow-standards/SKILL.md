---
description: "Workflow standards with examples for test-first design, verification approaches, and development process patterns"
user-invocable: false
---

# Workflow Standards -- Examples & Patterns

Reference examples for the WORKFLOW rules defined in CLAUDE.md.

---

## Test Title Design (before implementation)

```javascript
// === STEP 1: Design test titles only ===

describe("processOrder", () => {
  it("should return a receipt with all line items when order is valid");
  it("should throw when required fields are missing");
  it("should apply percentage discount before calculating taxes");
  it("should throw when item is out of stock");
});

// Review these titles with the user → validates understanding of behavior

// === STEP 2: Implement tests (RED) ===
// === STEP 3: Implement code (GREEN) ===
// === STEP 4: Refactor ===
```

```javascript
// BAD: Jump straight to implementing tests without designing the suite
// Leads to missing cases, unclear scope, and rework
```
