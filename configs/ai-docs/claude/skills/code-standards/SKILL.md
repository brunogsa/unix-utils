---
name: code-standards
description: "Code principles + examples. USE PROACTIVELY on ANY code edit — writing, refactoring, naming, controllers/use cases, error handling, logging, scripts, or reviewing code. Fires even on small tweaks."
user-invocable: false
---

# Code Standards

Principles for any code edit. Each section has a principle + WHY.

Paired code examples for every principle below: @references/examples.md (keyed by the same section header).

## Code top-down, pull helpers on demand

- Start from the controller/worker layer and work downward;
- Don't write a function until something calls it.

Why: helpers shaped by real demand match callers; speculative ones don't.

## Name by purpose, not mechanism

What the caller gets, not how it works.

Why: implementation changes with refactors but the caller's contract shouldn't — a mechanism-named function starts lying after a body rewrite.

## Self-explanatory names — no context-dependent jargon

Names parse for future readers lacking today's spec context. Avoid numbered phases (`Phase-1`), abbreviated prefixes (`sa`/`sap`), platform-colliding acronyms (`SAP` vs ERP).

Why: spec context decays fast (closed tickets, deleted threads, lost-from-memory); self-explanatory names survive it.

Heuristic: a reviewer skimming the diff in 18 months should not need to ask "what is `sa`?" or "what does Phase-2 do here?".

## Locale-neutral naming in shared APIs

Prefer `documentNumber` over `cnpj` in shared internal code. End-user strings use i18n. Locale-specific OK where the locale IS the contract (URL segments, validators).

Why: a `cnpj` field locks shared code to one country's regulations; `documentNumber` survives expansion.

## Name booleans positively

Prefix with `is`/`has`/`should`/`can`. Avoid negating a negative ("not-not-X").

Why: double negatives force the reader to flip the truth value at every read site — a cognitive tax.

## Extract long conditions into named booleans

When a condition spans 3+ clauses, extract it into a named boolean used at the if site.

Why: a multi-clause condition at the call site hides intent; a named boolean documents it.

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

## Layered architecture

Controller (I/O, validation, logging) → Use Case (pure business logic, no I/O).

Why: I/O changes most often (HTTP → queue → CLI); pure use cases survive every swap.

- Avoid duplicate `info` logs across layers — controller is the natural owner.
- Helpers stay quiet (`debug` for diagnostics, or `info` only when owning a concern the controller can't see).

## Builders assemble, use cases decide

Builder/factory functions should only assemble data from explicit parameters. Business decisions (conditionals, calculations, transformations) belong at the use-case/caller level.

Why: business decisions buried inside builders hide the actual rules; pulling them out keeps business logic visible and builders reusable.

## Log progress in I/O loops

Counter format: `[3/70] item-name`.

Why: silent loops feel hung; the counter answers "progressing?" and "stuck where?" at once.

## Use structured logging

Level, timestamp, transactionId, message, context.

Why: structured logs are queryable; free-text needs grep + human pattern matching.

## Log full diagnostic context on failures

Include the full input that caused the error.

Why: a failure log without input is a hunt; with input, it's a reproduction case.

## Logs must never crash the flow

Every reducer/accessor/template expression must tolerate undefined or empty inputs.

Why: telemetry that crashes the flow removes the very thing meant to help you debug.

## Pair `info` with `debug` carrying full payload

`info` logs counts/IDs/status; matching `debug` log carries full payload (sorted arrays). Toggle `debug` during incident, off after.

Why: `info` runs always (cheap, scannable); `debug` flips on during incidents — config flag beats code change.

Sensitive fields (CPF, CNPJ, email, address, tokens, free-text): flag candidates and ask before shipping; don't silently include or drop.

In prod: `debug` is off by default. During launch / incident, flip the config — no code change, no deploy.

**AI flags risky fields; user decides.** When proposing a `debug` payload that includes identifiers or potentially sensitive data:
- Surface the candidate fields explicitly and ask before shipping.
- Don't silently include them.
- Don't silently drop them either — both rob the user of the decision.

## Never retry indefinitely

Always cap consecutive retries.

Why: uncapped retries during an outage become a self-inflicted DDoS on the upstream.

## Scripts: human-friendly

`--help` and a comment header with usage + examples. Help → stdout + exit 0; bad input → stderr + exit 1.

Why: the next user (often future-you) won't read the source — `--help` is the contract surface.

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

## Distinguish "missing" from "intentional zero/empty"

Check null/undefined, not falsiness.

Why: `if (count)` treats `0` and `undefined` identically — falsiness checks paper over the distinction and ship bugs.

## Don't wrap trivial expressions

Wrappers earn existence by adding behavior (retry, logging, validation), not by renaming a clear stdlib call.

Why: a `getCurrentTime()` wrapper around `Date.now()` adds indirection with no payoff.

## Decompose dense, complex expressions

Break unfamiliar APIs, nested callbacks into named intermediate variables.

Why: dense expressions optimize for character count — readability beats brevity.

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
