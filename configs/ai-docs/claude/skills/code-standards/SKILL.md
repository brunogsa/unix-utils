---
name: code-standards
description: "Code principles + examples. USE PROACTIVELY on ANY code edit — writing, refactoring, naming, controllers/use cases, error handling, logging, scripts, or reviewing code. Fires even on small tweaks."
user-invocable: false
words-budget: 5096
instructions-budget: 80
---

# Code Standards

Principles for any code edit. Each section has a principle + WHY, with paired examples co-located under the principle.

## Code top-down, pull helpers on demand

- [Instruction] Start from the controller/worker layer and work downward;
- [Instruction] Don't write a function until something calls it.

[Why] Helpers shaped by real demand match callers; speculative ones don't.

## Name by purpose, not mechanism

[Instruction] Name functions and variables by what the caller gets, not how it works.

[Why] Implementation changes with refactors but the caller's contract shouldn't — a mechanism-named function starts lying after a body rewrite.

[Examples]
```javascript
// Bad -- describes the mechanism (what it does internally):
function collectAllColumns(rows) { /* ... */ }
function getValues(rows) { /* ... */ }

// Good -- describes the purpose/output (what the caller gets):
function buildCsvColumnOrder(rows) { /* ... */ }
function extractUniqueEmails(rows) { /* ... */ }
```

## Self-explanatory names — no context-dependent jargon

[Instruction] Applies to identifiers. See CLAUDE.md ("Self-describing artifacts — no context-dependent shorthand") for the principle.

Domain elaboration: avoid numbered phases (`Phase-1`), abbreviated prefixes (`sa`/`sap`), platform-colliding acronyms (`SAP` vs ERP).

Heuristic: a reviewer skimming the diff in 18 months should not need to ask "what is `sa`?" or "what does Phase-2 do here?".

[Examples]
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

## Locale-neutral naming in shared APIs

[Instruction] Prefer `documentNumber` over `cnpj` in shared internal code. End-user strings use i18n. Locale-specific OK where the locale IS the contract (URL segments, validators).

[Why] A `cnpj` field locks shared code to one country's regulations; `documentNumber` survives expansion.

## Name booleans positively

[Instruction] Prefix with `is`/`has`/`should`/`can`. Avoid negating a negative ("not-not-X").

[Why] Double negatives force the reader to flip the truth value at every read site — a cognitive tax.

[Examples]
```ts
// Bad -- negation of a negative:
if (!item.isShrinked) { ... }

// Good -- name the positive condition:
const isExpandable = !item.isShrinked;
if (isExpandable) { ... }
```

## Extract long conditions into named booleans

[Instruction] When a condition spans 3+ clauses, extract it into a named boolean used at the if site.

[Why] A multi-clause condition at the call site hides intent; a named boolean documents it.

[Examples]
```ts
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) { ... }
```

## Use consistent naming conventions

[Instruction] Collections plural for arrays, suffix for Sets/Maps. Pipeline vars: stage prefix when shape stays the same, distinct name when shape changes.

[Why] Convention is a free type system — drop the suffix and the reader has to look up the type every time.

## Single-responsibility

[Instruction] One thing at one level of abstraction.

[Why] N concerns means N reasons to change — each one risks regressing the others.

## Cap nesting depth

[Instruction] More than 2 levels is a smell; more than 3 is a refactor. Extract inner units into named helpers; flatten via early returns.

[Why] Each nesting level multiplies the mental state the reader holds — bugs hide where "I don't understand" lives.

Heuristic: more than 2 levels of nesting in one function body is a smell; more than 3 is a refactor request.

[Examples]
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

## Avoid global mutable state

[Instruction] Pass data through params and return values.

[Why] Module-scope state makes data flow invisible and breaks unit isolation.

## Pure functions by default

[Instruction] Isolate I/O into thin boundary functions.

[Why] Pure functions test without mocks; I/O is the part that needs infrastructure — keep it at the edges.

## Inject what's hard to mock

[Instruction] Pass I/O collaborators as parameters.

[Why] Imported singletons bind at module load — you can't substitute them per test.

## Spec cases ≠ code branches

[Instruction] When a spec defines N cases, design a unified pipeline that naturally produces correct output for all of them. Fewer branches, fewer bugs.

[Why] A 1:1 if/else translation of spec cases couples control flow to the spec — every requirement change demands a code change.

## Functions ≥2 params → named-param object. Pass specific fields, not whole objects

