---
name: test-standards
description: "Test principles + examples. USE PROACTIVELY on ANY test work — writing, reading, choosing test type (unit/integration/e2e), mocking, flakes, coverage gaps, regression tests, test titles, or reviewing tests."
user-invocable: false
---

# Test Standards

Principles for any test work. Each section pairs a principle with its WHY.

Paired code examples for every principle below: @references/examples.md (keyed by the same section header).

## Default to integration tests for behavior coverage

Black-box by nature. Mock at external/IO boundaries (DB, HTTP, queues, file system).

Why: integration tests survive internal refactors and exercise the path the caller actually takes. Unit tests pinned to implementation details break every time the implementation moves, even when behavior is identical.

- Prefer fakes and localstack-style emulators to bare mocks where the cost is reasonable.
- Add **unit tests** for leaf functions/modules — pure logic with no/few dependencies (parsers, normalizers, validators, formatters). Whitebox; expect tests to change when the implementation changes.
- Skip unit tests when the only "unit" is a thin glue function.
- **E2E tests sparingly** — slow and brittle; flakiness erodes trust in the suite. Acceptable when the specific case is cheap (existing fixture, single happy-path Playwright run, smoke test).
- **Manual tests** when automation cost is disproportionate (rare UI flows, third-party integrations without sandbox). Log per `test-driven-development` format.

## Gold rule: automate what a human would manually do to verify

Before writing tests, ask: "if I had to verify this change by hand, what steps would I take?" — then automate that list.

Applies to backend (API calls, payloads, DB states) and frontend (clicks, inputs, page states) equally — the human verification checklist is the same shape regardless of layer.

Why: coverage tools answer "is this line touched?" — they cannot answer "would a manual tester have noticed this?". The manual-verification checklist is the test checklist.

Concrete patterns this rule generates:

- **Cover every input variant** — N input fields, filters, query params, or request shapes of the same kind = N tests. Coverage on one says nothing about the others.
- **Boundary on caps/limits** — a cap of N gets an explicit N+1 test (send N+1 of the limited thing and prove the cap engages). Happy-path-only leaves the invariant unverified.
- **Async safety / idempotency** — disabled-during-fetch (UI), idempotency keys (API), retry-resistant operations — the actions a manual tester would re-fire need explicit tests.
- **Three-branch dependency outcome** — success, error response, AND timeout/never-responds. Missing the timeout branch leaves a real production gap (UI stays loading forever; backend leaks resources).
- **Inverse cache branch** — when set-and-fetch is tested, test clear-and-restore (or invalidate-and-refetch). Partial cache coverage is a known footgun.
- **Observably-non-empty BEFORE and AFTER** — for filter/transition tests (UI or API), baseline and final state must both be non-empty.
  - Empty-to-something only proves the filter renders/returns something — not that it changes meaningfully.

## Test behaviour, not implementation

Black-box integration tests preferred; supplement with focused unit tests.

Why: on refactors, integration tests (behavior) keep working and serve as a guardrail.

Unit tests pinned to implementation must be refactored too — the test stops protecting you the moment you most need it.

## Design test titles before implementation

Write titles (no bodies), review them, then run RED-GREEN.

Why: titles capture the contract before the code locks it in.

Writing tests AFTER you "see what works" shapes the test to whatever you ended up writing — the test stops being a contract.

- Applies upfront to integration tests and pre-known pure helpers, and again at each helper pulled on demand — designing them all upfront forces premature signatures.
- Commit tests together with their implementation — never titles alone.
- For scripts: usage syntax + examples in the comment header.

## Descriptive titles (BDD-like)

Test titles read as the behavior documentation, in domain language.

Why: titles get scanned a hundred times more than test bodies.

**Anti-pattern: spec-tracking refs in test titles**

AC/Req/Task/DBMA/Jira refs belong in commit messages, PR descriptions, or `spec.md` — not in test titles, which describe behavior.

**Anti-pattern: generic noun when multiple instances of the same kind exist**

When a system has multiple instances of the same kind — two search fields, two filters, two query params, two endpoints — name the specific one in the title.

Generic nouns invite confusion.

## Bug fix starts with a failing regression test

See `debug-standards` for the full rule.

## Deterministic & self-contained

No shared state, no randomness, clone inputs when testing mutating functions. Pin the clock with fake timers when the system under test reads it — directly or via helpers.

Why: flaky tests erode trust.

A test that passes 9 times and fails the 10th is worse than no test — engineers learn to rerun instead of investigate, and real failures get ignored.

- Time-derived tests without a frozen clock are time-bombs — they pass today and silently fail in N months when wall-clock crosses a threshold.
- Apply when test names contain "past", "future", "expired", "min", "cap", "deadline" — wall-clock-sensitive vocabulary.

## Mock sparingly

Only external dependencies (file I/O, network, external processes).

Why: every mock is a hypothesis about what the dependency does.

If the hypothesis drifts from reality, the test passes while production breaks. Mock at the system boundary, not in the middle.

## Use real-like mock data

Why: cryptic mock data (`name: "x"`, `email: "a@b"`) hides bugs that show up only with realistic shapes (encoding, length, casing). Real-like data catches real-like bugs.

## Don't re-implement logic under test

Let the system under test do the work.

