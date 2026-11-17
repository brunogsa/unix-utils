# Final report contents

What `SKILL.md` §7 closes the run with, read at §7 so the list loads fresh after any compaction. Compose it from the ledger `/address-verdicts` returned, not from a second reading of the verdict files.

## Timing, files and measured results

- Every verdict file path this run produced: the merged file, the rendered metrics verdict and judge file (now in `<RUN_DIR>`), the source paths §4.1 moved, and the fallback when it happened.
  - Also any leg that failed to produce a file, and the `test-sdd` leg when §2 resolved no plan.

- **A failed metrics leg reads `metrics: FAIL - leg failed (<reason>)`, never as clean.**

- Any deferred tooling ask, with its reading: `pessimistic, tooling deferred` or `not measured: no language entry`, each reported as a failing score, never a neutral one.

- Metrics apply outcomes: each open violation fixed with its SHA, and each still open, including rejected exceptions.

## Findings

- **Every finding below carries its `quality-gate#N [<lens>] (<file>:<lines>)` reference (`<lens>#N (...)` on the fallback) plus a one-line recap - never a bare id, count, or SHA alone.**

- Applied findings, with commit SHA.

- Findings the judge ruled Skip, with their `**Standards check**` line - they stay open in the merged file.

- **On a report-only run, every `refactor`, `auto-review`, `metrics` and `scout` finding, under a heading naming them as never judged.**
  - Close it with both ways to work them: tag headings `[AI!]` and run `/address-verdicts`, or re-run as `/quality-gate --auto-solve`.

- `judge: FAIL (<reason>)` or `judge: not run (merge fell back)` when that happened; on a failure, say to fix the judge and re-run `/quality-gate`.

- Every `[QUESTION]` finding, under "needs your answer".

- `fix review: disabled` while §6.1's notice stands; once deleted, the fix-review findings, "reported, never applied", or "fix review: clean", and on a failed check `fix review: FAIL (<reason>)`.

- The `test-sdd` `Unplanned tests added by the branch` finding, its tests listed, never dispatched, for the human to mark `[Done]`.

- Findings `/address-verdicts` skipped, with the reason, and findings whose apply failed, with what it needs to retry.

- The statement that unannotated findings are untouched; tagging them `[AI!]` works them via a later `/address-verdicts` run.

## Scout leg

Read the scout facts from `<RUN_DIR>/scout-classification.md`, and report one of:

- `scout leg: not run (no open scout)`.

- The in-goal task ids deleted.

- The in-goal ids kept because no finding for them reached the merged file.

- The off-goal ids left in the TaskList for the human, ids only, with no finding text.
