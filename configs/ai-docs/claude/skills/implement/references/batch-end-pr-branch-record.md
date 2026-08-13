# Batch-end — branch record & PR-level status marker

Read this only on a PR-label run (`pr_label` is not `""`) — skip entirely on a plain `<task-ids>` run.

**Dispatched from inside §8.1, right after its always-run push** (`batch-end-review.md`'s §8.1 step 2) — the separate opt-in PR step reached from the same place lives in [`batch-end-pr.md`](batch-end-pr.md).

## Branch record & PR-level status marker

Both edits below land in this PR's own entry in the plan's PR Breakdown, in one pass:

- **`Branch:` field** — record this PR's branch (`git branch --show-current` right now), once, regardless of whether step 2 succeeds.
  See `references/pr-awareness.md`'s "Branch recording" for why this write belongs here, not at branch creation.

- **PR-level status marker** — set this PR's own heading to **`[Done]`**, mirroring §6's task-level marker convention one level up:
  ```
  ### PR-N. [Done] <theme>

  **Tasks**: <N, N>

  **Depends on**: <none | PR-N>

  **Branch**: `<branch-name>`
  ```
  Write both inline, in a task-level marker's edit style — never scripted.
  Reaching here means every task is `[Done]` — a unit that couldn't finish halted at §5.5.
  The marker reflects the *code* being done: a PR that fails to open still halts the run (§5.5), but its work is finished.
