# Stacked PRs

A stack is a chain of branches, each cut from the previous one, with each PR based on its **parent branch** — so every PR's diff shows only its own delta.

Reach for a stack when a change is too big for one review but later work depends on earlier work.

Keep stacks shallow (2-4 PRs): every extra level multiplies the restack cost of any change below it.

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

## Amend mid-stack: restack upward

A new commit, amend, or rebase in a lower branch orphans every branch above it. Propagate in one rebase (Git ≥ 2.38):

```bash
git checkout feat-part2                # topmost branch of the stack
git rebase master --update-refs        # rewrites feat-part1 in the same pass
git push --force-with-lease origin feat-part1 feat-part2
```

Always `--force-with-lease`, never bare `--force` — it aborts if the remote moved, e.g. a reviewer pushed a fixup to the branch since your last fetch.

## Merge bottom-up

One PR at a time, starting at the bottom of the stack:

1. Merge the bottom PR into the default branch and delete its head branch.

2. Deleting the head branch makes GitHub retarget that branch's direct children onto the default branch automatically. Verify rather than trust it:

```bash
gh pr view <child> --json baseRefName
# retarget manually if it didn't happen:
gh api -X PATCH repos/{owner}/{repo}/pulls/<child> -F base=master
```

Retarget via REST, not `gh pr edit --base` — `gh pr edit` eagerly queries Projects-classic `projectCards`, the same deprecation hazard as `--body-file` (see the fallback section in [`../SKILL.md`](../SKILL.md)).

3. A squash or rebase merge rewrites the parent's commits, so the child still carries the originals and shows them as its own diff. Rebase the child past them:

```bash
git fetch origin
git rebase --onto origin/master feat-part1 feat-part2
git push --force-with-lease origin feat-part2
```

With plain merge commits, `git merge origin/master` into the child works instead — no history was rewritten.

4. Repeat for the next PR up until the stack is drained.

## Inspect a stack

```bash
gh pr list --base <branch>                       # direct children of <branch>
gh pr view <n> --json baseRefName,headRefName    # one PR's position
gh pr list --state open --json number,headRefName,baseRefName   # map the chain
```
