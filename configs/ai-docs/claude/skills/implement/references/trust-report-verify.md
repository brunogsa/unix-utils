---
words-budget: 1024
---
# Trust-report verify path (§5.1, toggle off)

Detail for /implement's §5.1 when §1.2's verify toggle answered no (`verify_gate.wanted: false`). Load once, the first time this run hits a `done` report.

## Why this exists

The delegated `general-purpose` verify dispatch (§5.1's default path) exists to catch a task subagent fooling itself — a self-graded `done` that doesn't hold up under a fresh, session-bias-free read.
Some runs already have that coverage from elsewhere (a human running their own second-opinion pass over each result, or accepting that only the batch-end quality-gate tail (§8.2) will catch it).
For those runs the per-task dispatch is pure redundancy: it slows every task down for a check nobody reads.

## What still runs

**The cheap checklist-exists check is unaffected — it always runs, toggle or not.**
It costs one file-existence check, not a subagent dispatch, so there's nothing to opt out of.
A missing checklist file is still a straight `fail`, recorded and routed to §5.2 exactly as it would be with the toggle on.

## What's skipped

The `agent(subAgent=general-purpose, title=Verify task <N>...)` dispatch itself — no fresh-context reviewer reads the checklist, the report, or the plan slice.
Nothing re-checks that the checklist is fully checked off, that the evidence stands on its own, or that report and evidence agree.

## What replaces it

When the checklist file exists, trust the task subagent's own §4.4 report directly:

- **`done`** → record the attempt with `result: "pass"`, `signature: "n/a"` (same fields §5.4 already writes on a verified pass) — then go straight to §5.4.
  - No fresh-eyes verdict backs this "pass"; it is the subagent's self-report, taken at face value.

- **`blocked`** → unchanged — routes to §5.2 exactly as it would with the toggle on, since a self-reported block was never something §5.1's verify judged anyway.

## What this costs

A `done` report that would have failed the delegated verify (self-contradictory checklist, evidence that doesn't hold up, a mismatch between report and evidence) now advances unexamined.
That risk is exactly what the toggle trades away for speed — accepted explicitly by whoever answered §1.2's question no, not inferred by this run.
