# More examples

Worked bad/good contrasts moved out of `SKILL.md`, grouped by the section whose rule each one illustrates.

## Lower reviewer load: nesting & dense lines

- [Example]
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

- [Example]
```javascript
// Bad -- requires mental unpacking:
const paths = Array.from({ length: count }, (_, i) => resolve(dir, `batch-${i + 1}.csv`));

// Good -- each step is clear:
const paths = [];
for (let i = 1; i <= count; i++) {
  paths.push(resolve(dir, FILE_NAMES.batch(i)));
}
```

## Extraction: helpers, components, wrappers

- [Example]
```tsx
// Bad — flat return; parent has no scannable outline:
return (
  <div>
    <h1>{title}</h1>
    {isOverCap && (
      <div className="banner banner--warning">
        <Icon name="warning" />
        <span>Cap reached: {currentCount} / {maxCount}</span>
        <Button onClick={onClear}>Clear</Button>
      </div>
    )}
    {isLoading && <Spinner />}
    {!isLoading && items.length === 0 && (
      <div className="empty">
        <Illustration name="empty-box" />
        <p>{emptyMessage}</p>
      </div>
    )}
    {!isLoading && items.length > 0 && <ul>{items.map(...)}</ul>}
  </div>
);

// Good — parent reads as outline; each branch is one line:
return (
  <div>
    <h1>{title}</h1>
    {isOverCap && <OverCapBanner current={currentCount} max={maxCount} onClear={onClear} />}
    {isLoading && <Spinner />}
    {!isLoading && items.length === 0 && <EmptyState message={emptyMessage} />}
    {!isLoading && items.length > 0 && <ItemList items={items} />}
  </div>
);
```

## Name by purpose, clearly

- [Example]
```javascript
// Bad -- describes the mechanism (what it does internally):
function collectAllColumns(rows) { /* ... */ }
function getValues(rows) { /* ... */ }

// Good -- describes the purpose/output (what the caller gets):
function buildCsvColumnOrder(rows) { /* ... */ }
function extractUniqueEmails(rows) { /* ... */ }
```

- [Example]
```ts
// Bad — `hasApplied` implies an event tracker, but is actually a URL-state derivative.
const hasApplied = appliedCNPJs.length > 0;
// A reader debugging "why are we in slow mode after clearing?" gets misled twice:
// once by the name (implies sticky), once by the derivation (it isn't).

// Good — rename to match the question it answers:
const isSlowMode = appliedCNPJs.length > 0;
// The identifier now reads as the mode gate it actually is.
```

- [Example]
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

- [Example]
```ts
// Bad — the type needs a comment to say what "entry" means:
/** One sold sourcing collection's contribution to a resolved child SKU. */
type Entry = { resolvedSku: string; quantidadeVenda: number };

// Good — the name itself says what it holds; the comment becomes unnecessary:
type SourcingContribution = { resolvedSku: string; quantidadeVenda: number };
```

## Booleans, conditions & naming conventions

- [Example]
```ts
// Bad -- negation of a negative:
if (!item.isShrinked) { ... }

// Good -- name the positive condition:
const isExpandable = !item.isShrinked;
if (isExpandable) { ... }
```

- [Example]
```ts
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) { ... }

// Negated quantifier — one clause, same decode cost:
const hasNoPriceableItem = !items.some((item) => item.precoTotal > 0);
if (hasNoPriceableItem) { ... }
```

## Layering & responsibilities

- [Example]
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

- [Example]
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

## Functions, purity & side effects

- [Example]
```ts
// Bad — name describes the operation; reads naturally only inside `setFailures`.
function withSchoolAgreementFetchError(failures, schoolDocNumber, error): Failures { ... }
setFailures((prev) => withSchoolAgreementFetchError(prev, schoolDocNumber, error));
// Parsed left-to-right: "with-school-agreement-fetch-error-applied-to-prev" — incomplete without setFailures.

// Good — name describes the output; reads as a noun on its own.
function getPreviousFailuresWithNewSchoolAgreementFetchError(failures, schoolDocNumber, error): Failures { ... }
setFailures((prev) => getPreviousFailuresWithNewSchoolAgreementFetchError(prev, schoolDocNumber, error));
// Parsed left-to-right: "set failures to: [the previous failures with a new school-agreement fetch error]".
```

- [Example]
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
