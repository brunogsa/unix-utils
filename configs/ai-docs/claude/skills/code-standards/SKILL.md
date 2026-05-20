---
name: code-standards
description: "Code principles + examples. USE PROACTIVELY on ANY code edit — writing, refactoring, naming, controllers/use cases, error handling, logging, scripts, or reviewing code. Fires even on small tweaks."
user-invocable: false
words-budget: 5096
---

# Code Standards

Principles for any code edit. Each section has a principle + WHY, with paired examples co-located under the principle.

## Code top-down, pull helpers on demand

- Start from the controller/worker layer and work downward;
- Don't write a function until something calls it.

Why: helpers shaped by real demand match callers; speculative ones don't.

## Name by purpose, not mechanism

What the caller gets, not how it works.

Why: implementation changes with refactors but the caller's contract shouldn't — a mechanism-named function starts lying after a body rewrite.

```javascript
// Bad -- describes the mechanism (what it does internally):
function collectAllColumns(rows) { /* ... */ }
function getValues(rows) { /* ... */ }

// Good -- describes the purpose/output (what the caller gets):
function buildCsvColumnOrder(rows) { /* ... */ }
function extractUniqueEmails(rows) { /* ... */ }
```

## Self-explanatory names — no context-dependent jargon

Applies to identifiers. See CLAUDE.md ("Self-describing artifacts — no context-dependent shorthand") for the principle.

Domain elaboration: avoid numbered phases (`Phase-1`), abbreviated prefixes (`sa`/`sap`), platform-colliding acronyms (`SAP` vs ERP).

Heuristic: a reviewer skimming the diff in 18 months should not need to ask "what is `sa`?" or "what does Phase-2 do here?".

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

Prefer `documentNumber` over `cnpj` in shared internal code. End-user strings use i18n. Locale-specific OK where the locale IS the contract (URL segments, validators).

Why: a `cnpj` field locks shared code to one country's regulations; `documentNumber` survives expansion.

## Name booleans positively

Prefix with `is`/`has`/`should`/`can`. Avoid negating a negative ("not-not-X").

Why: double negatives force the reader to flip the truth value at every read site — a cognitive tax.

```ts
// Bad -- negation of a negative:
if (!item.isShrinked) { ... }

// Good -- name the positive condition:
const isExpandable = !item.isShrinked;
if (isExpandable) { ... }
```

## Extract long conditions into named booleans

When a condition spans 3+ clauses, extract it into a named boolean used at the if site.

Why: a multi-clause condition at the call site hides intent; a named boolean documents it.

```ts
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) { ... }
```

## Use consistent naming conventions

Collections plural for arrays, suffix for Sets/Maps. Pipeline vars: stage prefix when shape stays the same, distinct name when shape changes.

Why: convention is a free type system — drop the suffix and the reader has to look up the type every time.

## Single-responsibility

One thing at one level of abstraction.

Why: N concerns means N reasons to change — each one risks regressing the others.

## Cap nesting depth

More than 2 levels is a smell; more than 3 is a refactor. Extract inner units into named helpers; flatten via early returns.

Why: each nesting level multiplies the mental state the reader holds — bugs hide where "I don't understand" lives.

Heuristic: more than 2 levels of nesting in one function body is a smell; more than 3 is a refactor request.

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

Pass data through params and return values.

Why: module-scope state makes data flow invisible and breaks unit isolation.

## Pure functions by default

Isolate I/O into thin boundary functions.

Why: pure functions test without mocks; I/O is the part that needs infrastructure — keep it at the edges.

## Inject what's hard to mock

Pass I/O collaborators as parameters.

Why: imported singletons bind at module load — you can't substitute them per test.

## Spec cases ≠ code branches

When a spec defines N cases, design a unified pipeline that naturally produces correct output for all of them. Fewer branches, fewer bugs.

Why: a 1:1 if/else translation of spec cases couples control flow to the spec — every requirement change demands a code change.

## Functions ≥2 params → named-param object. Pass specific fields, not whole objects

Signature documents exact dependencies.

Why: positional args lose meaning at call sites (`configure(3, 5000)` — what's 3?); fat-object params hide internal coupling.

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

Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).

Why: I/O changes most often (HTTP → queue → CLI); pure use cases survive every swap.

