# Coverage Taxonomy — corner cases and failure modes

Canonical checklists of the corner-case and failure-mode categories any coverage exercise probes.

Single source of truth: the `brainstorm` interview probes, the `spec-driven-development` spec-template checklists, and test-standards test design all point here.

Edit this file, never their inline recaps — parallel copies drift and ship coverage gaps between what's asked and what's checked.

## Corner cases (data-shape boundaries)

For each input field or collection the change touches:

- empty / single / many / max-size / overflow
- null / undefined / missing
- unicode / whitespace-only / leading-trailing spaces
- duplicate / out-of-order entries
- boundary numbers (0, -1, MAX_INT, off-by-one)
- clock / timezone / DST boundaries (midnight, month-end, leap day)
- combined / composed filters (multiple filters active at once)

## Failure modes (adverse interactions and dependencies)

For each dependency call and state-changing operation:

- validation error (4xx)
- downstream timeout / never-responds
- downstream 5xx
- partial failure (some items succeed, some fail)
- auth / authz failure
- rate limits / throttling (429)
- concurrency / race / double-submit
- idempotency (repeat-request behavior)
- network drop mid-operation
- datastore unavailable / deadlock / constraint violation
- crash mid-transaction (what state does the retry see?)
- stale cache (serving pre-change data after the change lands)
- resource exhaustion (disk / memory / connection pool / queue backpressure)

### Async delivery (event/message consumers)

For each event or message the change consumes or emits:

- duplicate delivery (at-least-once redelivery)
- out-of-order delivery
- redelivery after partial processing (consumer crashed mid-message)
- poison message / dead-letter path

## Classification note

Concurrency and idempotency file under failure modes (adverse interaction with state), not corner cases (data shape) — probe and checklist them there.

Duplicate / out-of-order *entries* (data inside one input list) are a corner case; duplicate / out-of-order *delivery* (the broker re-sends or reorders messages) files under async failure modes.
