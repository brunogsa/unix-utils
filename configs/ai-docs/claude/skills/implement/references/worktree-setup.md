# Worktree setup (detail for /implement's pre-flight worktree-setup step)

Load this only when §1.2's interview answered **yes** to "Run in a git worktree?". A no-worktree run never needs it.

Call `EnterWorktree` with no `path` argument.

`settings.json`'s `worktree.baseRef: "head"` makes the worktree branch from current HEAD, so this works from `main` or any feature branch — never from a fixed default branch.

Then symlink into the worktree, from the original checkout: `plan_<slug>.md`, `spec_<slug>.md`, and `branches_<slug>.md` (all untracked, so `git worktree add`'s checkout never carries them).

Use `ln -s <original-checkout-path>/<file> <worktree-path>/<file>` for each, using the original checkout's absolute path.

A copy drifts the moment either worktree's session leaves a Scout note or a plan edit.

The symlink keeps both worktrees reading and writing the same file, so an edit made in one is visible in the other immediately.

`branches_<slug>.md` may not exist yet in the original checkout — it's created lazily on a PR's first batch-end.

Symlink it anyway: a dangling symlink resolves the moment either worktree's manifest-append step first writes through it, landing the file at the original checkout's path.

Also copy (not symlink) any `.env*` files — these are worktree-local by design, never shared state.
