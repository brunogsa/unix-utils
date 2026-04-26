---
description: "Code guidelines and anti-patterns. USE PROACTIVELY when writing, refactoring, or reviewing any code."
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

## Boolean Naming

```ts
// Bad -- negation of a negative:
if (!item.isShrinked) { ... }

// Good -- name the positive condition:
const isExpandable = !item.isShrinked;
if (isExpandable) { ... }

// Bad -- boolean named as negative, then negated:
if (!isKnownNonTerminal) { ... }

// Good -- name the guard directly:
const isUnexpectedStatus = status !== 'Running' && status !== 'Scheduled';
if (isUnexpectedStatus) { ... }

// Also: extract long conditions into named booleans:
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) { ... }
```


---

## Decompose Dense Expressions

```javascript
// Bad -- requires mental unpacking:
const paths = Array.from({ length: count }, (_, i) => resolve(dir, `batch-${i + 1}.csv`));

// Good -- each step is clear:
const paths = [];
for (let i = 1; i <= count; i++) {
  paths.push(resolve(dir, FILE_NAMES.batch(i)));
}
```

---

## Named Parameters for Functions (>=2 params)

```ts
// Bad:
function configure(retries, timeout) {}

// Good:
function configure({ retries, timeout }) {}
```

---

## Pass Specific Fields, Not Entire Objects

```javascript
// Bad -- signature hides what the function actually needs:
async function fetchLogs({ config, workDir }) {
  const query = buildQuery(config.logGroups);
  const { start, end } = buildTimeWindow({ radiusMinutes: config.logRadius });
}

// Good -- signature documents exact dependencies:
async function fetchLogs({ logGroups, logRadius, workDir }) {
  const query = buildQuery(logGroups);
  const { start, end } = buildTimeWindow({ radiusMinutes: logRadius });
}
```

---

## Naming: Purpose Over Mechanism

```javascript
// Bad -- describes the mechanism (what it does internally):
function collectAllColumns(rows) { /* ... */ }
function getValues(rows) { /* ... */ }

// Good -- describes the purpose/output (what the caller gets):
function buildCsvColumnOrder(rows) { /* ... */ }
function extractUniqueEmails(rows) { /* ... */ }
```


---

## Naming Conventions

```javascript
// Booleans -- prefix with is/has/should/can:
const isValid = order.items.length > 0;
const hasPermission = user.roles.includes('admin');
const shouldRetry = attempt < MAX_RETRIES;

// Collections -- plural for arrays, suffix for non-arrays:
const orders = [order1, order2];         // array → plural
const userIdSet = new Set(['a', 'b']);   // Set → suffixed
const errorMap = new Map();              // Map → suffixed

// Pipeline variables -- stage-prefix when shape stays the same,
// distinct name when shape changes:
const rawOrder = parseInput(body);
const validatedOrder = validate(rawOrder);   // same shape → prefix
const receipt = generateReceipt(validatedOrder); // different shape → new name

// Callbacks -- describe transformation when input isn't obvious:
function collect({ dirPath, rowToValue }) {}   // input→output
function process({ items, buildPayload }) {}   // output-only when obvious
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

## Builders Bundle, Use Cases Decide

Builder/factory functions should only assemble data from explicit parameters. Business decisions (conditionals, calculations, transformations) belong at the use-case/caller level. This maximizes both business logic visibility (decisions are where the reader looks for them) and builder reusability (the same builder works for different business rules).

```ts
// Bad -- business rule hidden inside builder:
function buildAvulso({ parentKit, child }) {
    return {
        sku: child.sku,
        price: child.isBonused ? 0 : child.price,     // business rule buried here
        discount: child.isBonused ? 0 : parentKit.discount,
    };
}

// Good -- business rule visible at call site, builder is a dumb assembler:
const price = child.isBonused ? 0 : child.price;
const discount = child.isBonused ? 0 : parentKit.discount;
buildAvulso({ parentKit, childSku: child.sku, price, discount });

function buildAvulso({ parentKit, childSku, price, discount }) {
    return { sku: childSku, price, discount, brandSlug: parentKit.brandSlug };
}
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

