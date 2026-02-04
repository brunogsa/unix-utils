---
description: "Code standards with examples for layered architecture, enums, naming, loops, logging, formatting, and clean code patterns"
user-invocable: false
---

# Code Standards -- Examples & Patterns

Reference examples for the CODE rules defined in CLAUDE.md.

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
// === Round 1: Implement processOrder, create its skeletons ===

function processOrder(order) {
  const validated = validateOrder(order);
  const priced = applyPricing(validated);
  const receipt = generateReceipt(priced);
  return receipt;
}

// @param order {Order} -- raw order from API
// @returns {Order} -- validated order
// @throws {ValidationError} -- if fields missing or out of stock
function validateOrder(order) { /* TODO */ }

// @param order {Order} -- validated order
// @returns {Order} -- order with discountedTotal and taxTotal
function applyPricing(order) { /* TODO */ }

// @param order {Order} -- priced order with totals
// @returns {Receipt} -- formatted receipt with line items
function generateReceipt(order) { /* TODO */ }


// === Round 2: Implement validateOrder, create its skeletons ===

function validateOrder(order) {
  assertRequiredFields(order);
  assertInventoryAvailable(order.items);
  return order;
}

// @param order {Order} -- order to validate
// @throws {ValidationError} -- if id, items, or customer missing
function assertRequiredFields(order) { /* TODO */ }

// @param items {OrderItem[]} -- items to check
// @throws {ValidationError} -- if any item is out of stock
function assertInventoryAvailable(items) { /* TODO */ }


// === Round 3: Implement applyPricing, create its skeletons ===

function applyPricing(order) {
  const discounted = applyDiscounts(order);
  const taxed = calculateTaxes(discounted);
  return taxed;
}

// @param order {Order} -- validated order
// @returns {Order} -- order with discountedTotal applied
function applyDiscounts(order) { /* TODO */ }

// @param order {Order} -- discounted order
// @returns {Order} -- order with taxTotal calculated
function calculateTaxes(order) { /* TODO */ }


// === Round 4: Implement generateReceipt, create its skeletons ===

function generateReceipt(order) {
  const lines = formatLineItems(order.items);
  return { lines, total: order.discountedTotal + order.taxTotal };
}

// @param items {OrderItem[]} -- priced items
// @returns {string[]} -- formatted line strings
function formatLineItems(items) { /* TODO */ }


// === Rounds 5-9: Implement leaf functions (no new skeletons) ===
// assertRequiredFields → assertInventoryAvailable → applyDiscounts
// → calculateTaxes → formatLineItems


// === Final file order (BFS queue) ===
// processOrder → validateOrder → applyPricing → generateReceipt
// → assertRequiredFields → assertInventoryAvailable → applyDiscounts
// → calculateTaxes → formatLineItems
```

```javascript
// BAD: Bottom-up / depth-first
// Implements the deepest helper first without knowing the full picture

function assertRequiredFields(order) {
  if (!order.id) throw new Error('Missing id');
  // ...
}

// Then builds upward, discovering the interface doesn't fit
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

