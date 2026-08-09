# Worktree setup — the per-unit worktree §1.2 asked for

One caller loads this: §1.2's **per-unit** worktree, when the interview answered **yes** to "Run in a git worktree?".

A run that answered no never loads this file, however much it parallelizes — the `parallel-worktrees` skill authors its own creation and stocking, so a per-task worktree never comes through here.

## Creating the per-unit worktree

Call `EnterWorktree` with no `path` argument.

`settings.json`'s `worktree.baseRef: "head"` makes the worktree branch from current HEAD, so this works from `main` or any feature branch — never from a fixed default branch.

## What to bring in

Symlink into the worktree, from the original checkout: the plan and the spec (both untracked, so `git worktree add`'s checkout never carries them). A plan-only run symlinks just the plan.

Use `ln -s <original-checkout-path>/<file> <worktree-path>/<file>` for each, using the original checkout's absolute path.

A copy drifts the moment either worktree's session leaves a Scout note, a status marker, or a `Branch:` clause on the plan.

The symlink keeps both worktrees reading and writing the same file, so an edit made in one is visible in the other immediately.

Also copy (not symlink) any `.env*` files — these are worktree-local by design, never shared state.