[Instruction] Use named-param objects for any function with 2+ params; in the signature, list the specific fields the function needs rather than passing whole config objects.

[Why] Positional args lose meaning at call sites (`configure(3, 5000)` — what's 3?); fat-object params hide internal coupling.

[Examples]
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

[Instruction] Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).

[Why] I/O changes most often (HTTP → queue → CLI); pure use cases survive every swap.

- [Instruction] Avoid duplicate `info` logs across layers — controller is the natural owner.
- [Instruction] Helpers stay quiet (`debug` for diagnostics, or `info` only when owning a concern the controller can't see).

[Examples]
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

[Instruction] Builder/factory functions should only assemble data from explicit parameters. Business decisions (conditionals, calculations, transformations) belong at the use-case/caller level.

[Why] Business decisions buried inside builders hide the actual rules; pulling them out keeps business logic visible and builders reusable.

[Examples]
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

## Log progress in I/O loops

[Instruction] Counter format: `[3/70] item-name`.

[Why] Silent loops feel hung; the counter answers "progressing?" and "stuck where?" at once.

## Use structured logging

[Instruction] Level, timestamp, transactionId, message, context.

[Why] Structured logs are queryable; free-text needs grep + human pattern matching.

[Examples]
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

## Log full diagnostic context on failures

[Instruction] Include the full input that caused the error.

[Why] A failure log without input is a hunt; with input, it's a reproduction case.

## Logs must never crash the flow

[Instruction] Every reducer/accessor/template expression must tolerate undefined or empty inputs.

[Why] Telemetry that crashes the flow removes the very thing meant to help you debug.

[Examples]
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

[Instruction] `info` logs counts/IDs/status; matching `debug` log carries full payload (sorted arrays). Toggle `debug` during incident, off after.

[Why] `info` runs always (cheap, scannable); `debug` flips on during incidents — config flag beats code change.

In prod: `debug` is off by default. During launch / incident, flip the config — no code change, no deploy.

[Examples]
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
  schoolDocNumbers: [...input.schoolCNPJ].sort(),
  agreementIds: result.agreements.map((a) => a.agreementId).sort(),
  skuCodes: result.agreements.flatMap((a) => a.skus).sort(),
});
```

## Sensitive fields in log payloads: surface, never silently include or drop

[Instruction] When proposing a log payload that includes identifiers or potentially sensitive data (CPF, CNPJ, email, address, tokens, free-text), surface the candidate fields explicitly and ask before shipping.

- [Instruction] Don't silently include sensitive fields.
- [Instruction] Don't silently drop them either.

[Why] Silent-include leaks PII; silent-drop rob the user of the decision. Both replace an explicit per-field choice with a default the user never made.

## Never retry indefinitely

[Instruction] Always cap consecutive retries.

[Why] Uncapped retries during an outage become a self-inflicted DDoS on the upstream.

## Scripts: human-friendly

[Instruction] `--help` and a comment header with usage + examples. Help → stdout + exit 0; bad input → stderr + exit 1.

[Why] The next user (often future-you) won't read the source — `--help` is the contract surface.

[Examples]
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

## Scripts: right language

[Instruction] Bash for linear/glue, Node.js for structured data or complex flow.

[Why] Bash excels at process composition but degrades on structured data — pick the grain that matches.

## Scripts: Unix philosophy

[Instruction] One thing well, compose via pipes, accept behavior as parameters.

[Why] One thing well composes; a monolithic script becomes a private API nobody reuses.

## Input validation ALWAYS present on controllers

[Instruction] Defend at trust boundaries (user input, external APIs, queue payloads); trust internals.

[Instruction] When an internal invariant breaks, fail fast and loudly — never silently coerce, swallow, or default away the error.

[Why] Validation at every boundary is paranoid; validation only at trust boundaries is honest about the threat model.

## Normalize data at entry point

[Instruction] Convert string dates, numbers-as-strings to proper types immediately after validation.

[Why] Defer normalization and you scatter `parseInt`/`new Date` across the codebase.

## Extract magic values into constants

[Instruction] Use enums when applicable. Share constants across layers (UI + server) via single import.

[Why] A `10` scattered across files becomes a coordination problem when it changes — a constant is grep-able.

[Examples]
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

[Examples]
```ts
// Bad — `MAX_SCHOOLS = 10` duplicated in UI and server
// SchoolFilterCombobox.tsx:  const MAX_SCHOOLS = 10;
// schemas.ts:                schoolCNPJ: z.array(...).max(10);

