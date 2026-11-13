# Branch switch - step 1b, only when `PR_BRANCH != CUR_BRANCH`

Step 0's persisted branch answer decides:

- `switch`: run `gh pr checkout <n>`, then re-read `git branch --show-current`. Abort with git's error if the checkout fails or the branch still differs.

  Never stash or force past a failed checkout - the change it would overwrite is the user's to move, and the stash stack is shared across worktrees.

- Another worktree holds `PR_BRANCH` (step 0 skipped the question), or no answer: abort:
  > Not on PR branch. Run: `gh pr checkout <n>`, or work in `<worktree path>`, which already holds it.

After a switch, run the post-checkout steps the repo's CLAUDE.md names (rebuilding a library, regenerating a client) before step 7's first commit. A pre-commit hook otherwise checks against artifacts built on the old branch.
