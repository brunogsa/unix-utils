# Code Standards — Examples

Paired code examples for every principle in [../SKILL.md](../SKILL.md). Sections match SKILL.md headers — when applying a principle, load both files together.

## Name by purpose, not mechanism

```javascript
// Bad -- describes the mechanism (what it does internally):
function collectAllColumns(rows) { /* ... */ }
function getValues(rows) { /* ... */ }

// Good -- describes the purpose/output (what the caller gets):
function buildCsvColumnOrder(rows) { /* ... */ }
function extractUniqueEmails(rows) { /* ... */ }
```

## Self-explanatory names — no context-dependent jargon

```ts
// Bad — numbered phases force readers to recover spec context
const phaseOneReady = hasApplied && hasSchoolsData && hasAgreements;
const saSummaryQuery = trpc.errorCallbacks.summary.useQuery(...);  // sa = SalesAgreement? SAP? SAS?
const sapSummaryQuery = ...;  // SAP collides with the ERP

// Good — describe what each step does
const schoolsDataReady = hasApplied && hasSchoolsData && hasAgreements;
const salesAgreementSummaryQuery = trpc.errorCallbacks.summary.useQuery(...);
const salesAgreementProductSummaryQuery = ...;
```

## Name booleans positively

```ts
// Bad -- negation of a negative:
if (!item.isShrinked) { ... }

// Good -- name the positive condition:
const isExpandable = !item.isShrinked;
if (isExpandable) { ... }
```

## Extract long conditions into named booleans

```ts
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) { ... }
```

## Cap nesting depth

```ts
// Bad — Promise.all + .map + async + try/catch + conditional, all stacked
const perSchoolResults = await Promise.all(
  cnpjs.map(async (cnpj) => {
    const source = resolveDataSource(cnpj);
    try {
      const sa = await getSalesAgreements({ cnpj, source });
      if (sa.failed) {
        return { cnpj, agreements: [], failedBrands: sa.failed };
      }
      const skus = await getSKUs({ agreementIds: sa.ids });
      return { cnpj, agreements: enrich(sa.data, skus), failedBrands: [] };
    } catch (err) { ... }
  })
);

// Good — extract per-school helper with single concern
async function fetchSchoolData(cnpj: string) {
  const source = resolveDataSource(cnpj);
  return tryFetchAgreementsAndSkus({ cnpj, source });
}

const perSchoolResults = await Promise.all(cnpjs.map(fetchSchoolData));
```

## Functions ≥2 params → named-param object. Pass specific fields, not whole objects

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

## Layered architecture

```javascript
// BAD: Use case handles I/O
function processDataUseCase(filepath) {
  const data = readFileSync(filepath);  // I/O in use case!
  const result = doBusinessLogic(data);
  writeFileSync(outputPath, result);    // I/O in use case!
}

// GOOD: Controller handles I/O, use case is pure
function processDataUseCase(data) {
  return doBusinessLogic(data);
}

function processDataCommand(filepath, outputPath) {
  const data = JSON.parse(readFileSync(filepath, 'utf8'));
  const result = processDataUseCase(data);
  writeFileSync(outputPath, JSON.stringify(result));
}
```

## Builders assemble, use cases decide

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

## Use structured logging

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

## Logs must never crash the flow

```ts
// Bad — reduce throws on empty agreements
logger.info({
  message: 'Completed',
  skuCount: result.agreements.reduce((s, a) => s + a.skus.length, 0),
});

// Good — guard with optional chain + nullish fallback
logger.info({
  message: 'Completed',
  skuCount: result.agreements?.reduce((s, a) => s + (a.skus?.length ?? 0), 0) ?? 0,
});

// Even better — extract a safeSum helper if the pattern repeats
```

## Pair `info` with `debug` carrying full payload

```ts
logger.info({
  message: 'getSchoolsAgreementsAndSkus completed',
  service: 'ContractValidation',
  schoolCount: input.schoolCNPJ.length,
  agreementCount: result.agreements.length,
});

logger.debug({
  message: 'getSchoolsAgreementsAndSkus payload',
  service: 'ContractValidation',
  schoolDocNumbers: [...input.schoolCNPJ].sort(),  // sensitive: org identifiers — confirm with user
  agreementIds: result.agreements.map((a) => a.agreementId).sort(),
  skuCodes: result.agreements.flatMap((a) => a.skus).sort(),
});
```

## Scripts: human-friendly

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
```

## Extract magic values into constants

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
```

### Share across layers — one source of truth

```ts
// Bad — `MAX_SCHOOLS = 10` duplicated in UI and server
// SchoolFilterCombobox.tsx:  const MAX_SCHOOLS = 10;
// schemas.ts:                schoolCNPJ: z.array(...).max(10);

// Good — single shared constant
// src/constants/contract-validation.ts:  export const MAX_SCHOOLS = 10;
// Both UI and server import it.
```

## Decompose dense, complex expressions

```javascript
// Bad -- requires mental unpacking:
const paths = Array.from({ length: count }, (_, i) => resolve(dir, `batch-${i + 1}.csv`));

// Good -- each step is clear:
const paths = [];
for (let i = 1; i <= count; i++) {
  paths.push(resolve(dir, FILE_NAMES.batch(i)));
}
```
