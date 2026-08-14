# PR-label input, label resolution, per-PR loop, and branch recording

Detail for `/implement`'s pre-flight when the invocation arg is a `PR-N` label or list, instead of `<task-ids>`.

Every mechanic below is additive, gated on that arg shape, so a plain `<task-ids>` run is unaffected.

A "Single PR." plan (the PR Breakdown's literal backward-compat escape string) never receives a PR-label arg, so it takes none of these branches.

## Recognizing a PR-label arg

Anything that isn't `PR-N` or a comma-list of them (bare numbers, a numeric comma-list) stays `<task-ids>` mode; §1.1–§8 run exactly as documented.

SKILL.md §1.3 ran both DAG checkers once for the whole invocation before §2 seeded anything, so label resolution below never re-checks the DAG.

## Resolving each PR-N label

For each `PR-N` in the arg, in order, resolve its task-id list:

```bash
~/.claude/skills/implement/scripts/get-pr-tasks.sh <plan-file> <PR-N>
```

Exit 0 prints the comma-space task-id list in `<task-ids>` format — feed it straight into §3.3's exact-match loop.
Exit 1 (label not found) or exit 2 (usage/parse error) surfaces the diagnostic and stops before dispatching anything for that PR.

## Stack mode: merge or native (decided once, at §1.5)

A PR-label run syncs its stack in one of two modes, decided once, right after label resolution:

- **`merge`** — the default: branches stay append-only, synced by merging parent into child ([`stacked-prs.md`](stacked-prs.md)).
- **`native`** — GitHub's native stacked PRs (public preview): GitHub owns restacks and retargeting, server-side, by rebase.

Decide by shape first, availability second — both must pass for `native`:

- Any PR with 2+ parents in its `Depends on:` clause (a diamond, unrepresentable in a linear-only native stack) → `merge`.
- Linear chain AND `gh stack --help` exits 0 (the `gh-stack` extension is installed) → `native`. Extension missing → `merge`.

**This decision reads the PR graph, separate from §1.2's stacked-by-task gates** ([`stacked-by-task.md`](stacked-by-task.md)), which read the *task* graph inside one PR.
The two are independent: a `Mode: merge` plan can still ship each of its PRs as a linear stack of per-task layers, and vice versa.

Record the decision as a `Mode: <merge|native>` line under the plan's `## PR Breakdown` heading — same inline edit style as a `Branch:` clause, idempotent on re-runs.

The mode is sticky for the stack's whole life; later sessions (review fixes, post-merge sync) read it for their rulebook in [`stacked-prs.md`](stacked-prs.md):

- `merge` branches must never be linked into a native stack — their merge commits already made the history non-linear.
- `native` branches must never be manually merged into — one merge commit breaks the linearity the feature requires.

Everything else here is mode-independent: branch creation, `Branch:` recording, the per-PR loop, and fail-fast run identically.
The only `native` addition is one link step at the final PR's batch end — see [`batch-end-pr-native-link.md`](batch-end-pr-native-link.md).

## State-file keying (§2.3 widened)

Each PR gets its **own** state file, keyed on both `slug` and this PR's own `pr_label` — never the whole list, never `slug` alone.

That keying stops two worktrees running different PRs of the same plan from adopting each other's file, and lets a multi-PR list's per-PR loop tell its PRs' files apart.

Creating them all now (SKILL.md §2.3), not lazily, is what lets a halt on PR-2 still leave PR-3's file on disk with every task `pending`.

That leftover file is a visible record of work that never started.

## Branch creation (only when a checkout is needed)

`need-git-checkout.sh` (SKILL.md §3.1) answers from the plan alone: this PR's `Depends on:` field, plus whether any PR entry already carries a `Branch:` field from an earlier batch's push.

On `no`, this PR's `Branch:` clause isn't written here — see "Branch recording", below.

On `yes`, [`pr-branch-creation.md`](pr-branch-creation.md) owns resolving and creating this PR's branch; a `no` run never reads it.

## Branch recording (the plan's `Branch:` clause)

Every PR — checkout-needed or not — records its branch once, in its own PR Breakdown entry, at its own batch-end push, never at branch creation.

The field's grammar, the guarantee that this is its only writer, and the idempotence rule all live with the step that performs the write: [`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md), read at §8.1.

Nothing here needs them earlier.

## The per-PR loop and fail-fast

Each PR's own §3–§8 run scopes that PR's repo-green gate, quality-gate tail, and diff to only its own commits.

Label resolution and the checkout decision above run fresh per PR; the DAG re-check `implement/SKILL.md` §1.3 owns does not.

§2 seeds **every** PR's entries upfront — each PR's tasks followed by that PR's four batch-end reminders — so the list reads as the whole run's timeline.
A fail-fast stop simply leaves the later PRs' entries `pending`.

**Stop predicate, checked after each PR's own §8 completes:**
Proceed to the next PR only if every one of its tasks reached `[Done]` (none terminal-without-`[Done]`) and its whole batch end completed.

Both opt-in gates count as "completed" only when the interview turned them on — a declined gate never ran, so requiring it to have passed would block every PR after the first.

Otherwise stop: create no next PR's branch, dispatch none of its tasks, and report the batch as it stands — the remaining PRs stay untouched.

This mirrors §5.3's task-level chain-abort at the PR level: a task failure already chain-aborts that PR's own dependents, and this predicate also keeps a failed PR from starting the *next* one.
A chain-aborted dependent (`reason: "blocked-upstream"`) is terminal-without-`[Done]` too, so it fails this PR's every-task-`[Done]` check and halts here.
