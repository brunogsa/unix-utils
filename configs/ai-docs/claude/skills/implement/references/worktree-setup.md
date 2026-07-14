# Worktree setup (§1.3 detail)

Load this only when §1.2's interview answered **yes** to "Run in a git worktree?". A no-worktree run never needs it.

Call `EnterWorktree` with no `path` argument.

`settings.json`'s `worktree.baseRef: "head"` makes the worktree branch from current HEAD, so this works from `main` or any feature branch — never from a fixed default branch.

Then copy into the worktree, from the original checkout: `plan_<slug>.md`, `spec_<slug>.md` (both untracked, so `git worktree add`'s checkout never carries them), and any `.env*` files.
