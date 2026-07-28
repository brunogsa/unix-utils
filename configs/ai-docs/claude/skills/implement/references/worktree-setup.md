# Worktree setup (detail for /implement's pre-flight worktree-setup step)

Load this only when §1.2's interview answered **yes** to "Run in a git worktree?". A no-worktree run never needs it.

Call `EnterWorktree` with no `path` argument.

`settings.json`'s `worktree.baseRef: "head"` makes the worktree branch from current HEAD, so this works from `main` or any feature branch — never from a fixed default branch.

Then symlink into the worktree, from the original checkout: the plan and the spec (both untracked, so `git worktree add`'s checkout never carries them). A plan-only run symlinks just the plan.

Use `ln -s <original-checkout-path>/<file> <worktree-path>/<file>` for each, using the original checkout's absolute path.

A copy drifts the moment either worktree's session leaves a Scout note, a status marker, or a `Branch:` clause on the plan.

The symlink keeps both worktrees reading and writing the same file, so an edit made in one is visible in the other immediately.

Also copy (not symlink) any `.env*` files — these are worktree-local by design, never shared state.
