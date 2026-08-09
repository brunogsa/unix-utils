# Parallel task execution in per-task worktrees

Load this when §5.4 hands back an eligible set of more than one task. A single-task set needs nothing here — dispatch it in the main tree as usual.

Parallelism is derived, never asked: the plan's own dependency graph already says which tasks are independent, so a run gets it for free and the §1.2 interview stays the length it is.

## Eligibility — three predicates, all required

A set of tasks may run concurrently only when every pair in it clears all three:

- **DAG-satisfied** — every id in `depends_on` is already `done`. `implement-loop-state.sh --eligible-set` computes this and nothing else.

- **File-disjoint from each other** — intersect the tasks' **Files (logical order)** lists from the plan.
`depends_on` encodes *ordering*, not shared files, so two undeclared-independent tasks can still both edit one file and conflict on merge-back.

- **File-disjoint from the main tree's uncommitted paths** — `git status --porcelain` names them.
A fast-forward merge refuses to overwrite a locally-modified file, so a task touching one would halt the merge-back it was supposed to make cheap.

On any overlap, keep the lowest id in the parallel set and leave the rest pending;
they become eligible again once the conflicting task lands. Never split the difference by merging partial work.

Cap the set at 4. Beyond that the worktrees contend for the same disk and test runners, and the wall-clock curve flattens while the merge-back queue grows.

## Naming and creating each worktree

One worktree and one branch per task, both carrying the task id so nothing collides inside a unit:

```bash
git worktree add -b "implement/<slug>/t<id>" "/tmp/implement-wt/<slug>/t<id>" "<BATCH_BASE_SHA>"
```

Branching from `BATCH_BASE_SHA` rather than `HEAD` keeps every sibling on one common base, which is what makes the merge-back order below deterministic.

Then, from the original checkout, symlink the plan and the spec into the worktree and copy any `.env*` files — the same mechanics and the same reasons as [`worktree-setup.md`](worktree-setup.md).

§6 gives the orchestrator sole ownership of plan status edits, so concurrent-writer warnings do not apply — N worktrees are N readers of one file.

A worktree checks out `BATCH_BASE_SHA` clean, so it carries none of the main tree's uncommitted changes.
A task whose acceptance criteria constrain its own diff gets that for free, with no hunk staging.

## Dispatch, and the write that prevents a double dispatch

Before spawning anything, set that task's `status` to `"in_progress"` in the state file and record its `branch` and `worktree_path`.

Write it *before* the spawn, never after.
`implement-loop-state.sh` excludes `in_progress` from the eligible set, and that exclusion is the only thing stopping a later turn from dispatching the same task into a second worktree.

Then dispatch per §4, with two additions to §4.1's push list: the worktree path the subagent must work in, and its branch name.

Spawn the whole set in one message so they run concurrently — one message per agent serializes the fan-out and gives back the wall-clock the worktrees just bought.

## Merge-back — rebase in the worktree, fast-forward in the main tree

Merge back **only after every task in the set has reported and been accepted per §5.1**, one at a time, in ascending task-id order.

Ascending id is what makes the resulting history identical to the history a sequential run would have produced — the same commits, in the same order, on one line.

```bash
git -C "/tmp/implement-wt/<slug>/t<id>" rebase "<base-branch>"
git -C "<repo-root>" merge --ff-only "implement/<slug>/t<id>"
```

The rebase runs inside the worktree because that is where the branch is checked out; git refuses to rebase a branch checked out in another worktree.

Rebase every branch, including the first. The first is already a fast-forward, so its rebase is a no-op —
but a uniform two-step has no special case to get wrong on a later run.

A rebase conflict means the file-disjointness predicate was wrong for that pair.
Run `git rebase --abort`, leave the worktree and branch untouched, halt per §5.5 naming the branch — preserving the work for human resolution rather than guessing.

## Cleanup, and the exception it carves

Once a branch is merged, remove its worktree and delete its branch:

```bash
git worktree remove "/tmp/implement-wt/<slug>/t<id>"
git branch -d "implement/<slug>/t<id>"
```

This is a deliberate, narrow exception to SKILL.md's "never merges or deletes a worktree on its own".
That rule protects the **per-unit** worktree, which exists for a human to review and therefore must outlive the run.

A per-task worktree is the opposite: an implementation detail whose commits are already on the branch by the time it is removed, and which no human was ever meant to open.
`git branch -d` refuses an unmerged branch, so the delete cannot outrun the merge.

Leave the per-unit worktree alone regardless — the two live at different levels and this exception never reaches it.

## What parallelism does not change

Everything below stays exactly as the sequential flow defines it:

- The orchestrator remains the only role that creates a branch or a worktree, and the only role that spawns subagents. A subagent never checks anything out.

- §5.1's acceptance check is per report, unchanged: every reported SHA must resolve. Run it as each report lands rather than batching, so a failure re-dispatches while its siblings are still working.

- A failure or block inside a parallel set is that task's alone. Its siblings finish and merge normally; §5.2 and §5.3 handle it exactly as they would in a sequential run.

- `BATCH_BASE_SHA` is captured once per unit, in §3.2, and never per task.

One thing does change meaning — a subagent's `git log <BATCH_BASE_SHA>..HEAD` goes short, since a sibling's commits sit on its own branch.
`~/.claude/agents/tdd-coder.md` authors why that is expected rather than a defect; edit it there, not here.
