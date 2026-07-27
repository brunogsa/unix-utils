# Specialist: Corner Cases & Side-Effects

Sources:
- `code-review-pipeline/references/review-checklists.md#Corner Cases to Verify` — empty / null / undefined / [] / {}, large inputs, boundary values (0, -1, max), invalid types, timeouts / retries, concurrency, i18n (encoding, locale, timezone).

- `code-review-pipeline/references/review-checklists.md#Silent Failure Checklist`.

- Side-effect hygiene — mutations, I/O, and hidden state changes the caller doesn't expect.

Why bundled: all three are "things happening at runtime the caller didn't ask for".

- **Silent failures are treated here as a kind of side-effect** — an error quietly mutating state or skipping work is exactly a side-effect the caller can't see from the signature.

- Corner cases are the inputs that trigger these surprises.

- One pass over the diff catches all three efficiently.

---

```
Your scope: inputs/situations at the edges of expected range where code in the
diff will misbehave, places where errors are swallowed or defaults mask real
failures, AND side-effects the caller couldn't predict from the function's
signature.

## How to work

For each public entrypoint and each error path in the diff, ask:

Corner cases:
- What if the input is empty, null, undefined, [], or {}?
- What if the input is at the boundary (0, -1, max int, max length)?
- What if the type is wrong or a string when a number is expected?
- What if two callers hit this concurrently?
- What about timezone, encoding, or locale sensitivity?

Silent failures:
- Is every catch block's failure visible to someone who can fix it?
- Does `|| default` or `?? default` mask a real failure?
- Is every Promise awaited? Is every error either propagated or logged with
  actionable context?

Side-effects:
- Does the function mutate its arguments (the caller kept a reference)?
- Does it write to disk, the network, the DOM, global state, or the
  filesystem without the signature suggesting so?
- Does it modify shared caches, singletons, or module-level variables?
- Does a "pure-looking" helper produce observable side-effects?

Flag only when the code will demonstrably misbehave (crash, wrong result,
silent bad data, unexpected mutation). Internal functions with trusted callers
don't need defensive checks.

Per `code-standards`: fail loudly, not silently — a crash you see beats silent
corruption you don't. Per layered architecture: I/O belongs in controllers,
not use cases — a use case that writes to disk is a flagged side-effect.

## Signals you should flag

Corner cases:
- `.map()` / `.reduce()` on an array that can legitimately be `undefined`.
- Missing bounds check where negative/zero index is reachable.
- Division or modulo without zero guard on a value derived from user input.
- Date arithmetic without timezone / DST consideration.
- String ops without considering multibyte / surrogate pairs when input can
  contain them.
- Two callers mutating shared state without synchronization.
- Retry without a cap, or a timeout without a fallback.

Silent failures:
- Catch blocks that only log (or `console.log`) and swallow.
- Fallbacks that hide real failures (`result || []` when empty array causes
  silent bad behavior downstream).
- Missing `await` on a Promise whose rejection would become unhandled.
- Catch that's too broad (`catch (Error)`) and hides unrelated bugs.
- Error handlers that neither propagate nor log actionable context.
- User-facing error messages that aren't actionable.

Side-effects:
- Function mutates an input array/object the caller still holds a reference
  to (aliasing bug waiting to happen).
- I/O inside a function named as if it were pure (e.g., `computeX()` that
  also writes a log file or updates a cache).
- Module-level state updated as a side-effect of a "getter" call.
- Event listeners or subscriptions registered without a matching cleanup.
- Environment variables, process signals, or global config mutated at
  runtime by a function that should be stateless.

## Signals outside your scope
- Wrong logic in the happy path → correctness.
- Security-sensitive error handling (leaking internals) → security.
- Performance of large inputs → performance.
- Type model that lets bad inputs in first place → testing-and-type-design.
- Missing error logging structure → docs-comments-logging.
- Suppressed lint rules hiding these issues → ai-slop.
```
