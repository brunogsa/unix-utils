# Creating a PR's branch when a checkout is needed

Read this only when `need-git-checkout.sh` printed `yes` for this PR — [`pr-awareness.md`](pr-awareness.md) owns that question and the `no` path, where no branch is ever created.

It covers resolving `<feat_branch>/pr<N>`, the existing-branch check for a branch already present, and the zero-parent / single-parent / diamond branch-creation cases with their dependency guards.

## Resolving the branch name, and adopting one that already exists

**Prints `yes`** → resolve `<feat_branch>/pr<N>` before dispatching:

- `<feat_branch>` = `git branch --show-current`, stripped twice in this order: any trailing `-t<digits>` suffix, then any trailing `/pr<digits>` suffix. Stateless — no new persistent store, matching the plan's NFR.
  The `-t<digits>` strip is what makes a later PR resolve on a stacked run ([`stacked-by-task.md`](stacked-by-task.md)).
  HEAD then sits on the previous PR's topmost *layer* branch, `<feat_branch>/pr<N>-t<M>`, which stripping `/pr<digits>` alone would leave whole.
  - **Collision guard**: before using `<feat_branch>` as a prefix, check `git rev-parse --verify --quiet <feat_branch>`.
    Git refs nest path-hierarchically: a bare branch named exactly `<feat_branch>` blocks creating `<feat_branch>/pr<N>` because `refs/heads/<feat_branch>` cannot coexist with `refs/heads/<feat_branch>/pr<N>`.
    A bare branch can be left over from a first unit's stacked-by-task layering, which reuses the pre-existing branch verbatim for its first task rather than creating a new one.
    If found, rename it (`git branch -m <feat_branch> <feat_branch>-t1`, never delete) before branching.
    Safe whenever it was never pushed under that exact name (check `git ls-remote origin refs/heads/<feat_branch>` first) and its commits already live on in a pushed descendant layer branch.
- **Existing-branch check, first**: `git rev-parse --verify --quiet <feat_branch>/pr<N>`.
  A branch can legitimately already exist here: an earlier run halted (§5.5) with this PR's branch already created, and there is no resume path.
  Clearing that halt means a fresh `/implement` re-invocation of this same PR.
  This check is what lets that fresh run find its branch already in place, instead of failing on `checkout -b`.
  Branch already exists → `git checkout <feat_branch>/pr<N>` (plain, no `-b`) and skip every step below.
  The guard already ran, and passed, the first time this branch was created — re-running it on an adopted branch is redundant, not merely safe-to-repeat.
  This guarantee holds for the diamond case too: its guard already ran by branch-creation time, in the diamond-specific position after the checkout and merges.
  That run validated ancestry against every parent, not just one, so an adopted diamond branch inherits the same completed guarantee.
## Creating the branch — zero, one, or many parents

- Branch doesn't exist yet (first time through) → count `PR-N`'s parents from its PR Breakdown entry's `Depends on:` field (already open from §1.1):
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
    The guard's own `branch_for_pr()` hard-requires the parent's PR Breakdown entry to already carry a `Branch:` field — no fallback ancestry source, absence is always a hard block.
    That precondition always holds here.

    The stop predicate ([`pr-awareness.md`](pr-awareness.md)'s "The per-PR loop and fail-fast") starts this PR only after the parent's whole batch completed.
    That batch's §8 push is the sole writer of the parent's `Branch:` clause ([`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md)).
    So this step writes nothing itself; the parent's own write always got there first.
    Exit 0 → `git checkout -b <feat_branch>/pr<N>` with no explicit base ref, i.e. from current HEAD.
    Correct because a DAG root needs no branch of its own — the `no`-checkout case owned by [`pr-awareness.md`](pr-awareness.md).
    Its commits land on the pre-existing branch, so HEAD already sits at the parent's tip when a single dependent PR runs.
  - **Two or more parents** (diamond dependency) → resolve each parent's branch name from its own PR Breakdown entry first, in the order listed in `Depends on:`.
    Read it from column 4 of `parse-pr-breakdown.sh <plan-file>`, the field `check-pr-dependencies-ready.sh`'s own `branch_for_pr()` uses.
    Every parent's clause already exists here, by the same reasoning as the single-parent case above.
    - `git checkout -b <feat_branch>/pr<N> <first-listed-parent-branch>` — explicit base ref, same as the "Zero parents" bullet, never bare HEAD.
    - Then, for each remaining parent in listed order: `git merge <parent-branch> -m "Merge <parent-label> into <PR-N>"`.
      A conflict here is resolved by `/implement` itself, never surfaced to the user.
      Read the conflict markers, reconcile the intent behind both sides, then `git add` the resolved paths.
      Close out the merge with `git commit --no-edit`, never a bare `git commit`.
      A bare `git commit` opens `$EDITOR` on the pending `MERGE_MSG`, and this run has no TTY — it would hang or error.
      Never `git merge --abort`, never a blind `-X ours`/`-X theirs`, never an interactive handoff.
      Both branches are `/implement`-authored PRs from the same plan, so no independent human work is ever at risk of being silently overwritten.
    - Only once every parent is merged in, call the dependency guard exactly once, against the now-merged HEAD:
      ```bash
      ~/.claude/skills/implement/scripts/check-pr-dependencies-ready.sh <plan-file> <PR-N> <worktree-path>
      ```
      Same script as the single-parent case, just called *after* the checkout and merges instead of before.
      Its ancestry check (`git merge-base --is-ancestor <parent_branch> HEAD`) cannot pass for the second and later parents until their commits land via merge.
      Calling it earlier would always fail here, even when every parent legitimately is Done.
      Exit 1 surfaces the script's own stderr diagnostic verbatim and stops before dispatching any of this PR's tasks.
      Discard the half-built branch before stopping: `git checkout <first-listed-parent-branch>` then `git branch -D <feat_branch>/pr<N>`.
      A left-over branch would let a later re-invocation's existing-branch check adopt it — silently dispatching tasks on a parent that never actually passed.
      Nothing is lost: a re-run redoes the same checkout, the same merges, and the same conflict resolution.
      Exit 2 (usage/parse error) surfaces the same way, discarding the branch identically.
      Exit 0 → dispatch this PR's tasks, same as any other PR.
