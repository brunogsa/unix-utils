# Step 5 - Apply post-push changes

Three entry points: a change the user asks for after the push, step 4 finding the branch already had an open PR, or a later change that alters the PR's scope or a decision its body states. In every case:

- **Pull GitHub's current body into the file first** -- `gh pr view <n> --json body`, so a hand-edit made there is not overwritten by the next push.
  - Skip this on step 4's already-exists entry: the `.final.md` just composed IS the replacement, so pulling would overwrite it with the body it replaces.

- **Load the `doc-standards` skill before editing** -- this is the only prose the main session writes, so density cap, BLUF ordering, and collapse rules apply.
  - Steps 1-4 never need it: `pr-writer` and `pr-finalizer` each load it and own their own gates; step 4 only checks the artifact exists.

- **Edit `pr_<slug>_pr<N>.final.md` only** -- the `.ideal.md` is deliberately left to drift once the PR exists.
  - Re-deriving the final body from it would discard the user's own edits, and nobody reads the ideal description after the push.

- **Confirm with the user before writing to GitHub** -- the local edit is cheap to revise; the pushed body notifies reviewers.
- **Updating an existing PR's body: never use `gh pr edit --body-file`** - take the REST command and its mandatory read-back from the `gh-cli-usage` skill, which authors that hazard.
  - Restating the command would be a third copy that drifts the next time GitHub changes the endpoint.

- **A scope or decision change updates the PR body and the linked Linear issue in the same step** -- find the issue through [`ticket-id.md`](ticket-id.md).
  - Confirm the issue's edit with the user like the body's.
  - Reviewers and the team read the PR and the ticket, never the session notes; twice the stale one had to be requested.
  - `implement` §8.4 already refreshes the description at batch end, so this entry covers a change made outside that refresh.
