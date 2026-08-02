# Stacked PRs

A stack is a chain of branches, each cut from the previous one, with each PR based on its **parent branch** — so every PR's diff shows only its own delta.

Reach for a stack when a change is too big for one review but later work depends on earlier work.

Keep stacks shallow (2-4 PRs): every extra level adds one more branch to sync on every change below it.

## Build the chain (bottom-up)

```bash
git checkout -b feat-part1 master        # part 1 off the default branch
# ...commit...
git checkout -b feat-part2 feat-part1    # part 2 off part 1
# ...commit...
git push -u origin feat-part1 feat-part2

gh pr create --head feat-part1 --base master ...
gh pr create --head feat-part2 --base feat-part1 ...   # base = PARENT branch
```

Create PRs bottom-up, so each parent PR exists before its child points at it.

Basing a child on the default branch instead of its parent makes reviewers re-review the parent's commits inside the child's diff — the base choice is what makes the stack a stack.

Cross-link the chain in each PR body (e.g. `Stack: #10 ← #11 ← #12 (this PR)`), so reviewers see position and merge order without opening the others.

## Propagate changes by merging parent into child

New commits anywhere in the stack propagate upward with plain merges, parent before child:

```bash
git checkout feat-part2 && git merge feat-part1
git push origin feat-part1 feat-part2
```

Merge, not rebase, is the default here: history stays append-only, so every push is plain and the server rejects any push that would drop someone else's commits.

No branch ref ever moves out from under another worktree or agent.

Merge-commit noise in the branches is the accepted cost; a squash or merge at PR-land time is what reviewers and history actually keep.

A branch with several children (a fork in the stack) is no special case: each child merges the same shared parent.

The shared commits stay shared by ancestry — nothing is ever duplicated or orphaned.

A child that missed a sync round is merely behind; the next merge catches it up. There is no diverged-copy state to repair.

## Merge bottom-up

One PR at a time, starting at the bottom of the stack:

1. Merge the bottom PR into the default branch and delete its head branch.

2. Deleting the head branch makes GitHub retarget that branch's direct children onto the default branch automatically. Verify rather than trust it:

```bash
gh pr view <child> --json baseRefName
# retarget manually if it didn't happen:
gh api -X PATCH repos/{owner}/{repo}/pulls/<child> -F base=master
```

Retarget via REST, not `gh pr edit --base` — `gh pr edit` eagerly queries Projects-classic `projectCards`, the same deprecation hazard step 5 of [`../SKILL.md`](../SKILL.md) documents for `--body-file`.

3. Sync each remaining child with the new base — what it costs depends on how the repo merges:

- **Merge-commit repos**: nothing to do — the parent's commits are now in the default branch, so each child's diff is already clean.
- **Squash-merge repos**: the child's diff shows the parent's original commits until you `git merge master` into it. Both sides carry textually identical changes, so the merge normally auto-resolves.

```bash
git fetch origin
git checkout feat-part2 && git merge origin/master
git push origin feat-part2
```

4. Repeat for the next PR up until the stack is drained.

## Inspect a stack

```bash
gh pr list --base <branch>                       # direct children of <branch>
gh pr view <n> --json baseRefName,headRefName    # one PR's position
gh pr list --state open --json number,headRefName,baseRefName   # map the chain
```

## Appendix: rebase — only for rewriting history

Merge propagation cannot amend, reorder, split, or move commits between PRs. Those are history rewrites, and rewrites need rebase — a case that never arises in a fix-forward-only workflow.

If you do rewrite, propagate one **linear** leg at a time from its topmost branch (Git ≥ 2.38):

```bash
git checkout feat-part2
git rebase master --update-refs        # rewrites feat-part1 in the same pass
git push --force-with-lease --force-if-includes origin feat-part1 feat-part2
```

A fork in the stack is a second leg: rebase it onto the rewritten shared branch with `git rebase --onto <shared> <old-shared-tip> <leg-tip>`.

Never run `--update-refs` a second time from the fork's leg — it replays stale copies of the shared commits.

Always `--force-with-lease --force-if-includes`, never bare `--force` — the lease aborts if the remote moved since your last fetch.

`--force-if-includes` closes the remaining gap: a fetch you never integrated updates the lease's reference point, letting the lease pass while still discarding those commits.

Rebase moves branch refs, so it cannot move a branch checked out in another worktree — restack from one worktree with the stack's other branches not checked out anywhere.

## GitHub's native stacked PRs (public preview) — not this workflow

GitHub's native stacks (preview since 2026-07-30) are rebase-centric: propagation is a server-side cascading rebase that rewrites branches, the docs warn against manually merging stack branches, and stacks must be linear.

All three conflict with this merge-based flow (append-only branches, merged forks, plain pushes) — skip the native feature while that holds, and revisit if it gains merge tolerance.
