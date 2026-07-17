# Step 3: Fetch, filter, cluster, rank, propose

Consumed only by the step-3 subagent dispatched from `SKILL.md` — main never reads this file. Execute the subsections below (3a-3e) for the PR and filters given in your dispatch prompt.

### 3a. Inline review comments via GraphQL (need `isResolved`)

Query lives in `references/queries.graphql`. Invoke via:

```bash
gh api graphql -f query='...' -F owner="$OWNER" -F repo="$REPO" -F n=<n>
```

Keep only threads where `isResolved == false`. Flatten the comments inside.

### 3b. Top-level conversation comments via REST (no resolved concept)

```bash
gh api repos/$OWNER_REPO/issues/<n>/comments
```

These are always "open" by GitHub's model. Include all of them.

### 3c. Review summary bodies via REST

```bash
gh api repos/$OWNER_REPO/pulls/<n>/reviews
```

Include each review's `body` (when non-empty) plus its `state` (`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`) — `state` feeds the rank rule below.

### 3d. Apply user filters

`by <logins>` matches **ownership**, not participation. The unit of ownership differs by source — see the ownership table in SKILL.md's Usage section (`../SKILL.md#usage`). Concretely:

- **inline threads** — keep the thread iff `comments[0].author.login ∈ {logins}`. When kept, **include all comments in the thread**.
  - Replies provide context for addressing the thread, even if the user didn't write them.
- **top-level comments** — keep where `user.login ∈ {logins}`.
- **review-summary bodies** — keep where the review's `user.login ∈ {logins}`.

`in <paths>` — keep where `path` starts-with any of the paths (folder match) or equals it (file match).
- Top-level/review-summary comments have no `path` and are kept only if **no** `in` filter was given.

If the result is empty after filtering, report and stop — don't cluster an empty set.

See `references/reply-patterns.md` (jq ownership query) for the inline-thread `by` filter pattern.

### 3e. Cluster, rank, propose

Per comment field, once fetched and filtered: id, author, body, path, line, diffHunk, url, source (`"inline"`/`"top-level"`/`"review-summary"`), state (review-summary only), is_self.

- Semantic-cluster: group comments addressing one logical change. Same-file
  is a hint, not a rule; cross-file comments can share a cluster.
- Rank: severity (CHANGES_REQUESTED > general > nit) → cluster size → file
  recency (most recent first).
- Default action per cluster:
  - `answer` if every comment is a question (ends in "?", or starts with
    why/what/how/when/could/would/should/can/is/are/does, no actionable
    request).
  - `apply` otherwise.
  - Never default to `drop` — that's always an explicit user choice.
- Per cluster, propose a one-line drop reason — honest and specific (not
  "out of scope").

Emit the proposal block exactly per the format in SKILL.md's "Output: proposal block format" section (`../SKILL.md#output-proposal-block-format`).
