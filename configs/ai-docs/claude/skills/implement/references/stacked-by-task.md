# Stacked-by-task delivery — one PR per task

Read this whenever §1.2 asked the stacked question, which is every run. It owns the question itself, the two gates that can overrule the answer, and everything the `yes` branch changes.

The mechanics of a stack once it exists — propagation, bottom-up merge, retarget, the native rulebook — stay in [`stacked-prs.md`](stacked-prs.md). This file only says how a unit becomes one.

## The two delivery shapes

The plan never decides this. Its Task Breakdown and PR Breakdown read identically either way; only §1.2's answer differs.

| | What one PR is | What one task is |
|---|---|---|
| **Stacked** | one **task** | a layer of the stack |
| **Not stacked** | one **unit** — a `PR-N` entry, or the whole `<task-ids>` run | a commit inside that PR |

A unit is a stack.

A plan whose PR Breakdown reads `Single PR.` with four tasks delivers **one** stack of four PRs.

A plan with `PR-1` and `PR-2` delivers **two** stacks, each registered separately, with the `PR-1 → PR-2` dependency additionally spelled out in `PR-2`'s first-layer body.

## §1.2's question, and the two gates that can overrule it

Ask it as an opt-out — **"Deliver each task as its own stacked PR?" (yes/no, default yes)**.

Run both gates **before** asking, and when either fires, do not ask the question at all: report which one fired and confirm the forced non-stacked run via the same `AskUserQuestion` call.

- **`gh stack` is not installed** — `gh stack --help` exits non-zero. Without it a stack can be built but never registered.
- **A task in scope has two or more in-scope parents** — a true join:

  ```bash
  ~/.claude/skills/implement/scripts/resolve-task-order.sh <plan-file> <task-ids>
  ```

  Exit 1 names every offending task and its parents; surface that diagnostic verbatim. Exit 2 is a usage/parse error and stops the run like any other §1.3 failure.

**Neither gate is overridable.** A user who answers `yes` still gets a non-stacked run when one fired.

The confirmation exists so the downgrade is never silent, not to offer a way past it.

A join is refused by policy, not by impossibility.

A chain *can* be built through one, but the layer that joins two parents would then appear to depend on whichever happened to be ordered second.

No reviewer can tell that artificial edge from a real one.

Forks and disconnected tasks are not joins and never block.

## The layer order is the user's to set

Exit 0 prints a topological order — a task never precedes one it depends on, ties broken lowest-id-first. Show that order in the same interview call and let the user reorder it.

Never judge a reordering by eye — put the user's candidate back through the same script:

```bash
~/.claude/skills/implement/scripts/resolve-task-order.sh --verify <plan-file> <task-ids> <candidate-order>
```

`<task-ids>` is this unit's scope, unchanged from the gate call above; `<candidate-order>` is what the user typed back.

Passing both is what keeps a PR-label run working.

A unit holds only its own PR's tasks, so scoping to the candidate alone would flag every task of every other PR as missing.

Exit 0 accepts it. Exit 1 names every pair where a task landed before one of its in-scope parents; show that diagnostic and ask again.

Exit 2 means the candidate dropped or repeated an id.

This is the only place a delivery-order preference can be expressed. The plan's task numbering is an authoring artifact, not a shipping order.

A plan that numbered the library change before the contract change still ships contract-first if the user says so here.

## Layer branches

**Layer 1 needs no new branch.** It is whatever branch §3.1 already left checked out — the current branch on a `<task-ids>` run, `<feat_branch>/pr<N>` on a PR-label run.

Every rule in [`pr-branch-creation.md`](pr-branch-creation.md) about resolving a unit's starting point still applies unchanged, diamond PR-level dependencies included.

**Layers 2..M** each get a branch cut from the previous layer's tip, immediately before that task is dispatched:

```bash
git checkout -b <layer-1-branch>-t<task-id>     # from the previous layer's tip, i.e. current HEAD
```

The `-t<id>` suffix is a hyphen, never a slash: `refs/heads/<layer-1-branch>` already exists as a file, so a `<layer-1-branch>/t<id>` ref could not be created beside it.

Record each layer's branch in that task's `tasks[]` entry in the state file, as `branch`.

Existing-branch check first, same reason and same shape as `pr-branch-creation.md`'s.

An earlier halted run may have left the branch behind, and since there is no resume path, a fresh invocation must adopt it (`git checkout`, no `-b`) rather than fail.

## Stacked mode is strictly sequential

§5.4's parallel dispatch is **off** for the whole unit: never load `parallel-worktrees`, and treat a multi-id `--eligible-set` as its lowest-ordered member alone.

Each layer's branch is cut from the previous layer's tip, so a task cannot start until the one before it has committed.

Two tasks running in parallel worktrees have no single tip to stack the next layer on.

## Batch end

Not here — [`stacked-by-task-batch-end.md`](stacked-by-task-batch-end.md) owns the push, the one-PR-per-layer loop, the `gh stack link`, and both branch records.

Read it at §8.3, not now: a batch runs its whole §3–§8 pass in between, so anything loaded here is gone by the time it binds.
