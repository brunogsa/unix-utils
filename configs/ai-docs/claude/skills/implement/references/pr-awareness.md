# PR-label input, label resolution, per-PR loop, and manifest writes

Detail for `/implement`'s pre-flight when the invocation arg is a `PR-N` label or a `PR-N, PR-M, ...` list, instead of `<task-ids>`.

Load this only when the arg matches that shape. A plain `<task-ids>` run never loads it and is entirely unaffected — every mechanic below is additive, gated on "was a PR-label given".

A "Single PR." plan (the PR Breakdown's literal backward-compat escape string) never receives a PR-label arg in the first place, so it takes none of these branches either.

## Recognizing a PR-label arg

The invocation arg is PR-label mode when it matches `PR-N` or a comma-space list of them (`PR-1, PR-2`) — same one-space-after-comma convention as `<task-ids>`.

Anything else (bare numbers, a numeric comma-list) is the existing `<task-ids>` mode; §1.1–§8 run exactly as documented for it, unchanged.

## DAG re-check moved out — SKILL.md §1.3 owns it now

This file used to re-run `check-pr-dag.sh` before resolving the first label.
That instruction moved to SKILL.md §1.3, which runs both DAG checkers once, for the whole invocation, before §2 seeds anything.
So label resolution below never re-checks the DAG itself.

## Resolving each PR-N label

For each `PR-N` in the arg, in order, resolve its task-id list:

```bash
~/.claude/skills/implement/scripts/get-pr-tasks.sh <plan-file> <PR-N>
```

Exit 0 prints the comma-space task-id list in the same format `<task-ids>` already expects — feed it straight into §3.3's exact-match loop.
Exit 1 (label not found) or exit 2 (usage/parse error) surfaces the diagnostic and stops before dispatching anything for that PR.

## State-file keying (§2.3 widened)

Each PR in the list gets its **own** state file, keyed on both `slug` and this PR's own `pr_label` (never the whole list) — never on `slug` alone.
This is what lets two worktrees running different PRs of the same plan avoid adopting each other's file.
It's also what lets a multi-PR list's per-PR loop (below) tell its PRs' state files apart.

Every PR's file is created **now**, right after §2's TaskList is seeded — not lazily as each PR's turn comes up.
That is what lets a halt on PR-2 still leave PR-3's file on disk with every task `pending`.
It reads as a visible record of work that never started, rather than a file that never existed.

A plain `<task-ids>` run writes `pr_label: ""` — see SKILL.md §2.3 for the exact lookup command and JSON shape.

## Branch creation (only when a checkout is needed)

Before dispatching a PR's tasks, ask:

```bash
~/.claude/skills/implement/scripts/need-git-checkout.sh <plan-file> <PR-N> <worktree-path>
```

`<worktree-path>` is the directory this run operates in — the worktree from §1.4 if one was created, else CWD.

**Prints `no`** → dispatch this PR's tasks on the current branch.
No `git checkout -b` runs.
No manifest write happens here either — this PR's own `branches_<slug>.md` entry is written later, at its own batch-end (see "Manifest writes", below), same as every other PR.

**Prints `yes`** → resolve and create `<feat_branch>/pr<N>` before dispatching, following [`pr-branch-creation.md`](pr-branch-creation.md).

That file carries the existing-branch check for a branch already present.
That case is legitimate — a halted run's fresh re-invocation can reach this same PR again and find its branch already there.
It also carries the zero-parent, single-parent, and diamond-dependency creation cases and their dependency guards. A `no` run never reads it.

## Manifest writes (`branches_<slug>.md`)

Every PR — checkout-needed or not — writes its own entry once, at its own batch-end (§8.3, see `references/batch-end-pr.md`), never in this branch-creation step:

```bash
~/.claude/skills/implement/scripts/append-branch-pr-entry.sh <worktree-path>/branches_<slug>.md <slug> <this-PR-label> <this-PR-branch>
```

A `no`-checkout PR's branch is the `git branch --show-current` value from its own preflight; a checkout-needed PR's branch is whatever `checkout -b` (or the existing-branch check's plain `checkout`) resolved to above.

This is the *only* write for a given PR's entry.
Nothing runs at that PR's own branch creation (see the guard step above), so there's no earlier write for this one to race against.
A PR is simultaneously a later PR's recorded parent and the subject of its own batch-end write — that dual role is exactly what makes the guard's precondition always hold above.
`append-branch-pr-entry.sh`'s idempotence still matters across two separate runs reaching the *same* PR's batch-end.
Example: an earlier run halted mid-§8, and a fresh `/implement` re-invocation for this same PR reaches §8 again.
It does not need to matter across two different call sites.

## The per-PR loop and fail-fast

A PR-label list runs the existing §3–§8 batch once per PR, strictly in the order given.
The whole pipeline from `BATCH_BASE_SHA` capture through batch-end and PR creation repeats per PR, so each PR's repo-green gate, quality-gate tail, and diff scope to only that PR's own commits.

§1.1 (locate plan/spec), §1.2 (interview), §1.3 (DAG re-check), §1.4 (worktree setup), §1.5 (label resolution, this file) and §2 (TaskList seeding, plus every unit's state file) run once for the whole list.

§2 seeds **every** PR's entries upfront — each PR's tasks followed by that PR's four batch-end reminders, in the order the PRs execute.
So the list reads as the whole run's timeline from the start.
A fail-fast stop simply leaves the later PRs' entries `pending`.

Before each PR's loop iteration, label resolution and the checkout decision above both run fresh for that PR.
The DAG re-check does not — §1.3 already ran it once, for the whole invocation.

**Stop predicate, checked after each PR's own §8 completes:** proceed to the next PR only if every one of that PR's tasks reached `[Done]` (none terminal-without-`[Done]`) AND §8.1's repo-green gate passed.
Otherwise stop — do not create the next PR's branch, do not dispatch any of its tasks.
Report the batch as it stands; the remaining PRs in the list are untouched.

This mirrors §5.3's task-level chain-abort but at the PR level.
A task failure inside one PR's batch already chain-aborts that PR's own dependents via the existing mechanism.
This stop predicate is what additionally keeps a failed PR from starting the *next* PR in the list.
A chain-aborted dependent (`reason: "blocked-upstream"`) is terminal-without-`[Done]` too — it fails this PR's every-task-`[Done]` check and halts here.
