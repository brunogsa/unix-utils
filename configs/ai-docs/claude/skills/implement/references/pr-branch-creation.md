# Creating a PR's branch when a checkout is needed

Read this only when `need-git-checkout.sh` printed `yes` for this PR — [`pr-awareness.md`](pr-awareness.md) owns that question and the `no` path, where no branch is ever created.

It covers resolving `<feat_branch>/pr<N>`, the existing-branch check for a branch already present, and the zero-parent / single-parent / diamond branch-creation cases with their dependency guards.

## Resolving the branch name, and adopting one that already exists

**Prints `yes`** → resolve `<feat_branch>/pr<N>` before dispatching:

- `<feat_branch>` = `git branch --show-current`, with any trailing `/pr<digits>` suffix stripped. Stateless — no new persistent store, matching the plan's NFR.
- **Existing-branch check, first**: `git rev-parse --verify --quiet <feat_branch>/pr<N>`.
  A branch can legitimately already exist here: an earlier run halted (§5.5) with this PR's branch already created, and there is no resume path.
  Clearing that halt means a fresh `/implement` re-invocation of this same PR.
  This check is what lets that fresh run find its branch already in place, instead of failing on `checkout -b`.
  Branch already exists → `git checkout <feat_branch>/pr<N>` (plain, no `-b`) and skip every step below.
  The guard already ran, and passed, the first time this branch was created — re-running it on an adopted branch is redundant, not merely safe-to-repeat.
  This guarantee holds for the diamond case too: its guard already ran by branch-creation time, in the diamond-specific position after the checkout and merges.
  That run validated ancestry against every parent, not just one, so an adopted diamond branch inherits the same completed guarantee.
## Creating the branch — zero, one, or many parents

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
    The stop predicate — [`pr-awareness.md`](pr-awareness.md)'s "The per-PR loop and fail-fast" — starts the next PR only once every task of the previous one reached `[Done]` and its repo-green gate passed.
    This means the parent PR's own full batch already completed before this PR's pre-flight ever started.
    That completed batch includes the parent's own §9 batch-end, where it wrote its own entry (see "Manifest writes" in [`pr-awareness.md`](pr-awareness.md) — that step is the only writer of a PR's manifest entry).
    So this step writes nothing itself; only the parent's own batch-end write ever populates this entry, and it always got there first.
    Exit 0 → `git checkout -b <feat_branch>/pr<N>` with no explicit base ref, i.e. from current HEAD.
    Correct because a DAG-root PR's commits land directly on the pre-existing branch, so by the time a single dependent PR runs, HEAD already sits at its parent's tip.
    That is the `no`-checkout case, owned by [`pr-awareness.md`](pr-awareness.md) — a DAG root needs no branch of its own, so nothing was ever created for it to diverge onto.
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
      A left-over branch would let a later re-invocation's existing-branch check adopt it — silently dispatching tasks on a parent that never actually passed.
      Re-running this PR from scratch redoes the same checkout, the same merges, and the same conflict resolution, so nothing is lost by discarding it.
      Exit 2 (usage/parse error) surfaces the same way, discarding the branch identically.
      Exit 0 → dispatch this PR's tasks, same as any other PR.
