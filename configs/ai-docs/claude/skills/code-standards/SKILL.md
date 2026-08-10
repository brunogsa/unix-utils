---
name: code-standards
description: "USE PROACTIVELY when you write, edit, or review code — any language, including config that is itself code like init.lua, not just settings.json — even one-liners. Not for pure reading."
user-invocable: false
words-budget: 4096
instructions-budget: 80
---

# Code Standards

Principles for any code edit. Each rule is an instruction with its nested why; code-fence examples sit at the margin below.

## Readability & decomposition

### Lower reviewer load: nesting & dense lines

- [Instruction] **CRITICAL: Treat the human reviewer as the bottleneck — favor any tactic that lowers reviewer cognitive load over author keystrokes.**
  - [Why] The AI writes code in seconds; the reviewer takes minutes and pays that tax on every read — optimize the larger cumulative cost, not the author's one-time write.

- [Instruction] Treat more than 2 nesting levels as a smell, more than 3 as a refactor — reduce it by extracting inner units or early returns.
  - [Why] Each nesting level multiplies the mental state the reader holds — bugs hide where "I don't understand" lives.

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

- [Instruction] Break multi-clause one-liners across 2-3 short lines.
  - [Why] Spreading the logic moves work from the reader's mental stack into discrete, scannable steps.

- [Instruction] Break unfamiliar APIs, nested callbacks into named intermediate variables.
  - [Why] A dense expression forces the reader to unpack it mentally before they can judge it; named intermediates do that unpacking once, in the code.

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

### Extraction: helpers, components, wrappers

