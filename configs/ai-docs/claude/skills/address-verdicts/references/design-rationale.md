# address-verdicts design rationale

Reasoning behind rules `SKILL.md` states in one line. It adds no constraint; open it only to judge whether a rule still holds.

## Why the dispatch cap is ~10 findings

The `refactor` agent's p90 is 85 assistant turns, so 30-50 findings can exhaust it mid-run with nothing committed.

## Why the refactor lens keeps its own agent

For code findings, it refuses any behavior change by design.

A correctness fix needs `tdd-coder`'s test-first discipline; the refusal catches a "simplification" that quietly changes semantics.

## Why a prose-covering test-sdd finding is never written

The human approved the plan, but CLAUDE.md forbids a test over prose, and that ban wins.

## Why batches are sized and commits stay per finding

A batch that outruns its subagent's turn budget leaves work half-applied with no record of where it stopped.

A lens-sized commit would bury which fix answers which finding, so a human reviews one commit per finding.

## Why skipping beats guessing

A skip is final until the human deletes its line, whereas a wrong guess lands a commit nobody asked for.

## Why newest-by-modification-time and a mandatory recap

The branch segment in `verdict_<lens>_<branch>_YYYY-MM-DD_HH:MM.md` stops filenames sorting chronologically.

A bare finding id in the closing report forces the human to open the verdict file to learn what was decided.

## Why two marks per finding

The heading `[Done]` prefix and the body `APPLIED`/`SKIPPED` line do different jobs.

- The heading marker is machine-checkable, so a re-run skips what landed and `grep` counts it, but it cannot say why a finding was skipped.
- The body line carries the outcome and evidence, and `^SKIPPED \(` greps it, holding a skip out of every later run.

Together they are the on-disk ledger of fixed versus deferred.

## Why annotate lens by lens

A session killed mid-run still leaves an accurate ledger for the finished lenses.

## Why marked mode selects only `[AI!]` findings, with no fallback

Marked mode commits, pushes, and merges across a whole stack, so each finding it touches must be one the human read and chose.

An `all` fallback would push unread findings to every PR in the stack.

## Why a skipped finding keeps its `[AI!]` but is not retried

The mark records the human's choice, and the `SKIPPED` line records that the choice could not be honored.

Deleting the `SKIPPED` line reopens the finding, since only the human knows whether the skip reason still holds.

## Why an `[AI!: <message>]` note wins over the finding's own fix

The reviewer wrote the finding without the human's context, and the note is the human's answer after reading it.

The note stays in the body after `[Done]` replaces the tag, so the ledger shows why the fix differs from what the finding suggested.

## Why marked mode reads only `verdict_quality-gate_*` files

Each quality-gate file is one branch's merged review, and a standalone lens file can be an older generation of findings a merged file already carries.

## Why a stop covers a subtree

Siblings share only the clean parent; descendants would lack its fixes.

## Why the tree includes ancestors

A stopped run leaves pushed fixes, now `[Done]`, on the branches below the stop.

A re-run starting at the lowest still-marked branch would never merge them forward, and would report clean.

## Why the CI watch keys on the pushed SHA

A PR's check list lags a push, so a watch started right away can read the previous commit's green checks as a pass.

`gh run list --commit <sha>` names only runs for the pushed commit, so no earlier run can stand in.

## Why merge forward, never rebase

A rebase rewrites every upper branch, so each push becomes a force-push and review threads lose their anchors.

A merge commit keeps pushed history intact and needs no force.

## Why CI is watched only on PRs its gate triggers on

A workflow scoped to `pull_request: branches: [main]` never runs the full gate on a PR into another stack branch.

Watching it would wait on the few unrelated checks that run, and read their pass as the gate's.

## Why one TaskList entry per branch and lens in marked mode

The one-entry-per-lens rule assumes one branch; a stack applies each lens once per branch, at a different point in the timeline, so per-branch entries keep the TaskList in working order.

## Why the learn step runs before the first apply, over every file at once

Applying a finding swaps its `[AI!]` for `[Done]`, and `/improve-from-user` skips `[Done]` as a prior run's output, so applied picks no longer read as picks.

One run over the whole stack lets `/improve-from-user` count a kind of finding picked on 3 branches as 3 pieces of evidence, where 8 separate runs would each see 1.

Known gap: the learn launch skips a re-run only when some verdict file has a `[Done]` heading, so a first run that applied nothing gets its marks mined twice.

## Why every question is asked before the first checkout

A question asked mid-chain blocks a run that has already pushed the branches below; asking all up front costs one round-trip, then the chain runs unattended.

## Why any failure stops the whole chain

An upper branch that merges a red lower branch inherits the failure, and every later push publishes it to another PR.

Stopping on the failing branch leaves one place to fix, with nothing above it touched.

## Why a blank line precedes outcomes

The prose checker reads an unseparated line as a hard-wrapped continuation.

## Why the full test run happens once, at the end of §6

Coders verify only the test files their batch touched, so no earlier step runs the whole suite, and a run skipping it could report green while a fix broke a test elsewhere.

One run after the last lens costs one run instead of one per dispatch.

Marked mode already validates each branch and watches CI, so it needs no second run.

A red result is reported, not fixed: a fix here would land after the annotations, outside any finding.
