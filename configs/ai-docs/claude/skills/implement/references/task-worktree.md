# Task Worktree Workflow

When working in **worktree isolation mode**, each plan task runs in its own git worktree branched off the current feature branch. The user creates feature worktrees themselves; this workflow covers only task branches inside an existing feature worktree.

The safety guarantee is simple: **ensure the task branch is fully committed and merged back into the feature branch before moving on.** No push to origin needed — the merge IS the safety net. Worktree and branch cleanup happens in batch later.

## Naming convention

```
<parent-dir>/<repo>_<feature>_<task>
```

Example — feature worktree at `~/workspace/integrator-dbma-840`:

| Feature | Task | Branch | Path |
|---|---|---|---|
| `dbma-840` | `task-5` | `feat/dbma-840-task-5` | `~/workspace/integrator-dbma-840_dbma-840_task-5` |

## CREATE — spin up a task worktree

Run from inside the feature worktree:

```bash
# 1. Confirm you're on the feature branch
git rev-parse --abbrev-ref HEAD

# 2. Compute the path
FEATURE=dbma-840
TASK=task-5
MAIN=$(git worktree list --porcelain | awk '/^worktree / {print $2; exit}')
WPATH="$(dirname $MAIN)/$(basename $MAIN)_${FEATURE}_${TASK}"
BRANCH="feat/$FEATURE-$TASK"

# 3. Create worktree + branch off current HEAD
git worktree add -b "$BRANCH" "$WPATH"

# 4. Move into it
cd "$WPATH"
```

## MERGE-BACK — bring task changes into the feature branch

Run from **outside** the task worktree (e.g., from the feature worktree):

```bash
# 1. Verify task worktree is clean — no uncommitted or untracked changes
git -C "$WPATH" status

# 2. Confirm you're on the feature branch
git rev-parse --abbrev-ref HEAD    # should be feat/<feature>

# 3. Merge task branch (--no-ff preserves the task boundary in history)
git merge --no-ff "$BRANCH" -m "Merge $BRANCH into feat/$FEATURE"
```

**That's it.** The worktree and branch are left intact — clean up in batch when convenient (see below).

If step 3 produces **merge conflicts**: resolve them in the feature worktree, complete the merge, then continue. The task worktree remains available for reference.

## Batch cleanup (when ready)

```bash
# List all worktrees to see what needs cleanup
git worktree list

# Remove a task worktree (only after its branch is merged)
git worktree remove "$WPATH"

# Delete the local task branch (safe-delete: fails if not fully merged)
git branch -d "$BRANCH"
```

## Integration with /implement lifecycle

When worktree isolation is active for a task:

- **Pre-flight (after confirming base branch):** create the task worktree and `cd` into it. All subsequent work happens there.
- **Verify step (before [Done] handshake):** run `git -C "$WPATH" status` — must be clean (all committed, nothing untracked).
- **[Done] handshake:** run the MERGE-BACK from the feature worktree. The merge commit lands in the feature branch history as the canonical record of the task.
- **plan.md** lives in the feature worktree, not the task worktree. Status edits happen there.
- **Worktree + branch are not deleted** at `[Done]` — they survive for reference until the user does batch cleanup.