- [Instruction] When a render tree exceeds ~50 lines with multiple conditional branches, extract each branch into a self-naming sub-component (inline same-file is fine; any framework's templates).
  - [Why] Flat conditional markup with anonymous blocks forces the reader to parse every branch; named sub-components make the top level read as the page's outline.

- [Instruction] When extracting, preserve data-testids and behavior — you're moving the markup, not changing it.
  - [Why] An extraction that alters behavior or testids is a refactor disguised as a move — it breaks tests and erodes review trust.

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

- [Instruction] Extract a helper for 2–4 callsites only when extraction raises BOTH the readability and cognitive-load bars.
  - [Why] One bar alone doesn't justify the indirection; both must rise or inline wins — DRY reduces complexity, it isn't a value in itself.

- [Instruction] Readability bar: the helper's name must communicate intent better than the inline form.
  - [Why] If the inline pattern is already self-evident, a helper name adds indirection without revelation.

- [Instruction] Cognitive-load bar: extraction must shrink the working set the reader holds.
  - [Why] A 10-line helper hiding a 2-line pattern spreads the same load across two files the reader must chase.

- [Instruction] A wrapper must earn its keep — by adding behavior (retry, logging, validation) or by giving a counter-intuitive API an intuitive interface; never by renaming a clear stdlib call.
  - [Why] Each call site of a counter-intuitive API is a future bug site, so taming it pays off; a `getCurrentTime()` wrapper over `Date.now()` only adds indirection.

## Naming

### Name by purpose, clearly

- [Instruction] **CRITICAL: Name functions and variables by what the caller gets, not how it works.**
  - [Why] Implementation changes with refactors but the caller's contract shouldn't — a mechanism-named function starts lying after a body rewrite.

- [Example]
```javascript
// Bad -- describes the mechanism (what it does internally):
function collectAllColumns(rows) { /* ... */ }
function getValues(rows) { /* ... */ }

// Good -- describes the purpose/output (what the caller gets):
function buildCsvColumnOrder(rows) { /* ... */ }
function extractUniqueEmails(rows) { /* ... */ }
```

- [Instruction] Rename when a name implies the wrong concept, even when it computes the right value.
  - [Why] A reader trusts what the name says, not what it computes; a misleading name sends them down the wrong path even though the value is correct.

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

- [Instruction] In identifiers, avoid numbered phases (`Phase-1`), abbreviated prefixes (`sa`/`sap`), and platform-colliding acronyms (`SAP` vs ERP).
  - [Why] A reviewer skimming the diff in 18 months shouldn't have to recover spec context to decode `sa` or `Phase-2`.

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

- [Instruction] Use locale-neutral names in shared code (`documentNumber` over `cnpj`) — reserve locale-specific forms for where the locale IS the contract (URL segments, validators, i18n'd end-user strings).
  - [Why] A `cnpj` field locks shared code to one country's regulations; `documentNumber` survives expansion to others.

- [Instruction] Don't mix languages in code identifiers — keep names in one language (default English), unless a country-specific term (`cnpj`, `notaFiscal`) turns obscure when translated.
  - [Why] A half-native-half-English name (`endereco` beside `agreementId`) reads awkwardly and splits the codebase's vocabulary, forcing every reader to code-switch mid-line.

### Booleans, conditions & naming conventions

- [Instruction] Prefix booleans with `is`/`has`/`should`/`can`.
  - [Why] An affirmative prefix signals the value is a boolean and which way true points.

- [Instruction] Avoid negating a negative (`!isNotReady`) — name the positive condition.
  - [Why] Double negatives force the reader to flip the truth value at every read site — a cognitive tax.

- [Example]
```ts
// Bad -- negation of a negative:
if (!item.isShrinked) { ... }

// Good -- name the positive condition:
const isExpandable = !item.isShrinked;
if (isExpandable) { ... }
```

- [Instruction] **CRITICAL: When a condition spans 3+ clauses, extract it into a named boolean used at the if site.**
  - [Why] A multi-clause condition at the call site hides intent; a named boolean documents it.

- [Example]
```ts
const isExpandableKit = item.type === KIT && !item.isShrinked && item.children.length < 1;
if (isExpandableKit) { ... }
```

- [Instruction] Encode a collection's type in its name — plural for arrays, a `Set`/`Map` suffix for those.
  - [Why] The convention is a free type system; drop it and the reader looks up the type at every use.

## Architecture & layering

### Layering & responsibilities

- [Instruction] **CRITICAL: Code top-down — start at the controller/worker layer and pull a helper only once a caller needs it.**
  - [Why] Helpers shaped by real demand match their callers; speculative ones built ahead of a caller don't.

- [Instruction] **CRITICAL: One thing at one level of abstraction.**
  - [Why] A function that does two jobs has two reasons to change — that's the single-responsibility principle (SRP) — and editing it for one job risks breaking the other.

- [Instruction] **Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).**
  - [Why] I/O changes most often (HTTP → queue → CLI); pure use cases survive every swap.

- [Instruction] Make the controller the logging owner — avoid duplicate `info` across layers; helpers stay quiet (`debug` only, or `info` solely for what the controller can't see).
  - [Why] One owner per log line keeps the output deduplicated and tells the reader which layer to trust for each fact.

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

- [Instruction] Builder/factory functions should only assemble data from explicit parameters. Business decisions (conditionals, calculations, transformations) belong at the use-case/caller level.
  - [Why] Business decisions buried inside builders hide the actual rules; pulling them out keeps business logic visible and builders reusable.

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

- [Instruction] When a spec defines N cases, design a unified pipeline that naturally produces correct output for all of them.
  - [Why] A 1:1 if/else translation couples control flow to the spec — every requirement change demands a code change, and every extra branch is another place for a bug to hide.

### Design & performance choices

- [Instruction] Prefer composition — small, focused pieces — over inheritance and deep class hierarchies.
  - [Why] Inheritance couples to the parent's implementation, not just its contract; composition couples to interfaces only.

- [Instruction] **Information hiding** -- expose intent, hide implementation across code APIs, CLI interfaces, doc structures, and test helpers; clients depend only on the contract.
  - [Why] Hiding internals lets you change them later without breaking downstream callers; exposing internals creates coupling you'll have to keep forever.

- [Instruction] **Keep backward compatibility unless told otherwise** -- changing shared code, APIs, schemas, or configs must not break existing callers without explicit approval.
  - [Why] Shared code's blast radius is every consumer; a silent breaking change ships failures you can't see from the diff.

- [Instruction] Drive optional behavior with an explicit flag the consumer sets, not a heuristic that infers intent from incidental state.
  - [Why] An inferred trigger couples behavior to a coincidence of the data, so it fires in cases the consumer never meant and the caller loses the choice.

- [Example] Bad: `hasReadableDetail: detail !== undefined` — inferred from whether a field happened to parse. Good: a `shouldPrintResponse` flag the caller sets deliberately.

- [Instruction] Pass a single `ctx` object for cross-cutting values (request ID, user, trace) that logging and tracing need but business logic doesn't — not a new param at every layer.
  - [Why] Cross-cutting concerns grow new params across every layer without a context — a hidden propagation tax.

- [Instruction] Parallelize CPU-bound work with worker threads; use async only for I/O.
  - [Why] Async on CPU-bound tasks blocks the event loop — concurrency in name only.

- [Instruction] Simplest correct version first. Memoization/caching needs profiling proof OR a clear Big-O reason.
  - [Why] An optimization you can't tie to a profile or a Big-O argument adds complexity that may not even sit on the hot path — cost with no measured benefit.

## Functions, purity & side effects

- [Instruction] Avoid global mutable state — pass data through params and return values.
  - [Why] Module-scope state makes data flow invisible and breaks unit isolation.

- [Instruction] Keep functions pure by default — isolate I/O into thin boundary functions.
  - [Why] Pure functions test without mocks; I/O is the part that needs infrastructure — keep it at the edges.

- [Instruction] **Name a helper for what it returns, not its operation — a `get`-noun signals a new immutable; a verb like `append` signals mutation.**
  - [Why] The name is the caller's only clue whether the result is fresh or changed in place; `getX` reads as the value returned, `appendX` reads as a command that hides it.

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

- [Instruction] Inject what's hard to mock — pass I/O collaborators as parameters.
  - [Why] Passing the collaborator as a param lets a test swap in a fake; an imported singleton binds at module load and can't be substituted.

- [Instruction] **Use named-param objects for any function with 2+ params.**
  - [Why] Positional args lose meaning at call sites (`configure(3, 5000)` — what's 3?).

- [Instruction] **In the signature, list the specific fields the function needs rather than passing whole config objects.**
  - [Why] Fat-object params hide internal coupling — the signature stops documenting what the function actually depends on.

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

## Logging & observability

- [Instruction] Log progress in I/O loops with a counter: `[3/70] item-name`.
  - [Why] Silent loops feel hung; the counter answers "progressing?" and "stuck where?" at once.

- [Instruction] Use structured logging with level, timestamp, transactionId, message, context.
  - [Why] Structured logs are queryable; free-text needs grep + human pattern matching.

- [Example]
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

- [Instruction] On failure, log the full input that caused the error.
  - [Why] A failure log without input is a hunt; with input, it's a reproduction case.

- [Instruction] Logs must never crash the flow — every reducer/accessor/template expression must tolerate undefined or empty inputs.
  - [Why] Telemetry that crashes the flow removes the very thing meant to help you debug.

- [Example]
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

- [Instruction] Pair each `info` log (counts/IDs/status) with a `debug` log carrying the full payload (sorted arrays).
  - [Why] `info` stays cheap and scannable always-on; the heavy `debug` detail rides alongside for when you need it.

- [Example]
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

- [Instruction] When a log payload may carry sensitive data (CPF, CNPJ, email, address, tokens, free-text), surface the candidate fields and ask before shipping — never silently include or drop them.
  - [Why] Silent-include leaks PII; silent-drop robs the user of the decision. Both replace an explicit per-field choice with a default the user never made.

## Error handling & resilience

- [Instruction] Always validate input at trust boundaries (user input, external APIs, queue payloads); trust internals.
  - [Why] Validating every internal call is wasted effort; only the trust boundary takes untrusted data, so that's the one place validation actually catches anything.

- [Instruction] **CRITICAL: Fail loudly, not silently — errors propagate or get logged explicitly; when an internal invariant breaks, fail fast and never coerce, swallow, or default it away.**
  - [Why] A crash stops the program where the bug is; a swallowed error lets it run on and corrupt data downstream, with no trail back to the break.

- [Instruction] Never retry indefinitely — always cap consecutive retries.
  - [Why] Uncapped retries during an outage become a self-inflicted DDoS on the upstream.

- [Instruction] Make batch operations idempotent and resumable, so a crash mid-flight can safely re-run from where it stopped.
  - [Why] Long batches eventually crash; without idempotent resumability you re-run the whole thing and risk duplicates.

- [Instruction] On fatal failure, emit a best-effort report of what completed before aborting.
  - [Why] A partial-progress report turns a crashed batch into a known state instead of a guess about what landed.

## Data handling

- [Instruction] **Normalize data at the entry point — convert string dates and numbers-as-strings to proper types right after validation.**
  - [Why] Defer normalization and you scatter `parseInt`/`new Date` across the codebase.

- [Instruction] **CRITICAL: Use an enum for a fixed set of related magic values; a named constant for a standalone one.**
  - [Why] A `10` or `"KIT"` scattered across files is a coordination problem when it changes — a named constant is grep-able and changes once.

- [Example]
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

- [Instruction] Distinguish missing from intentional zero/empty — check null/undefined, not falsiness.
  - [Why] `if (count)` treats `0` and `undefined` identically — falsiness checks paper over the distinction and ship bugs.

- [Instruction] Never narrow a runtime-derived value to a stricter enum with a blind `as` or `as unknown as` cast.
  - [Why] A blind cast lies to the type system about unchecked data.

- [Instruction] Validate runtime-derived enum membership at the boundary and throw a domain error on mismatch.
  - [Why] Validation catches out-of-range values loudly at the boundary instead of failing silently downstream as wrongly-typed enums.

- [Example]
```ts
function assertSgeSiglaNivel(value: string): asserts value is SgeSiglaNivel {
  if (!Object.values(SgeSiglaNivel).includes(value as SgeSiglaNivel)) {
    throw new SgeInvalidSiglaNivelError(value);
  }
}
```

## Scripts

### Scripts: human-friendly

- [Instruction] Give every script a `--help` and a comment header with usage + examples.
  - [Why] The next user (often future-you) won't read the source — `--help` is the contract surface.

- [Instruction] Route help to stdout with exit 0, bad input to stderr with exit 1.
  - [Why] Conventional streams and exit codes let callers and pipes tell success from misuse without parsing output.

- [Instruction] Keep the header to exactly four things — the script's name, its one-line purpose, its invocation forms, and its stdin/stdout/exit-code I/O contract.
  - [Why] Rationale, background, and worked examples belong in the owning skill's `SKILL.md`; a header padded with them stops being brief and simple to scan.

- [Example]
```python
#!/usr/bin/env python3
# extract-field.py - Extract a field from JSON lines
#
# Usage:
#   extract-field.py <field> [file]
#   cat data.jsonl | extract-field.py .name
#
# stdin: JSON lines, when no file argument is given
# stdout: the extracted field value, one per line
# exit: 0 on success, 1 on bad input
```

### Scripts: language, conversion & naming

- [Instruction] Default every script's target language to Python; pick `.js` only when its header carries a `# Requires-npm: <package> — <stdlib gap>` line naming an npm package Python's stdlib cannot substitute.
  - [Why] Python's stdlib already covers process glue, JSON, and file work, so an unstated npm reach forks the toolchain for no real gain; the header names the one genuine exception.

- [Instruction] Convert a `.sh` script to its target language when it embeds `awk`, `jq`, `sed -E`, or a here-doc, or when it exceeds 128 lines with none of those four.
  - [Why] Either signal marks a script a junior developer can no longer read end-to-end — the same bar measured 54 of 82 real scripts across this repo needing conversion.

- [Instruction] Exempt a hook that fires on every tool call from that verdict — it stays `.sh` regardless; exclude `install.sh` from the bar entirely.
  - [Why] A per-tool-call hook pays a fresh interpreter cold start on every turn, and `install.sh` bootstraps the interpreters a conversion would make it depend on.

- [Instruction] Name every script `<verb>-<object>[-<qualifier>]` in kebab-case, sourcing the verb list, category denylist, and abbreviation allowlist from `scripts/naming-rule-lexicon.json` — never restate them here.
  - [Why] A lexicon file keeps the verb list, denylist, and allowlist a single edit instead of a prose rewrite scattered across every rule change.

- [Instruction] **CRITICAL: Follow the Unix philosophy — make each script do one thing well and compose via stdin/stdout pipes.**
  - [Why] A small, pipeable tool composes into pipelines; a monolithic script becomes a private API nobody reuses.

- [Instruction] Accept behavior as parameters rather than hardcoding it.
  - [Why] Parameterized behavior lets the next caller reuse the script unchanged; hardcoded choices force a fork.

### Scripts: tests

- [Instruction] Test every `.py` script with `pytest` and every `.js` script with `node:test`, in a `<stem>.test.<ext>` file inside a `tests/` directory beside the script.
  - [Why] A shared runner and one filename convention retire the hand-rolled bash test harnesses this repo used to write per script, one framework instead of many.