- Avoid duplicate `info` logs across layers — controller is the natural owner.
- Helpers stay quiet (`debug` for diagnostics, or `info` only when owning a concern the controller can't see).

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

Builder/factory functions should only assemble data from explicit parameters. Business decisions (conditionals, calculations, transformations) belong at the use-case/caller level.

Why: business decisions buried inside builders hide the actual rules; pulling them out keeps business logic visible and builders reusable.

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

Counter format: `[3/70] item-name`.

Why: silent loops feel hung; the counter answers "progressing?" and "stuck where?" at once.

## Use structured logging

Level, timestamp, transactionId, message, context.

Why: structured logs are queryable; free-text needs grep + human pattern matching.

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

Include the full input that caused the error.

Why: a failure log without input is a hunt; with input, it's a reproduction case.

## Logs must never crash the flow

Every reducer/accessor/template expression must tolerate undefined or empty inputs.

Why: telemetry that crashes the flow removes the very thing meant to help you debug.

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

`info` logs counts/IDs/status; matching `debug` log carries full payload (sorted arrays). Toggle `debug` during incident, off after.

Why: `info` runs always (cheap, scannable); `debug` flips on during incidents — config flag beats code change.

Sensitive fields (CPF, CNPJ, email, address, tokens, free-text): flag candidates and ask before shipping; don't silently include or drop.

In prod: `debug` is off by default. During launch / incident, flip the config — no code change, no deploy.

**AI flags risky fields; user decides.** When proposing a `debug` payload that includes identifiers or potentially sensitive data:
- Surface the candidate fields explicitly and ask before shipping.
- Don't silently include them.
- Don't silently drop them either — both rob the user of the decision.

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

## Never retry indefinitely

Always cap consecutive retries.

Why: uncapped retries during an outage become a self-inflicted DDoS on the upstream.

## Scripts: human-friendly

`--help` and a comment header with usage + examples. Help → stdout + exit 0; bad input → stderr + exit 1.

Why: the next user (often future-you) won't read the source — `--help` is the contract surface.

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

Bash for linear/glue, Node.js for structured data or complex flow.

Why: bash excels at process composition but degrades on structured data — pick the grain that matches.

## Scripts: Unix philosophy

One thing well, compose via pipes, accept behavior as parameters.

Why: one thing well composes; a monolithic script becomes a private API nobody reuses.

## Input validation ALWAYS present on controllers

Defend at trust boundaries (user input, external APIs, queue payloads); trust internals.

When an internal invariant breaks, fail fast and loudly — never silently coerce, swallow, or default away the error.

Why: validation at every boundary is paranoid; validation only at trust boundaries is honest about the threat model.

## Normalize data at entry point

Convert string dates, numbers-as-strings to proper types immediately after validation.

Why: defer normalization and you scatter `parseInt`/`new Date` across the codebase.

## Extract magic values into constants

Use enums when applicable. Share constants across layers (UI + server) via single import.

Why: a `10` scattered across files becomes a coordination problem when it changes — a constant is grep-able.

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

## Distinguish "missing" from "intentional zero/empty"

Check null/undefined, not falsiness.

Why: `if (count)` treats `0` and `undefined` identically — falsiness checks paper over the distinction and ship bugs.

## Don't wrap trivial expressions

Wrappers earn existence by adding behavior (retry, logging, validation), not by renaming a clear stdlib call.

Why: a `getCurrentTime()` wrapper around `Date.now()` adds indirection with no payoff.

## Helper-extraction must raise 2 bars: readability AND cognitive load

A helper for 2–4 callsites earns its place only when extraction **strictly raises both** bars. Both must rise — not one.

1. **Readability bar** — does the helper's name communicate intent better than the inline form?
   - If the inline pattern is already self-evident (a 3-line `JSON.parse(decodeURIComponent(raw))`), a helper named `extractTrpcInputField` adds indirection without revelation.
2. **Cognitive load bar** — does extraction shrink the working set the reader has to hold?
   - A 10-line helper hiding a 2-line pattern doesn't reduce load; it spreads the same load across two files (the call site + the helper body), and now the reader chases both.

If either bar fails, **inline wins**. DRY is not a value on its own — it's a heuristic for reducing complexity.

When extraction adds complexity, DRY is the wrong heuristic for that case.

Symmetric to "Don't wrap trivial expressions" (wrappers must add behavior) — this rule covers wrappers that hide patterns without adding behavior, and asserts they're noise unless they clear both bars.

## Decompose dense, complex expressions

Break unfamiliar APIs, nested callbacks into named intermediate variables.

Why: dense expressions optimize for character count — readability beats brevity.

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

When a render function or JSX block exceeds ~50 lines with multiple conditional branches, extract each branch into a self-naming sub-component (inline same-file is fine when the sub-component isn't reused elsewhere).

Why: flat conditional JSX with anonymous `<div>` blocks forces every reader to parse every branch's content to understand the page outline.

Named sub-components make the top-level scannable as an outline — `{isOverCap && <OverCapBanner />}` reads its intent in one glance; the 7-line div behind it doesn't.

Target shape: every conditional block in the parent becomes a one-line `<Foo prop={...} />`. The parent JSX reads as the page's outline.

data-testids and behavior are preserved by definition — you're only moving JSX, not changing it.

Applies to any framework's render tree (React JSX, Vue templates, Svelte markup, JSX-like DSLs) — the principle is "render functions are outlines, not encyclopedias".

## Abstract counter-intuitive APIs

Wrap with intuitive interfaces.

Why: every call site of a counter-intuitive API is a future bug site.

## Context object for cross-cutting concerns

Pass a single context (request ID, user, trace) instead of adding params everywhere.

Why: cross-cutting concerns grow new params across every layer without a context — a hidden propagation tax.

## Parallelize CPU-bound work

Workers for CPU, async for I/O.

Why: async on CPU-bound tasks blocks the event loop — concurrency in name only.

## Don't optimize without evidence

Simplest correct version first. Memoization/caching needs profiling proof OR a clear Big-O reason.

Why: premature optimization adds complexity without evidence — profile first.

## Resilient batch operations

Idempotent, resumable, crash-resilient. Best-effort report on fatal failure.

Why: long batches eventually crash mid-flight; without resumability, you re-run the whole thing and risk duplicates.

## Prefer composition over inheritance

Small, focused pieces over deep class hierarchies.

Why: inheritance couples to the parent's implementation, not just its contract; composition couples to interfaces only.

## Fail loudly, not silently

Errors propagate or get logged explicitly.

Why: a crash you see beats a silent corruption you don't — silent failures hide until the data is wrong downstream.
