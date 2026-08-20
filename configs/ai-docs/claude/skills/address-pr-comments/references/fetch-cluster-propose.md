# Fetching, filtering, clustering, ranking, and proposing PR-comment replies

Consumed only by the subagent [`address-pr-comments/SKILL.md`](../SKILL.md) dispatches for this work — main never reads this file. Execute the subsections below in order, for the PR and filters given in your dispatch prompt.

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

### 3d. Self-TODO gate (always applied, before user filters)

A candidate item — inline thread, top-level comment, or review-summary body — proceeds only if BOTH hold:

- **Not resolved.** Inline threads: `isResolved == false` (already required by 3a). Top-level comments and review-summary bodies have no resolved concept (3b/3c), so this half is automatically satisfied for them.
- **Self-flagged.** At least one comment in the item is authored by `ME` (`is_self == true`) and its body contains `TODO:` (case-insensitive substring match).

Drop anything failing either check — silently, before clustering.

It's not a "dropped cluster" (no reply owed, no cluster entry at all): it's out of scope because you haven't yet triaged it into a promised follow-up.

This is why a bot's own review-summary boilerplate ("I left N suggestions below") never survives this gate: `ME` never replies inside it, so it has no self-flagged TODO.

That holds regardless of how many of its inline suggestions are still open.

### 3e. Apply user filters

`by <logins>` matches **ownership**, not participation. The unit of ownership differs by source — see the ownership table in SKILL.md's Usage section (`../SKILL.md#usage`). Concretely:

- **inline threads** — keep the thread iff `comments[0].author.login ∈ {logins}`. When kept, **include all comments in the thread**.
  - Replies provide context for addressing the thread, even if the user didn't write them.

- **top-level comments** — keep where `user.login ∈ {logins}`.
- **review-summary bodies** — keep where the review's `user.login ∈ {logins}`.

`in <paths>` — keep where `path` starts-with any of the paths (folder match) or equals it (file match).
- Top-level/review-summary comments have no `path` and are kept only if **no** `in` filter was given.

If the result is empty after filtering, report and stop — don't cluster an empty set.

See `references/reply-patterns.md` (jq ownership query) for the inline-thread `by` filter pattern.

### 3f. Cluster, rank, propose

Load `code-review-pipeline/references/review-principles.md` first — it governs severity, drop framing, and actionable-vs-informational calls below.

Per comment field, once fetched and filtered: id, author, body, path, line, diffHunk, url, source (`"inline"`/`"top-level"`/`"review-summary"`), state (review-summary only), is_self.

Inline comments carry one more: `thread_id`, the enclosing thread's `PRRT_...` node id from 3a. Every comment flattened out of the same thread repeats it.

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

- For `apply` clusters, synthesize a one-line **Planned change** — the
  concrete edit that resolves the self-flagged TODO. Paraphrase or quote
  the TODO's own wording; don't invent scope it didn't state. `apply`
  alone doesn't tell the user what will actually change, and the TODO
  already named the promised fix — surface it instead of making them
  re-read the thread to find it.

### 3g. Emit the proposal block

Return this single block as your final message — one `### Cluster N` section per cluster, nothing else. Main never shows this to the user as text: it parses each section into one `AskUserQuestion` question (SKILL.md's "Output: cluster decisions via AskUserQuestion"), so every field below must stay filled in and unambiguous — main has no way to ask you a follow-up.

```
## PR <n> — <total> candidate comments in <K> clusters

### Cluster 1: <short title> [action: apply]
- Files: src/auth/login.ts, src/auth/session.ts
- Threads: PRRT_kwDOAbc123, PRRT_kwDOAbc456
- Planned change: <one-line synthesis of the TODO's promised fix>
- Comments:
  - [c12345] (alice) src/auth/login.ts:42 — "the rate limit should also..."
    <url>
  - [c12389] (yours) src/auth/login.ts:44 — "TODO: <what you promised to fix>"
    <url>
- Proposed drop reason (if flipped): rate-limit lives in the gateway, not the app
```

Top-level comments use `(top-level)` in `Files`; self-authored ones are labeled `(yours)`.

`Threads` lists each distinct `thread_id` in the cluster **once**, deduped — it is the cluster's reply-target list, and a thread contributing three comments still earns one entry.

Omit the line entirely for a cluster with no inline comments; top-level and review-summary sources have no thread to reply into.

`Planned change` appears only on `apply` clusters — `answer`/`drop` clusters have no code change to preview.

For `[action: answer]` clusters, leave the `Answer:` line for the user to fill — clustering never writes their answers.
