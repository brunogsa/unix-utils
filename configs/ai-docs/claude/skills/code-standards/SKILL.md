---
description: "Code standards with examples for layered architecture, enums, naming, loops, logging, formatting, and clean code patterns"
user-invocable: false
---

# Code Standards -- Examples & Patterns

Reference examples for the coding rules defined in CLAUDE.md.

---

## Layered Architecture (Controllers/Commands + Use Cases)

```javascript
// BAD: Use case handles I/O
function processDataUseCase(filepath) {
  const data = readFileSync(filepath);  // I/O in use case!
  const result = doBusinessLogic(data);
  writeFileSync(outputPath, result);    // I/O in use case!
}

// GOOD: Controller handles I/O, use case is pure
// Use case (pure logic):
function processDataUseCase(data) {
  const result = doBusinessLogic(data);
  return result;
}

// Controller (orchestration + I/O):
function processDataCommand(filepath, outputPath) {
  try {
    const data = JSON.parse(readFileSync(filepath, 'utf8'));
    const result = processDataUseCase(data);
    writeFileSync(outputPath, JSON.stringify(result));
    console.log('Success!');
  } catch (error) {
    console.error('Failed:', error);
  }
}
```

---

## Deep Clone with Type Preservation

```javascript
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z$/;
const dateReviver = (key, value) => {
  if (typeof value === 'string' && ISO_DATE_PATTERN.test(value)) {
    return new Date(value);
  }
  return value;
};
const clone = JSON.parse(JSON.stringify(obj), dateReviver);
```

---

## Enums over Magic Strings

```ts
// Don't do this:
if (type === "KIT" || type === "AVULSO") {
  // do something
}

// Prefer:
enum ProductType {
  KIT = "KIT",
  AVULSO = "AVULSO"
}

if (type === ProductType.KIT || type === ProductType.AVULSO) {
  // do something
}

// Or for sets:
const TYPE_SET = new Set([ProductType.KIT, ProductType.AVULSO]);
if (TYPE_SET.has(type)) {
  // do something
}
```

---

## Avoid Negatives

```ts
// Bad:
if (!item.isShrinked) {
    // do something
}

// Good:
const isExpandable = !item.isShrinked;
if (isExpandable) {
    // do something
}
```

---

## Name Long Conditions

```ts
// Bad:
if (item.type === KIT && !item.isShrinked && item.children.length < 1) {
    // do something
}

// Good:
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) {
    // do something
}
```

---

## Prefer `for-of` over `for`

```ts
// Bad (index unused):
for (let i = 0; i < items.length; i++) {
    const item = items[i];
    // do something
}

// Good:
for (const item of items) {
    // do something
}
```

---

## Named Parameters for Functions (>=2 params)

```ts
// Bad:
function configure(a, b) {}

// Good:
function configure({ retries, timeout }) {}
```

---

## Loop Simplification

```ts
// Bad -- nested loops mixing concerns:
groups.forEach((group) => {
  group.lines.forEach((line) => {
    if (line.composition.length) processLine(line);
  });
});

// Good -- flatten then process:
const allLines = groups.flatMap(g => g.lines);
allLines.forEach((line) => {
  if (line.composition.length) processLine(line);
});
```

---

## Structured Logging

```ts
logger.info({
  level: "INFO",
  timestamp: "2025-07-10T15:12:34Z",
  transactionId: "550e8400-e29b-41d4-a716-446655440000",
  message: "User created successfully",
  userId: 666,
  userCpf: "***29430880"
});
```

---

## Formatting Preservation

```ts
// WRONG - Changed indentation and added spaces to empty line:
function example() {
    const x = 1;

    return x;
}

// CORRECT - Preserved exact formatting:
function example() {
  const x = 1;

  return x;
}
```

```bash
# WRONG - Changed quote style and indentation:
if [ "$status" == "active" ]; then
    echo "Running"
fi

# CORRECT - Kept original formatting:
if [ '$status' == 'active' ]; then
  echo "Running"
fi
```

---

## Avoid Round-Tripping Through Side Effects

```bash
# Bad -- writes to clipboard then reads it back in the same flow:
extract-data | copy-to-clipboard
result=$(read-from-clipboard)
use "$result"

# Good -- pass data directly:
result=$(extract-data)
use "$result"
```

---

## Top-Down / Breadth First Coding

```javascript
// === LAYER 1: Start with the high-level function ===

function processOrder(order) {
  const validated = validateOrder(order);       // doesn't exist yet
  const priced = applyPricing(validated);       // doesn't exist yet
  const receipt = generateReceipt(priced);      // doesn't exist yet
  return receipt;
}

// === Skeletons created during Layer 1 ===

function validateOrder(order) {
  // TODO: validate required fields, check inventory
}

function applyPricing(order) {
  // TODO: apply discounts, calculate taxes
}

function generateReceipt(order) {
  // TODO: format receipt with line items
}

// === LAYER 2: Implement skeletons, create new ones as needed ===

function validateOrder(order) {
  assertRequiredFields(order);          // doesn't exist yet
  assertInventoryAvailable(order.items); // doesn't exist yet
  return order;
}

function applyPricing(order) {
  const discounted = applyDiscounts(order);  // doesn't exist yet
  const taxed = calculateTaxes(discounted);  // doesn't exist yet
  return taxed;
}

// ... layer by layer until done
```

```javascript
// BAD: Bottom-up / depth-first
// Starts by implementing the deepest helper without knowing
// the full picture, often leads to rework

function assertRequiredFields(order) {
  // fully implemented first, before knowing how it's used
  if (!order.id) throw new Error('Missing id');
  // ...
}

// Then builds upward, discovering the interface doesn't fit
```

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

---

## Script Usage Documentation

```bash
#!/usr/bin/env bash
# extract-field - Extract a field from JSON lines
#
# Usage:
#   extract-field <field> [file]
#   cat data.jsonl | extract-field .name
#
# Examples:
#   extract-field .email users.jsonl          # extract email from file
#   extract-field '.address.city' users.jsonl # nested field
#   cat api-response.json | extract-field .id # from stdin

# BAD: No usage section, caller has to read the implementation to understand it
```

---

## Prefer Tests & Logs over Comments

```ts
// Bad -- comments explaining what code does:
function createRecord(user, data) {
  // Check permissions
  if (!hasPermission(user)) return false;
  return db.insert(data);
}

// Good -- self-documenting code + logs + tests:
function createRecordIfUserHasPermission(user, data) {
  if (!validateUserPermissions(user)) {
    logger.info({ message: "Record creation rejected", userId: user.id });
    return false;
  }
  return db.insert(data);
}

test("rejects when user lacks permission", () => {
  expect(createRecordIfUserHasPermission(userWithoutPerms, data)).toBe(false);
});
```
