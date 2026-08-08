# PR-label input, label resolution, per-PR loop, and branch recording

Detail for `/implement`'s pre-flight when the invocation arg is a `PR-N` label or a `PR-N, PR-M, ...` list, instead of `<task-ids>`.

Load this only when the arg matches that shape — every mechanic below is additive, gated on "was a PR-label given", so a plain `<task-ids>` run is entirely unaffected.

A "Single PR." plan (the PR Breakdown's literal backward-compat escape string) never receives a PR-label arg, so it takes none of these branches either.

## Recognizing a PR-label arg

The invocation arg is PR-label mode when it matches `PR-N` or a comma-space list of them (`PR-1, PR-2`) — same one-space-after-comma convention as `<task-ids>`.

Anything else (bare numbers, a numeric comma-list) is the existing `<task-ids>` mode; §1.1–§8 run exactly as documented, unchanged.

## DAG re-check moved out — SKILL.md §1.3 owns it now

§1.3 runs both DAG checkers once for the whole invocation, before §2 seeds anything, so label resolution below never re-checks the DAG itself.

## Resolving each PR-N label

For each `PR-N` in the arg, in order, resolve its task-id list:

```bash
~/.claude/skills/implement/scripts/get-pr-tasks.sh <plan-file> <PR-N>
```

Exit 0 prints the comma-space task-id list in the format `<task-ids>` expects — feed it straight into §3.3's exact-match loop.
Exit 1 (label not found) or exit 2 (usage/parse error) surfaces the diagnostic and stops before dispatching anything for that PR.

## Stack mode: merge or native (decided once, at §1.5)

A PR-label run syncs its stack in one of two modes, decided once per invocation, right after label resolution:

- **`merge`** — the default: branches stay append-only, synced by merging parent into child ([`stacked-prs.md`](stacked-prs.md)).
- **`native`** — GitHub's native stacked PRs (public preview): GitHub owns restacks and retargeting, server-side, by rebase.

Decide by shape first, availability second — both must pass for `native`:

- Any PR with 2+ parents in its `Depends on:` clause (a diamond) → `merge`. Native stacks are linear-only, so a diamond is unrepresentable there.
- Linear chain AND `gh stack --help` exits 0 (the `gh-stack` extension is installed) → `native`. Extension missing → `merge`.

Record the decision as a `Mode: <merge|native>` line directly under the plan's `## PR Breakdown` heading — same inline edit style as a `Branch:` clause, idempotent on re-runs.

The mode is sticky for the stack's whole life; later sessions (review fixes, post-merge sync) read it to pick their rulebook in [`stacked-prs.md`](stacked-prs.md):

- `merge` branches must never be linked into a native stack — their merge commits already made the history non-linear.
- `native` branches must never be manually merged into — one merge commit breaks the linearity the feature requires.

Everything else in this file is mode-independent: branch creation, `Branch:` recording, the per-PR loop, and fail-fast run identically.
The only `native` addition is one link step at the final PR's batch end — see "Native mode" in [`batch-end-pr.md`](batch-end-pr.md).

## State-file keying (§2.3 widened)

Each PR gets its **own** state file, keyed on both `slug` and this PR's own `pr_label` — never the whole list, never `slug` alone.
That is what lets two worktrees running different PRs of the same plan avoid adopting each other's file, and lets a multi-PR list's per-PR loop tell its PRs' files apart.

Every PR's file is created **now**, right after §2's TaskList is seeded — not lazily as each PR's turn comes up.
That is what lets a halt on PR-2 still leave PR-3's file on disk with every task `pending` — a visible record of work that never started.

A plain `<task-ids>` run writes `pr_label: ""` — see SKILL.md §2.3 for the exact lookup command and JSON shape.

## Branch creation (only when a checkout is needed)

Before dispatching a PR's tasks, ask:

```bash
~/.claude/skills/implement/scripts/need-git-checkout.sh <plan-file> <PR-N>
```

It answers from the plan alone: this PR's `Depends on:` clause, plus whether any PR line already carries a `Branch:` clause from an earlier batch's push.

**Prints `no`** → dispatch this PR's tasks on the current branch; no `git checkout -b` runs.
Nothing is recorded on the plan line here — this PR's `Branch:` clause is written later, at its own batch-end push (see "Branch recording", below).

**Prints `yes`** → resolve and create `<feat_branch>/pr<N>` before dispatching, following [`pr-branch-creation.md`](pr-branch-creation.md).

That file carries the existing-branch check — legitimate, since a halted run's re-invocation can reach this PR again and find its branch already there.
It also carries the zero-parent, single-parent, and diamond-dependency creation cases and their dependency guards. A `no` run never reads it.

## Branch recording (the plan's `Branch:` clause)

Every PR — checkout-needed or not — records its branch once, on its PR Breakdown line, at its own batch-end push (§8.3, see `references/batch-end-pr.md`), never in this branch-creation step:

```
N. **[Done] PR-N** — <title>. Tasks: <N, N>. Depends on: <none | PR-N>. Branch: `<branch-name>`.
```

Write it inline, in the same edit style as a status marker — never scripted. The backticks are load-bearing: `parse-pr-breakdown.sh` reads the name between them, so a branch containing periods survives.

A `no`-checkout PR's branch is the `git branch --show-current` value from its own preflight; a checkout-needed PR's branch is whatever `checkout -b` (or the existing-branch check's plain `checkout`) resolved to.

This is the *only* write for a PR's clause — nothing runs at that PR's own branch creation (see the guard step above), so no earlier write can race it.
A PR is both a later PR's recorded parent and the subject of its own batch-end write — that dual role is what keeps the guard's precondition holding above.

Re-writing the clause must stay idempotent across two separate runs reaching the *same* PR's batch-end — replace the existing clause rather than appending a second one.
Example: an earlier run halted mid-§8 and a fresh `/implement` re-invocation reaches §8 again. It need not be idempotent across two different call sites.

## The per-PR loop and fail-fast

A PR-label list runs §3–§8 once per PR, strictly in the order given — `BATCH_BASE_SHA` capture through batch-end and PR creation.
So each PR's repo-green gate, quality-gate tail, and diff scope to only that PR's own commits.

§1.1–§1.5 (locate plan/spec, interview, DAG re-check, worktree setup, and this file's label resolution) and §2 (TaskList seeding, plus every unit's state file) run once for the whole list.

§2 seeds **every** PR's entries upfront — each PR's tasks followed by that PR's four batch-end reminders, in execution order — so the list reads as the whole run's timeline.
A fail-fast stop simply leaves the later PRs' entries `pending`.

Before each PR's loop iteration, label resolution and the checkout decision above both run fresh for that PR; the DAG re-check does not (§1.3, above).

**Stop predicate, checked after each PR's own §8 completes:**
Proceed to the next PR only if every one of its tasks reached `[Done]` (none terminal-without-`[Done]`) and its whole batch end completed.

Both opt-in gates are part of "completed" only when the interview turned them on.
A declined gate never ran, so requiring it to have passed would block every PR after the first.

Otherwise stop — do not create the next PR's branch, do not dispatch any of its tasks.
Report the batch as it stands; the remaining PRs are untouched.

This mirrors §5.3's task-level chain-abort at the PR level: a task failure already chain-aborts that PR's own dependents, and this predicate additionally keeps a failed PR from starting the *next* one.
A chain-aborted dependent (`reason: "blocked-upstream"`) is terminal-without-`[Done]` too — it fails this PR's every-task-`[Done]` check and halts here.