// Good — single shared constant
// src/constants/contract-validation.ts:  export const MAX_SCHOOLS = 10;
// Both UI and server import it.
```

## Distinguish "missing" from "intentional zero/empty"

[Instruction] Check null/undefined, not falsiness.

[Why] `if (count)` treats `0` and `undefined` identically — falsiness checks paper over the distinction and ship bugs.

## Don't wrap trivial expressions

[Instruction] Wrappers earn existence by adding behavior (retry, logging, validation), not by renaming a clear stdlib call.

[Why] A `getCurrentTime()` wrapper around `Date.now()` adds indirection with no payoff.

## Helper-extraction must raise 2 bars: readability AND cognitive load

[Instruction] A helper for 2–4 callsites earns its place only when extraction **strictly raises both** bars. Both must rise — not one.

1. [Instruction] **Readability bar** — does the helper's name communicate intent better than the inline form?
   - [Examples] If the inline pattern is already self-evident (a 3-line `JSON.parse(decodeURIComponent(raw))`), a helper named `extractTrpcInputField` adds indirection without revelation.
2. [Instruction] **Cognitive load bar** — does extraction shrink the working set the reader has to hold?
   - [Examples] A 10-line helper hiding a 2-line pattern doesn't reduce load.
   - [Examples] It spreads the same load across two files (call site + helper body); the reader chases both.

[Instruction] If either bar fails, **inline wins**. DRY is not a value on its own — it's a heuristic for reducing complexity.

[Why] When extraction adds complexity, DRY is the wrong heuristic for that case.

## Decompose dense, complex expressions

[Instruction] Break unfamiliar APIs, nested callbacks into named intermediate variables.

[Why] Dense expressions optimize for character count — readability beats brevity.

[Examples]
```javascript
// Bad -- requires mental unpacking:
const paths = Array.from({ length: count }, (_, i) => resolve(dir, `batch-${i + 1}.csv`));

// Good -- each step is clear:
const paths = [];
for (let i = 1; i <= count; i++) {
  paths.push(resolve(dir, FILE_NAMES.batch(i)));
}
```

## CRITICAL: Decompose long render trees into named sub-components

[Instruction] CRITICAL: When a render function or JSX block exceeds ~50 lines with multiple conditional branches, extract each branch into a self-naming sub-component.

- [Examples] Inline same-file is fine when not reused.
- [Examples] Target shape: every conditional block becomes a one-line `<Foo prop={...} />`; parent JSX reads as the page's outline.
- [Examples] Preserve data-testids and behavior — you're only moving JSX, not changing it.
- [Examples] Applies to any framework's render tree (React JSX, Vue templates, Svelte markup, JSX-like DSLs).

[Why] Flat conditional JSX with anonymous `<div>` blocks forces every reader to parse every branch to understand the page outline.

Named sub-components make the top level scannable — `{isOverCap && <OverCapBanner />}` reads its intent in one glance; the 7-line div behind it doesn't. Render functions are outlines, not encyclopedias.

[Examples]
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

## Abstract counter-intuitive APIs

[Instruction] Wrap with intuitive interfaces.

[Why] Every call site of a counter-intuitive API is a future bug site.

## Context object for cross-cutting concerns

[Instruction] Pass a single context (request ID, user, trace) instead of adding params everywhere.

[Why] Cross-cutting concerns grow new params across every layer without a context — a hidden propagation tax.

## Parallelize CPU-bound work

[Instruction] Workers for CPU, async for I/O.

[Why] Async on CPU-bound tasks blocks the event loop — concurrency in name only.

## Don't optimize without evidence

[Instruction] Simplest correct version first. Memoization/caching needs profiling proof OR a clear Big-O reason.

[Why] Premature optimization adds complexity without evidence — profile first.

## Resilient batch operations

[Instruction] Idempotent, resumable, crash-resilient. Best-effort report on fatal failure.

[Why] Long batches eventually crash mid-flight; without resumability, you re-run the whole thing and risk duplicates.

## Prefer composition over inheritance

[Instruction] Small, focused pieces over deep class hierarchies.

[Why] Inheritance couples to the parent's implementation, not just its contract; composition couples to interfaces only.

## Fail loudly, not silently

[Instruction] Errors propagate or get logged explicitly.

[Why] A crash you see beats a silent corruption you don't — silent failures hide until the data is wrong downstream.
