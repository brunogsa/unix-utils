# PR-label input, label resolution, per-PR loop, and manifest writes

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

**Prints `no`** → dispatch this PR's tasks on the current branch.
No `git checkout -b` runs.
No manifest write happens here either — this PR's own `branches_<slug>.md` entry is written later, at its own batch-end (see "Manifest writes", below), same as every other PR.

**Prints `yes`** → resolve and create `<feat_branch>/pr<N>` before dispatching, following [`pr-branch-creation.md`](pr-branch-creation.md).

That file carries the resume check for an already-existing branch, plus the zero-parent, single-parent, and diamond-dependency creation cases and their dependency guards. A `no` run never reads it.

## Manifest writes (`branches_<slug>.md`)

Every PR — checkout-needed or not — writes its own entry once, at its own batch-end (§9, see `references/batch-end-pr.md`), never in this branch-creation step:

```bash
~/.claude/skills/implement/scripts/append-branch-pr-entry.sh <worktree-path>/branches_<slug>.md <slug> <this-PR-label> <this-PR-branch>
```

A `no`-checkout PR's branch is the `git branch --show-current` value from its own preflight; a checkout-needed PR's branch is whatever `checkout -b` (or the resume-check's plain `checkout`) resolved to above.

This is the *only* write for a given PR's entry.
Nothing runs at that PR's own branch creation (see the guard step above), so there's no earlier write for this one to race against.
A PR is simultaneously a later PR's recorded parent and the subject of its own batch-end write — that dual role is exactly what makes the guard's precondition always hold above.
`append-branch-pr-entry.sh`'s idempotence still matters across re-runs of the *same* PR's batch-end (a resumed batch re-reaching §9), not across two different call sites.

## The per-PR loop and fail-fast

A PR-label list runs the existing §1.4–§9 batch once per PR, strictly in the order given.
The whole pipeline from `BATCH_BASE_SHA` capture through batch-end and PR creation repeats per PR, so each PR's gate, tails, and diff scope to only that PR's own commits.

§1.1 (locate plan/spec), §1.2 (interview), §1.3 (worktree setup), and §2 (orchestration review) run once for the whole list.
§2 reviews the list's PR ordering and dependencies as a whole, which is cheaper and more useful than reviewing each PR in isolation.

**Exception: §2.2's TaskList task creation repeats per PR.** Before dispatching each PR's first task, create entries only for that PR's own resolved task-ids — never every PR's tasks upfront.

Before each PR's loop iteration: the defensive DAG re-check, label resolution, and checkout decision above, all run fresh for that PR.

**Stop predicate, checked after each PR's own §9 completes:** proceed to the next PR only if every one of that PR's tasks reached `[Done]` (none terminal-without-`[Done]`) AND §9.1's repo-green gate passed.
Otherwise stop — do not create the next PR's branch, do not dispatch any of its tasks.
Report the batch as it stands; the remaining PRs in the list are untouched.

This mirrors §5.4's task-level chain-abort but at the PR level.
A task failure inside one PR's batch already chain-aborts that PR's own dependents via the existing mechanism.
This stop predicate is what additionally keeps a failed PR from starting the *next* PR in the list.
A chain-aborted dependent (`reason: "blocked-upstream"`) is terminal-without-`[Done]` too — it fails this PR's every-task-`[Done]` check and halts here.
