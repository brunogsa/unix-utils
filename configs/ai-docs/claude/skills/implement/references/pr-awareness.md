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

**Prints `no`** → dispatch this PR's tasks on the current branch.
No `git checkout -b` runs.
No manifest write happens here either — this PR's own `branches_<slug>.md` entry is written later, at its own batch-end (see "Manifest writes", below), same as every other PR.

**Prints `yes`** → resolve `<feat_branch>/pr<N>` before dispatching:

- `<feat_branch>` = `git branch --show-current`, with any trailing `/pr<digits>` suffix stripped. Stateless — no new persistent store, matching the plan's NFR.
- **Resume check, first**: `git rev-parse --verify --quiet <feat_branch>/pr<N>`.
  Branch already exists → `git checkout <feat_branch>/pr<N>` (plain, no `-b`) and skip every step below.
  The guard already ran, and passed, the first time this branch was created — re-running it on an adopted branch is redundant, not merely safe-to-repeat.
  This guarantee holds for the diamond case too: its guard already ran by branch-creation time, in the diamond-specific position after the checkout and merges.
  That run validated ancestry against every parent, not just one, so an adopted diamond branch inherits the same completed guarantee.
- Branch doesn't exist yet (first time through) → count `PR-N`'s parents from its PR Breakdown line's `Depends on:` clause (already open from §1.1):
  - **Zero parents** (a second independent root reached after an earlier PR's batch already ran) → branch explicitly from the confirmed base branch (§1.2): `git checkout -b <feat_branch>/pr<N> <base-branch>`.
    Never from current HEAD — HEAD may sit at an unrelated PR's tip.
    No parent to guard against or record.
  - **Exactly one parent** → first, the dependency guard:
    ```bash
    ~/.claude/skills/implement/scripts/check-pr-dependencies-ready.sh <plan-file> <PR-N> <worktree-path>
    ```
    Exit 1 refuses to create this PR's branch or dispatch any of its tasks.
    Surface the script's own stderr diagnostic verbatim and stop; do not retry.
    Exit 2 (usage/parse error) surfaces the same way.
    The guard's own `branch_for_pr()` hard-requires the parent's `branches_<slug>.md` entry to already exist — no fallback ancestry source, absence is always a hard block.
    That precondition is already satisfied by the time this guard runs, every time.
    The stop predicate (below) means the parent PR's own full batch already completed before this PR's pre-flight ever started.
    That completed batch includes the parent's own §9 batch-end, where it wrote its own entry (see "Manifest writes" below).
    So this step writes nothing itself; only the parent's own batch-end write ever populates this entry, and it always got there first.
    Exit 0 → `git checkout -b <feat_branch>/pr<N>` with no explicit base ref, i.e. from current HEAD.
    Correct because a DAG-root PR's commits (the `no`-checkout case above) land directly on the pre-existing branch, so by the time a single dependent PR runs, HEAD already sits at its parent's tip.
  - **Two or more parents** (diamond dependency) → resolve each parent's branch name from `branches_<slug>.md` first, in the order listed in `Depends on:`.
    Same `**<label>**` → `` branch: `<name>` `` lookup that `check-pr-dependencies-ready.sh`'s own `branch_for_pr()` uses internally.
    Every parent's entry is guaranteed to already exist here, by the same reasoning as the single-parent case above.
    Each parent's own batch already completed and wrote its own manifest entry before this PR's pre-flight could start.
    - `git checkout -b <feat_branch>/pr<N> <first-listed-parent-branch>` — explicit base ref, same as the "Zero parents" bullet, never bare HEAD.
      HEAD may sit at an unrelated PR's tip by the time a diamond PR's turn comes up.
    - Then, for each remaining parent in listed order: `git merge <parent-branch> -m "Merge <parent-label> into <PR-N>"`.
      A conflict here is resolved by `/implement` itself, never surfaced to the user.
      Read the conflict markers, reconcile the intent behind both sides, then `git add` the resolved paths.
      Close out the merge with `git commit --no-edit`, never a bare `git commit`.
      A bare `git commit` opens `$EDITOR` on the pending `MERGE_MSG`; this run has no TTY, so that call would hang or error — exactly the interactive handoff this batch's multi-PR design forbids.
      Never `git merge --abort`, never a blind `-X ours`/`-X theirs`, never an interactive handoff.
      Both branches are `/implement`-authored PRs from the same plan, so no independent human work is ever at risk of being silently overwritten.
    - Only once every parent is merged in, call the dependency guard exactly once, against the now-merged HEAD:
      ```bash
      ~/.claude/skills/implement/scripts/check-pr-dependencies-ready.sh <plan-file> <PR-N> <worktree-path>
      ```
      Same script as the single-parent case, just called *after* the checkout and merges instead of before.
      Its ancestry check (`git merge-base --is-ancestor <parent_branch> HEAD`) cannot pass for the second and later parents until their commits actually land via merge.
      So calling it any earlier would always fail here, even when every parent legitimately is Done.
      Exit 1 surfaces the script's own stderr diagnostic verbatim and stops before dispatching any of this PR's tasks.
      Discard the half-built branch before stopping: `git checkout <first-listed-parent-branch>` then `git branch -D <feat_branch>/pr<N>`.
      A left-over branch would let a later resume's "branch already exists → skip the guard" check adopt it — silently dispatching tasks on a parent that never actually passed.
      Re-running this PR from scratch redoes the same checkout, the same merges, and the same conflict resolution, so nothing is lost by discarding it.
      Exit 2 (usage/parse error) surfaces the same way, discarding the branch identically.
      Exit 0 → dispatch this PR's tasks, same as any other PR.

## Manifest writes (`branches_<slug>.md`)

Every PR — checkout-needed or not — writes its own entry once, at its own batch-end (§9, see `references/batch-end.md`), never in this branch-creation step:

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

Before each PR's loop iteration: the defensive DAG re-check, label resolution, and checkout decision above, all run fresh for that PR.

**Stop predicate, checked after each PR's own §9 completes:** proceed to the next PR only if every one of that PR's tasks reached `[Done]` (none terminal-without-`[Done]`) AND §9.1's repo-green gate passed.
Otherwise stop — do not create the next PR's branch, do not dispatch any of its tasks.
Report the batch as it stands; the remaining PRs in the list are untouched.

This mirrors §5.4's task-level chain-abort but at the PR level.
A task failure inside one PR's batch already chain-aborts that PR's own dependents via the existing mechanism.
This stop predicate is what additionally keeps a failed PR from starting the *next* PR in the list.
