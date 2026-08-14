# Batch-end — branch record & PR-level status marker

Read this only on a PR-label run (`pr_label` is not `""`) — skip entirely on a plain `<task-ids>` run.

A stacked run reaches here too, and both edits below still apply to the unit as a whole.

Its *additional* per-task layer records are [`stacked-by-task-batch-end.md`](stacked-by-task-batch-end.md)'s, written in the same pass; on a stacked run the branch recorded here is the unit's topmost layer.

**Dispatched from inside §8.1, right after its always-run push** (`batch-end-review.md`'s §8.1 step 2) — the separate opt-in PR step reached from the same place lives in [`batch-end-pr.md`](batch-end-pr.md).

## Branch record & PR-level status marker

Both edits land in this PR's own entry in the plan's PR Breakdown, in one pass:

```
### PR-N. [Done] <theme>

**Tasks**: <N, N>

**Depends on**: <none | PR-N>

**Branch**: `<branch-name>`
```

- **`Branch:` field** — record this PR's branch (`git branch --show-current` right now), once, regardless of whether step 2 succeeds.

- **PR-level status marker** — set this PR's own heading to **`[Done]`**, mirroring §6's task-level marker convention one level up.
  Reaching here means every task is `[Done]` — a unit that couldn't finish halted at §5.5.
  The marker reflects the *code* being done: a PR that fails to open still halts the run (§5.5), but its work is finished.

Write both inline, in a task-level marker's edit style — never scripted.

Each PR is its own `###` heading and each field its own line, per the grammar the `spec-driven-development` skill's `assets/plan-template.md` authors.
A plan written before that grammar packs the same fields onto one numbered-list line; `parse-pr-breakdown.sh` reads either, so edit whichever shape the plan already uses.
The backticks are load-bearing: `parse-pr-breakdown.sh` reads the name between them, so a branch containing periods survives.

## Why every PR records here, and only here

Every PR — checkout-needed or not — records its branch at its own batch-end push, never at branch creation.
A `no`-checkout PR's branch is `git branch --show-current`'s value from its own preflight; a checkout-needed PR's is whatever `checkout -b` (or the existing-branch check's plain `checkout`) resolved to.

This is the *only* write for a PR's clause — [`pr-branch-creation.md`](pr-branch-creation.md)'s guard writes nothing.
So no earlier write can race it, even though a PR is both a later PR's recorded parent and the subject of its own batch-end write.

Re-writing the clause must stay idempotent across two separate runs reaching the *same* PR's batch-end — replace the existing clause rather than appending a second one.
Example: an earlier run halted mid-§8 and a fresh `/implement` re-invocation reaches §8 again.
It need not be idempotent across two different call sites.