Why: if the test reproduces the logic, both move together.

A bug in the production logic is mirrored in the test, and the test passes anyway. The test must encode an independent expectation.

## Remove redundant / tautological tests

When a new test exercises the same code path with the same inputs as an existing one, remove the duplicate or merge.

Why: two tests asserting the same thing don't improve safety — they slow the suite, double the maintenance burden, and create false confidence.

Schema example: if "max 10" is enforced, one test at 11 covers it; tests at 12, 15, 100 are redundant. Boundary + 1 is the contract.

## One test per distinct cause

Isolate each independent trigger for a behavior. Different inputs that exercise the same code path are one test, not two.

Why: distinct causes are the unit of safety. If two test cases hit the same production code path, the second adds maintenance with no extra coverage.

## When N triggers share one outcome, test the outcome

When multiple events produce the same outcome — different filters reset the page, different mutations invalidate one cache, different errors roll back one transaction — write ONE test asserting the outcome.

Don't write N tests one-per-trigger when all paths lead to the same final state.

Why: N specific tests grow linearly with each new trigger and silently miss the next one added.

A test of the outcome itself ("any refetch resets page to 1") inherits coverage automatically when new triggers join.

- **vs. "Remove redundant tests"** — that rule fires on identical assertions; this rule fires when triggers differ but outcome doesn't.
- **vs. "One test per distinct cause"** — that rule fires when causes have independent production branches; this rule fires when triggers share one production branch.

## Don't test log presence

Log emission is not behavior the caller observes.

Why: log assertions are brittle (change when the log format evolves), tautological (mirror the impl), and clutter the suite. Test the behavior that produced the log, not the log itself.

**Exception**: when a log is an external contract (audit log consumed by another system, structured event for analytics), test the payload shape — that's contract testing, not log presence testing.

## Cover every variant of a behavior

When a feature has N variants (tabs, entity types, query params, view modes, browser sizes), every variant must be covered — directly or via parametrization.

Why: coverage on variant A says nothing about variant B's behavior. The "one example, infer the rest" heuristic fails the moment behavior diverges across variants.

Heuristic: ask "are the other variants tested?" for every test you write.

## Group tests by intent: happy path, corner cases, failure scenarios

Why: readers scanning "what does this do when it works?" should not wade through error paths. Grouping by intent makes the contract scannable at a glance.

## Avoid order-dependent assertions

Tests should not break when the implementation changes the order of items in a collection, unless order is part of the contract.

Why: asserting on exact array order couples tests to implementation details. A refactor that changes iteration order shouldn't break a behavior test.

## Fixtures must support every state the tests assert on

When a single fixture is reused across tests that assert on different states (idle, loading, error, edge case), the fixture's defaults must allow each test to express its state without monkey-patching internals.

Why: if a test has to mutate the fixture in surprising ways to reach a state, the fixture is too narrow. Extending the factory is the contract; tests stay declarative.

When you add a new test that asserts on a state the fixture didn't anticipate, **extend the factory** rather than constructing one-offs in the test body.

## Parametrized test inputs (OK when readable)

Why: parametrization reduces duplication when N tests differ only by input/expected. Stops being useful when bodies diverge — at that point, separate tests are more readable.

## Inline test helpers until reused

Keep builder/factory helpers in the test file until a second test file needs them. Centralize at 2+ callers, not speculatively.

Why: speculative centralization adds indirection without payoff.

Readers have to navigate to a shared module to understand what a test does. The 2+ caller rule keeps the abstraction grounded in real demand.

## Test body and helpers easier to read

Ensure a human can read it and understand what is happening.

Why: a test you can't read is a test you can't trust during a failure.

The body is documentation of intent — opaque tests get deleted at the first "what does this even test?" moment.

## Re-use constants in assertions

Reference the same enums/constants as production code.

Why: hardcoding the literal value in the test means a refactor that renames the enum silently breaks production while the test still passes (with the old literal). Sharing the constant catches drift.

## Debug with code and tests, not temp files

Why: temp files (scratchpads, throwaway scripts) vanish when the session ends. The next person who hits the same bug has no signal. A failing test or a committed debug script survives.

## Leverage coverage to find untested flows

After tests pass, check coverage if available; uncovered branches reveal corner cases the tests didn't actually exercise.

Why: green tests prove the cases you thought of work. Coverage gaps reveal the cases you didn't think of — corner cases hide there.

- Source order: repo's existing coverage script first; else run coverage directly; else read existing artifacts (lcov, coverage.xml).
- Skip silently if none work.

## Tests follow migrated code

When moving logic to a new location, adapt existing tests to the new path. Don't delete behavior coverage.

Why: deleting tests during a migration is silent regression risk. The behavior they protected is still being shipped — without the test, the next bug in that area has no signal.

## Regression baselines: hand-coded shape, not self-comparison

A test that asserts `f(X) === f(X)` proves only that `f` is deterministic — it can never fail unless the system is non-deterministic.

Why: a genuine regression guard must encode an *expectation* the implementation might miss. Self-comparison guards nothing.

- Regression baselines must be hand-coded values that the implementation could plausibly fail to produce.
- This is distinct from "Don't reproduce logic under test" (which is about the test recomputing what the code does).
- Self-comparison is about the test asserting against its own runtime output.
