# PR-label input, per-PR loop, and branch creation (§1 detail)

Detail for `/implement`'s pre-flight when the invocation arg is a `PR-N` label or a `PR-N, PR-M, ...` list, instead of `<task-ids>`.

Load this only when the arg matches that shape. A plain `<task-ids>` run never loads it and is entirely unaffected — every mechanic below is additive, gated on "was a PR-label given".

A "Single PR." plan (the PR Breakdown's literal backward-compat escape string) never receives a PR-label arg in the first place, so it takes none of these branches either.

## Recognizing a PR-label arg

The invocation arg is PR-label mode when it matches `PR-N` or a comma-space list of them (`PR-1, PR-2`) — same one-space-after-comma convention as `<task-ids>`.

Anything else (bare numbers, a numeric comma-list) is the existing `<task-ids>` mode; §1.1–§9 run exactly as documented for it, unchanged.

## Defensive DAG re-check, before resolving the first label

Before resolving the first `PR-N` in the arg, re-run:

```bash
~/.claude/skills/spec-driven-development/scripts/check-pr-dag.sh <plan-file>
```

Self-review validated this DAG once, but the plan is symlinked and mutable for the rest of execution (§1.3).
A later hand-edit could reintroduce a cycle, dangling reference, or duplicate label that self-review already caught and cleared.

Exit 1 blocks with the script's own diagnostic on stderr, the same message self-review would have shown. Exit 0 (including the "Single PR." / absent-section trivial pass) proceeds.

## Resolving each PR-N label

For each `PR-N` in the arg, in order, resolve its task-id list:

```bash
~/.claude/skills/implement/scripts/get-pr-tasks.sh <plan-file> <PR-N>
```

Exit 0 prints the comma-space task-id list in the same format `<task-ids>` already expects — feed it straight into §1.6's exact-match loop.
Exit 1 (label not found) or exit 2 (usage/parse error) surfaces the diagnostic and stops before dispatching anything for that PR.

## State-file keying (§1.5 widened)

Each PR in the list gets its **own** state file, keyed on both `slug` and this PR's own `pr_label` (never the whole list) — never on `slug` alone.
This is what lets two worktrees running different PRs of the same plan avoid adopting each other's file.
It's also what lets a multi-PR list's per-PR loop (below) tell its PRs' state files apart.

A plain `<task-ids>` run writes `pr_label: ""` — see SKILL.md §1.5 for the exact lookup command and JSON shape.

## Branch creation (only when a checkout is needed)

Before dispatching a PR's tasks, ask:

```bash
~/.claude/skills/implement/scripts/need-git-checkout.sh <plan-file> <PR-N> <worktree-path>
```

`<worktree-path>` is the directory this run operates in — the worktree from §1.3 if one was created, else CWD.

**Prints `no`** → dispatch this PR's tasks on the current branch. No `git checkout -b`, no `branches_<slug>.md` write (that manifest write is out of this task's scope).

**Prints `yes`** → create `<feat_branch>/pr<N>` before dispatching:

- `<feat_branch>` = `git branch --show-current`, with any trailing `/pr<digits>` suffix stripped. Stateless — no new persistent store, matching the plan's NFR.
- Count `PR-N`'s parents from its PR Breakdown line's `Depends on:` clause (already open from §1.1).
- **Zero parents** (a second independent root reached after an earlier PR's batch already ran) → branch explicitly from the confirmed base branch (§1.2): `git checkout -b <feat_branch>/pr<N> <base-branch>`.
  Never from current HEAD — HEAD may sit at an unrelated PR's tip.
- **Exactly one parent** → `git checkout -b <feat_branch>/pr<N>` with no explicit base ref, i.e. from current HEAD.
  This is correct because a DAG-root PR's commits (the `no`-checkout case above) land directly on the pre-existing branch.
  By the time a single dependent PR runs, HEAD already sits at its parent's tip.
- **Two or more parents** (diamond dependency) → stop and report a clear "diamond dependency not supported here" block; do not attempt a merge.
  Real diamond-merge handling is a separate, later concern outside this task's scope.

## The per-PR loop and fail-fast

A PR-label list runs the existing §1.4–§9 batch once per PR, strictly in the order given.
The whole pipeline from `BATCH_BASE_SHA` capture through batch-end and PR creation repeats per PR, so each PR's gate, tails, and diff scope to only that PR's own commits.

§1.1 (locate plan/spec), §1.2 (interview), §1.3 (worktree setup), and §2 (orchestration review) run once for the whole list.
§2 reviews the list's PR ordering and dependencies as a whole, which is cheaper and more useful than reviewing each PR in isolation.

Before each PR's loop iteration: the defensive DAG re-check, label resolution, and checkout decision above, all run fresh for that PR.

**Stop predicate, checked after each PR's own §9 completes:** proceed to the next PR only if every one of that PR's tasks reached `[Done]` (none terminal-without-`[Done]`) AND §9.1's repo-green gate passed.
Otherwise stop — do not create the next PR's branch, do not dispatch any of its tasks.
Report the batch as it stands; the remaining PRs in the list are untouched.

This mirrors §5.4's task-level chain-abort but at the PR level.
A task failure inside one PR's batch already chain-aborts that PR's own dependents via the existing mechanism.
This stop predicate is what additionally keeps a failed PR from starting the *next* PR in the list.
