# address-verdicts design rationale

Evidence and long-form reasoning behind rules that `SKILL.md` states in one line. None of it adds a constraint; open it only to judge whether a rule still holds.

## Why one TaskList entry per lens

No finding is lost to the grouping: each entry names its own count, and §5 still annotates every finding individually in its verdict file.

That file, not the TaskList, is the durable per-finding ledger.

## Why the dispatch cap is ~10 findings

The `refactor` agent is the concrete case: its p90 is 85 assistant turns, so 30-50 findings can exhaust it mid-run with nothing committed.

## Why the refactor lens keeps its own agent

For code findings, the refactor lens keeps its own agent because it refuses any behavior change by design.

A correctness fix needs `tdd-coder`'s test-first discipline, and a "simplification" that quietly changes semantics is exactly what the refusal catches.

## Why a prose-covering test-sdd finding is never written

The human approved the plan, but CLAUDE.md forbids a test over prose, and the forbidden-to-exist test wins.

This skill is the one place that overrules `/quality-gate` §5.1's "every test-sdd finding applies unconditionally".

## Why batches are sized and commits stay per finding

A batch that outruns its subagent's turn budget leaves the work half-applied with no record of where it stopped.

A lens-sized commit would bury which fix answers which finding, so the diff a human reviews stays one commit per finding.

## Why skipping beats guessing

The caller can re-run a skipped finding by hand, whereas a wrong guess lands a commit nobody asked for.

## Why newest-by-modification-time and a mandatory recap

The branch segment in `verdict_<lens>_<branch>_YYYY-MM-DD_HH:MM.md` means filenames no longer sort lexically into chronological order.

A bare finding id in the closing report forces the human to open the verdict file to know what was decided, even when it is already annotated there.

## Why two marks per finding

The heading `[Done]` prefix and the body `APPLIED`/`SKIPPED` line do different jobs.

- The heading marker is machine-checkable, so a re-run skips what landed and `grep` counts it, but it cannot say why a finding was skipped.
- The body line carries the outcome and evidence, but it is not greppable.

Together they form the durable, on-disk ledger of fixed versus deferred.

## Why annotate lens by lens

Annotating as each lens returns means a session killed mid-run still leaves an accurate ledger for the finished lenses.

Holding every annotation to the end would lose all of them on an interrupted run.
