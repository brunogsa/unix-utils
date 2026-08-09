---
name: parallel-worktrees
description: "Run independent items concurrently, one git worktree each, then merge them back so history reads as if they ran one at a time. Trigger: an orchestrator holds 2+ dispatchable items and wants them fanned out at once — implement's parallel wave, or any fan-out whose agents would otherwise share one index."
disable-model-invocation: false
---

# Parallel execution in per-item worktrees

A worktree exists only to keep concurrent siblings off one index, so nothing else ever earns one.
A single-item set dispatches in the main tree as usual, and a sequential run creates none at all.

Parallelism is derived, never asked: the caller's own dependency data already says which items are independent, so a run gets it for free and no interview grows a question for it.

## What the caller supplies

Four inputs, and nothing else:

- **The candidate set** — the ids of items whose dependencies are already satisfied. Computing that is the caller's job; this skill never reads a dependency graph.

- **One file list per candidate** — the paths that item is expected to touch. The two predicates below intersect these.
- **A base commit** — the SHA every worktree branches from, captured once for the whole set, never per item.
- **A slug** — any string unique to the run. It names the branches and the worktree paths, so two concurrent runs never collide.

Everything below is this skill's own, not the caller's to pass in.
Each extra input would be one more precondition a new caller has to satisfy before it can reuse any of this.

## Eligibility — two file predicates the caller has not checked

Dependency satisfaction encodes *ordering*, not *shared files*, so two items with no declared dependency between them can still edit one file and conflict on merge-back.

Both predicates run here, over the candidate set:

- **File-disjoint from each other** — intersect the candidates' file lists pairwise.

- **File-disjoint from the main tree's uncommitted paths** — `git status --porcelain` names them.
A fast-forward merge refuses to overwrite a locally-modified file, so an item touching one would halt the merge-back it was supposed to make cheap.

On any overlap, keep the lowest id and leave the rest for a later round; they become eligible again once the conflicting item lands.

Cap the set at 4. Beyond that the worktrees contend for the same disk and test runners, and the wall-clock curve flattens while the merge-back queue grows.

A set that falls below 2 after all this is not a wave: hand it back to the caller to dispatch in the main tree, and create no worktree at all.

## Naming and creating each worktree

One worktree and one branch per item, both carrying the item id so nothing collides inside a run:

```bash
git worktree add -b "parallel/<slug>/t<id>" "/tmp/parallel-wt/<slug>/t<id>" "<base-sha>"
```

Branching from the base commit rather than `HEAD` keeps every sibling on one common base, which is what makes the merge-back order below deterministic.

A worktree checks out that commit clean, so each item's diff is its own — no hunk staging, whatever the main tree has uncommitted.

### What to bring in

A clean checkout carries tracked files only, so every untracked artifact the dispatched agent must read has to be brought in by hand — a plan, a spec, a shared notes file:

```bash
ln -s <original-checkout-path>/<file> <worktree-path>/<file>
```

Symlink rather than copy: a copy drifts the moment either side appends to the file, where the symlink keeps every worktree reading and writing the same one.

Copy — never symlink — any `.env*` file. Those are worktree-local by design, never shared state.

## The write that prevents a double dispatch

Before spawning anything, mark each item in-flight in whatever ledger the caller's eligibility computation reads, recording its branch and worktree path alongside.

Write it *before* the spawn, never after. That in-flight mark is the only thing stopping a later round from dispatching the same item into a second worktree.

A caller with no such ledger has no guard to write: it dispatches its wave once and runs no top-up round.

## Dispatch — one message for the whole set

Spawn every agent in the set in a single message, so they run concurrently.
One message per agent serializes the fan-out and gives back the wall-clock the worktrees just bought.

Each prompt carries two things beyond whatever the caller already pushes per item: the worktree path the agent must work in, and its branch name.

## Asking for a top-up while the wave runs

A caller re-querying its eligibility computation mid-wave must use a query that accounts for in-flight items.
One that assumes nothing is in flight reads a wave-in-progress as a stalled run and stops to wait for a human.

Anything such a query returns must clear both file predicates against the **live** siblings' files too, not just the finished ones.

## Merge-back — rebase in the worktree, fast-forward in the main tree

Merge back only after every item in the set has reported and been accepted by the caller's own acceptance check, one at a time, in ascending id order.

Ascending id makes the resulting history identical to a sequential run's — the same commits, in the same order, on one line.

```bash
git -C "/tmp/parallel-wt/<slug>/t<id>" rebase "<base-branch>"
git -C "<repo-root>" merge --ff-only "parallel/<slug>/t<id>"
```

The rebase runs inside the worktree: git refuses to rebase a branch checked out elsewhere.

Rebase every branch, including the first, where it is a no-op — a uniform two-step has no special case to get wrong.

A rebase conflict means the file-disjointness predicate was wrong for that pair.
Run `git rebase --abort` and leave that worktree and branch untouched, then halt down the caller's own halt path, naming the branch.
Preserving the work is what lets a human resolve it, where guessing at the conflict would bury what actually collided.

## Cleanup, and the exception it carves

Remove each worktree and delete its branch as soon as that branch merges — per merge, never batched to the end of the wave:

```bash
git worktree remove "/tmp/parallel-wt/<slug>/t<id>"
git branch -d "parallel/<slug>/t<id>"
```

`git branch -d` refuses an unmerged branch, so the delete cannot outrun the merge.

Cleanup stops entirely on the way out of a halt or a rebase conflict — those branches hold unmerged work, so every worktree stays and the halt message names each one.

A worktree the caller made for its own reasons is never this skill's to remove: it may exist for a human to review, so it has to outlive the run.
The ones here are the opposite — per-item implementation detail, commits already on the branch, and no human was meant to open one.

## What parallelism does not change

- The orchestrator stays the only role that creates a branch or a worktree, and the only role that spawns agents. A dispatched agent never checks anything out.

- The caller's acceptance check stays per report. Run it as each report lands, so a failure re-dispatches — into its own worktree — while its siblings still work.

- A failure or block inside a set is that item's alone. Its siblings finish and merge normally, and the caller's retry and chain-abort rules apply exactly as in a sequential run.

One thing does change meaning: an agent reading `git log <base-sha>..HEAD` for prior context finds it short or empty, since a sibling's commits sit on that sibling's own branch.
Tell the agent so up front, or it chases the gap as a defect — `~/.claude/agents/tdd-coder.md` authors that for the agent this skill's first caller dispatches.
