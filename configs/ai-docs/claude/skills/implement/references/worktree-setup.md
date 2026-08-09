# Worktree setup — creating the per-unit one, and stocking either kind

Two callers load this, and they share only the second section:

- §1.2's **per-unit** worktree, when the interview answered **yes** to "Run in a git worktree?" — read both sections.

- [`parallel-worktree-execution.md`](parallel-worktree-execution.md)'s **per-task** worktrees — read "What to bring in" only; that file authors its own creation command, which must branch from `BATCH_BASE_SHA`.

A run that answered no and never parallelizes creates no worktree, so it never loads this file.

## Creating the per-unit worktree

Call `EnterWorktree` with no `path` argument.

`settings.json`'s `worktree.baseRef: "head"` makes the worktree branch from current HEAD, so this works from `main` or any feature branch — never from a fixed default branch.

## What to bring in — either kind of worktree

Symlink into the worktree, from the original checkout: the plan and the spec (both untracked, so `git worktree add`'s checkout never carries them). A plan-only run symlinks just the plan.

Use `ln -s <original-checkout-path>/<file> <worktree-path>/<file>` for each, using the original checkout's absolute path.

A copy drifts the moment either worktree's session leaves a Scout note, a status marker, or a `Branch:` clause on the plan.

The symlink keeps both worktrees reading and writing the same file, so an edit made in one is visible in the other immediately.

Also copy (not symlink) any `.env*` files — these are worktree-local by design, never shared state.
