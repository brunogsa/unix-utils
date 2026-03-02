---
description: "Top-Down Breadth First (TDBF) coding pattern with full example showing rounds, skeletons, and BFS file order"
user-invocable: false
---

# Top-Down / Breadth First Coding -- Example

Reference example for the TDBF Coding rule in CLAUDE.md. Use when writing new functions/modules.

---

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
