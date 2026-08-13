# Stacked-by-task — batch end

Read this at §8.3, on a run where `stack.wanted` is true.

It replaces the single-PR path in [`batch-end-pr.md`](batch-end-pr.md); everything else about §8.3 — when it runs, the halt rule, the `pr-creator` dispatch contract, the body's required content — is unchanged.

[`stacked-by-task.md`](stacked-by-task.md) owns the §1.2 decision that got the run here, and the layer branches this step pushes.

## Push, open the PRs, register the stack

1. **Push every layer branch** in one command, in layer order.

2. **Open one PR per layer, bottom-up**, one `pr-creator` dispatch each, so every parent PR exists before its child targets it.
   - `--base` is the **previous layer's branch**; layer 1's `--base` is whatever `batch-end-pr.md` already resolves for the unit.
   - Body-file path: `./pr_<slug>_t<task-id>.final.md`, so the layers don't overwrite each other.
   - Each body's scope is that task alone — its plan slice and its acceptance criteria, not the unit's.
   - Cross-link the chain in every body (`Stack: #10 ← #11 ← #12 (this PR)`), per [`stacked-prs.md`](stacked-prs.md).
     - A dependent unit's first-layer body also names the unit it depends on, and that this is a separate stack.

3. **Register this unit's chain**: `gh stack link` from the topmost layer, per [`batch-end-pr-native-link.md`](batch-end-pr-native-link.md) —
   - including its rule that a failed link is a downgrade, not a halt. Once per unit at its own batch end, never once per run: each unit is its own stack.

   - Check `gh stack link --help` first.
     - A dependent unit's chain reaches down through its parent's layers, so if the extension registers everything reachable, note it in the package as a platform limit and continue.

## Where the branch gets recorded

Two records, both written here, neither replacing the other:

- **Per layer** — each task's own branch, on that task's heading in the Task Breakdown, beside the `[Done]` marker §6 already writes there:

  ```
  ### 3. [Done] Map PREPARA INTENSIVO in the SGE serie table

  **Branch**: `feat/x/pr1-t3`
  ```

- **Per unit** — the unit's **last** layer's branch, in its PR Breakdown entry, exactly as [`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md) already specifies.
  - `git branch --show-current` at batch end returns it, since HEAD sits on the topmost layer.

  A plain `<task-ids>` run has no PR Breakdown entry to write, so it records the per-layer half alone.

  Recording the last layer is what makes a dependent unit root on its parent's tip rather than beside it.

  Its consumers — `check-pr-dependencies-ready.sh`'s `branch_for_pr()`, `pr-branch-creation.md`'s parent resolution, `batch-end-pr.md`'s `--base` — all resolve correctly with no change.
