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

## Why marked mode selects only `[AI!]` findings, with no fallback

Marked mode commits, pushes, and merges across a whole stack, so each finding it touches must be one the human read and chose.

A fallback to `all` on an unmarked run would push findings nobody read to every PR in the stack.

The `[AI!]` tag sits in the `[Done]` slot, so applying a finding swaps one tag for the other and a heading never carries both.

## Why a skipped marked finding keeps its `[AI!]`

The mark records the human's choice, and a skip does not change that choice, so the next marked run retries it.

Deleting the tag is the human's way to drop it, since only they know whether the skip reason is permanent.

## Why an `[AI!: <message>]` note wins over the finding's own fix

The reviewer wrote the finding without the human's context, and the note is the human's answer after reading it.

The note stays in the body after `[Done]` replaces the tag, so the ledger shows why the fix differs from what the finding suggested.

## Why marked mode reads only `verdict_quality-gate_*` files

The human chose this scope: each quality-gate file is one branch's merged review, and a standalone lens file can be an older generation of findings a merged file already carries.

The filename replaces `/` with `-`, so the branch is read from the header, never from the filename.

## Why the chain covers the whole stack, not just from the lowest marked branch

A stopped run leaves pushed fixes on the branches below the stop, and their findings are now `[Done]`.

A re-run starting at the lowest still-marked branch would never merge those fixes forward, and would report clean.

## Why the CI watch keys on the pushed SHA

A PR's check list updates some seconds after a push, so a watch started right away can read the previous commit's green checks as a pass.

`gh run list --commit <sha>` names only runs for the pushed commit, so no earlier run can stand in for it.

## Why merge forward, never rebase

A rebase rewrites every upper branch, so each push becomes a force-push and review threads lose their anchors.

A merge commit keeps the pushed history intact and needs no force.

## Why CI is watched only on PRs its gate triggers on

A workflow scoped to `pull_request: branches: [main]` never runs the full gate on a PR into another stack branch.

Watching that PR would wait on the few unrelated checks that do run, and read their pass as the gate's.

## Why one TaskList entry per branch and lens in marked mode

The one-entry-per-lens rule assumes one branch; a stack applies each lens once per branch, at a different point in the timeline.

One entry per branch and lens keeps the TaskList in the order the run actually works.

## Why the learn step runs before the first apply, over every file at once

Applying a finding swaps its `[AI!]` for `[Done]`, and `/improve-from-user` skips `[Done]` as a prior run's output. So after the run, the applied picks no longer read as picks.

One run over the whole stack lets `/improve-from-user` count a kind of finding picked on 3 branches as 3 pieces of evidence, where 8 separate runs would each see 1.

On a re-run the question recommends skipping, since a still-`[AI!]` finding the first run skipped would be mined again. `/improve-from-user` would then read that repeat as the human raising it again and propose to strengthen a rule nobody re-asked for.

## Why every question is asked before the first checkout

A clarifying question asked mid-chain blocks a run that has already pushed the branches below.

Asking all of them up front costs one round-trip, and the chain then runs unattended.

## Why any failure stops the whole chain

An upper branch that merges a red lower branch inherits the failure, and every push after it publishes the failure to another PR.

Stopping on the failing branch leaves the human one place to fix, with nothing above it touched.
