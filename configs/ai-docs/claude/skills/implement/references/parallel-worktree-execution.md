# Parallel task execution in per-task worktrees

Load this when §5.4 hands back an eligible set of more than one task.

A worktree exists only to keep concurrent siblings off one index, so nothing else ever earns one.
A single-task set dispatches in the main tree as usual, and a sequential run creates none at all.

Parallelism is derived, never asked: the plan's own dependency graph already says which tasks are independent, so a run gets it for free and the §1.2 interview stays the length it is.

## Eligibility — three predicates, all required

A set of tasks may run concurrently only when every pair in it clears all three:

- **DAG-satisfied** — every id in `depends_on` is already `done`. `implement-loop-state.sh --eligible-set` computes this and nothing else.

- **File-disjoint from each other** — intersect the tasks' **Files (logical order)** lists from the plan.
`depends_on` encodes *ordering*, not shared files, so two undeclared-independent tasks can still both edit one file and conflict on merge-back.

- **File-disjoint from the main tree's uncommitted paths** — `git status --porcelain` names them.
A fast-forward merge refuses to overwrite a locally-modified file, so a task touching one would halt the merge-back it was supposed to make cheap.

On any overlap, keep the lowest id in the parallel set and leave the rest pending;
they become eligible again once the conflicting task lands.

Cap the set at 4. Beyond that the worktrees contend for the same disk and test runners, and the wall-clock curve flattens while the merge-back queue grows.

## Naming and creating each worktree

One worktree and one branch per task, both carrying the task id so nothing collides inside a unit:

```bash
git worktree add -b "implement/<slug>/t<id>" "/tmp/implement-wt/<slug>/t<id>" "<BATCH_BASE_SHA>"
```

Branching from `BATCH_BASE_SHA` rather than `HEAD` keeps every sibling on one common base, which is what makes the merge-back order below deterministic.

Then bring the plan, the spec, and any `.env*` files in, per [`worktree-setup.md`](worktree-setup.md).

§6 makes the orchestrator the only writer of plan status, so N worktrees are N readers of one file.

A worktree checks out `BATCH_BASE_SHA` clean, so a task's diff is its own — no hunk staging, whatever the main tree has uncommitted.

## Dispatch, and the write that prevents a double dispatch

Before spawning anything, set that task's `status` to `"in_progress"` in the state file and record its `branch` and `worktree_path`.

Write it *before* the spawn, never after.
`implement-loop-state.sh` excludes `in_progress` from the eligible set, and that exclusion is the only thing stopping a later turn from dispatching the same task into a second worktree.

Then dispatch per §4, with two additions to §4.1's push list: the worktree path the subagent must work in, and its branch name.

Spawn the whole set in one message so they run concurrently — one message per agent serializes the fan-out and gives back the wall-clock the worktrees just bought.

## While the wave runs, ask `--eligible-set` — never the plain verdict

The plain verdict assumes nothing is in flight; mid-wave it answers `halted`, which stops the run to wait for a human. Ask it once `in_progress` reaches 0.

A non-empty `tasks` is a top-up a landed sibling freed — clear the three predicates against the **live** siblings' files too, not just the finished ones.

`exhausted: true` means the batch budget is spent: dispatch nothing more, and let the live siblings finish.

## Merge-back — rebase in the worktree, fast-forward in the main tree

Merge back **only after every task in the set has reported and been accepted per §5.1**, one at a time, in ascending task-id order.

Ascending id makes the resulting history identical to a sequential run's — the same commits, in the same order, on one line.

```bash
git -C "/tmp/implement-wt/<slug>/t<id>" rebase "<base-branch>"
git -C "<repo-root>" merge --ff-only "implement/<slug>/t<id>"
```

The rebase runs inside the worktree: git refuses to rebase a branch checked out elsewhere.

Rebase every branch, including the first, where it is a no-op — a uniform two-step has no special case to get wrong.

A rebase conflict means the file-disjointness predicate was wrong for that pair.
Run `git rebase --abort`, leave the worktree and branch untouched, halt per §5.5 naming the branch — preserving the work for human resolution rather than guessing.

## Cleanup, and the exception it carves

The orchestrator removes each worktree and deletes its branch as soon as that branch merges — per merge, never batched to the end of the wave:

```bash
git worktree remove "/tmp/implement-wt/<slug>/t<id>"
git branch -d "implement/<slug>/t<id>"
```

SKILL.md's **never merges or deletes §1.2's worktree** still holds: that one exists for a human to review, so it must outlive the run.

A per-task worktree is the opposite: an implementation detail whose commits are on the branch before it is removed, and no human was meant to open it.
`git branch -d` refuses an unmerged branch, so the delete cannot outrun the merge.

Cleanup stops entirely on the way out of a halt or a rebase conflict — those branches hold unmerged work, so every worktree stays, and the halt message names each one.

Leave the per-unit worktree alone regardless — the two live at different levels and this exception never reaches it.

## What parallelism does not change

Everything below stays exactly as the sequential flow defines it:

- The orchestrator remains the only role that creates a branch or a worktree, and the only role that spawns subagents. A subagent never checks anything out.

- §5.1's acceptance check is per report, unchanged. Run it as each report lands, so a failure re-dispatches while its siblings still work.

- A failure or block inside a parallel set is that task's alone. Its siblings finish and merge normally; §5.2 and §5.3 handle it exactly as they would in a sequential run.

- `BATCH_BASE_SHA` is captured once per unit, in §3.2, and never per task.

One thing does change meaning — a subagent's `git log <BATCH_BASE_SHA>..HEAD` goes short, since a sibling's commits sit on its own branch.
`~/.claude/agents/tdd-coder.md` authors why that is expected rather than a defect; edit it there, not here.
