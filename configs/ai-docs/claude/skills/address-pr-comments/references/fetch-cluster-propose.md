# Fetching, filtering, clustering, ranking, and proposing PR-comment replies

Executed only by the subagent [`address-pr-comments/SKILL.md`](../SKILL.md) dispatches - main never reads this file. Run the subsections below in order, for the PR and filters in your dispatch prompt.

### 3a. Inline review comments via GraphQL (need `isResolved`)

Query: `references/queries.graphql`. Invoke via:

```bash
gh api graphql -f query='...' -F owner="$OWNER" -F repo="$REPO" -F n=<n>
```

Keep only threads where `isResolved == false`. Flatten the comments inside.

### 3b. Top-level conversation comments via REST (no resolved concept)

```bash
gh api repos/$OWNER_REPO/issues/<n>/comments
```

Always "open" by GitHub's model; include all of them.

### 3c. Review summary bodies via REST

```bash
gh api repos/$OWNER_REPO/pulls/<n>/reviews
```

Include each review's `body` (when non-empty) plus its `state` (`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`) - `state` feeds the rank rule below.

### 3d. Self-AI gate (always applied, before user filters)

A candidate item - inline thread, top-level comment, or review-summary body - proceeds only if BOTH hold:

- **Not resolved.** Inline threads: `isResolved == false` (3a). Top-level comments and review-summary bodies have no resolved concept, so they pass this half.

- **Self-flagged.** At least one comment in the item is authored by `ME` (`is_self == true`) and its body has a line whose first non-blank, non-list-marker token is `AI:` (case-insensitive).

Drop anything failing either check - silently, before clustering, and not as a dropped cluster: no reply is owed and no cluster entry exists.

### 3e. Apply user filters

`by <logins>` matches **ownership**, not participation; the unit differs by source (ownership table in SKILL.md's Usage section, `../SKILL.md#usage`). Inline `by` jq pattern: `references/reply-patterns.md`.

- **inline threads** - keep the thread iff `comments[0].author.login ∈ {logins}`. When kept, **include all comments in the thread**.

- **top-level comments** - keep where `user.login ∈ {logins}`.

- **review-summary bodies** - keep where the review's `user.login ∈ {logins}`.

`in <paths>` - keep where `path` starts-with any of the paths (folder match) or equals it (file match).

- Top-level/review-summary comments have no `path` and are kept only if **no** `in` filter was given.

If nothing remains after filtering, report and stop.

### 3f. Cluster, rank, propose

Load `code-review-pipeline/references/review-principles.md` first - it governs severity, drop framing, and actionable-vs-informational calls.

Comment fields: id, author, body, path, line, diffHunk, url, source (`"inline"`/`"top-level"`/`"review-summary"`), state (review-summary only), is_self.

Inline comments carry one more: `thread_id`, the thread's `PRRT_...` node id from 3a, repeated on each comment of that thread.

- Semantic-cluster: group comments addressing one logical change. Same-file is a hint, not a rule; cross-file comments can share a cluster.
- Rank: severity (CHANGES_REQUESTED > general > nit) → cluster size → file recency (most recent first).
- Default action per cluster:
  - `answer` if every comment is a question (ends in "?", or starts with why/what/how/when/could/would/should/can/is/are/does, no actionable request).
  - `apply` otherwise.
  - Never default to `drop` - that's always an explicit user choice.

- Per cluster, propose a one-line drop reason - honest and specific (not "out of scope").

- For `apply` clusters, synthesize a one-line **Planned change** - the concrete edit that resolves the self-flagged `AI:` note. Paraphrase or quote that note's own wording; don't invent scope it didn't state.

#### PR-wide sweep (`apply` clusters)

An `AI:` note is a rule for the whole PR, not a fix for the one line it sits on - the user leaves it once and never repeats it. So per `apply` cluster:

1. Write the note's general rule as a one-line `Rule:` - the class of problem, not this one line. The user corrects an over- or under-reaching rule via "Other" before any edit.

2. Run `gh pr diff <n>` once per run, shared by every cluster. The sweep universe is exactly its added lines: lines starting with `+`, minus the `+++` file headers.

3. Leave untouched code out of the sweep and out of the proposal - the rule is scoped to what this PR adds or changes.

4. The `in` filter narrows which comments become candidates, never the sweep universe - the rule covers the whole PR.

5. Match every added line against the rule. List each match under `Sites:` as `path:line`, commented lines included.

6. Read a file only to build a site's preview, never to widen the sweep.

7. A note local by nature (renaming one symbol) still gets the explicit `Sites: commented lines only (local fix)`.

8. A line matching several clusters' rules belongs to the highest-ranked one; each other cluster lists it as `path:line (in Cluster N)` and leaves it alone.

9. Give each site a preview: `before → after` when both sides fit on one line each, otherwise 1-3 lines of high-level pseudocode of the change.

### 3g. Emit the proposal block

Return this single block as your final message - one `### Cluster N` section per cluster, nothing else. Main renders each section into a chat preview plus one `AskUserQuestion` question (SKILL.md's "Output: preview every cluster, then ask") and cannot ask follow-ups, so fill every field unambiguously.

```
## PR <n> - <total> candidate comments in <K> clusters

### Cluster 1: <short title> [action: apply]
- Files: src/auth/login.ts, src/auth/session.ts
- Threads: PRRT_kwDOAbc123, PRRT_kwDOAbc456
- Planned change: <one-line synthesis of the `AI:` note's promised fix>
- Rule: <the general rule behind the note, applied PR-wide>
- Sites:
  - src/auth/login.ts:44 - `limit(req)` → `limit(req, user)`
  - src/auth/session.ts:118 - read the user from the session, pass it to `limit`
- Comments:
  - [c12345] (alice) src/auth/login.ts:42 - "the rate limit should also..."
    <url>
  - [c12389] (yours) src/auth/login.ts:44 - "AI: <what you promised to fix>"
    <url>
- Proposed drop reason (if flipped): rate-limit lives in the gateway, not the app
```

`[action: answer]` clusters carry `Draft answer: <the reply text>` in place of `Planned change`/`Rule`/`Sites`. Draft it from the `AI:` note's own instruction (the user already triaged what to say).

Top-level comments use `(top-level)` in `Files`; self-authored ones are labeled `(yours)`.

`Threads` lists each distinct `thread_id` in the cluster **once** - the reply-target list, so three comments from one thread earn one entry. Omit the line for a cluster with no inline comments.

`Planned change`, `Rule`, and `Sites` appear only on `apply` clusters.
