---
name: address-pr-comments
description: "Address unresolved PR review comments end-to-end: fetch (filter by author/file) → semantic cluster → one-round selection → commit-per-cluster → batch push → AI-signed inline replies. User-invoked only."
disable-model-invocation: true
---

# Address PR Comments

Take a PR's unresolved review comments through the full address-and-respond loop:

1. Fetch unresolved comments (filter by author and/or file).
2. Semantic-cluster, sort by relevance, propose default per-cluster action (apply / answer / drop).
3. **One round** of user editing on the proposal block (no per-cluster back-and-forth).
4. One commit per applied cluster, one batch push at the end.
5. Reply on every comment of every cluster — AI-signed — linking to commit, answering the question, or stating the drop reason.

This skill **does not** mark threads resolved. The user closes them after reviewing the replies.

## Usage

`/address-pr-comments <PR#> [filters]`

`<PR#>` is required. Filters are freeform; parse semantically. Recognised forms:

| Form | Effect |
|---|---|
| `by alice, bob` | keep only items **owned** by these gh logins (see "ownership" below) |
| `in src/foo, src/bar` | keep only comments whose `path` matches these files/folders |
| (omitted) | all unresolved comments from all authors on all files |

**Ownership** (what `by` matches):
- **inline thread** — owner = author of the thread's **first comment**. Replies don't transfer ownership.
- **top-level conversation comment** — owner = author of the comment itself (no threading).
- **review-summary body** — owner = author of the review.

Why: the thread-opener raises the concern; replies are participation.

- Filtering by participation surfaces threads the user only answered in (not theirs to address). Thread-opener matches the "my comments" mental model.

Examples:
- `/address-pr-comments 169`
- `/address-pr-comments 169 by alice`
- `/address-pr-comments 169 in src/auth, src/api/users.ts`
- `/address-pr-comments 169 by alice, bob in src/auth`

The PR number alone is enough — both filters are optional.

## Scope

- **Input**: live PR on the current repo's GitHub remote.
- **Mutates**:
  - The local working tree (one commit per applied cluster on the PR's branch).
  - The remote (one batch `git push` after all commits).
  - The PR (one reply per addressed comment, AI-signed).
- **Does not**: resolve threads, request re-review, dismiss reviews, or touch other PRs.
- **Self-comments are included** — the proposal block labels them `(yours)`.

## Reuse note

Duplicates `gh api` fetch primitives from `improve-principles-and-skills-from-user-feedback` Mode B intentionally — that flow uses REST only; this one needs GraphQL for `isResolved`.

## Execution (Hybrid)

Subagents can't post replies, commit, or push — permission UIs live in main. Fetching + clustering is heavy and read-only. Split:

1. **Main context** — steps 1, 2, 4–7 (preconditions, fetch, selection, commit, push, reply).
2. **Subagent** (`general-purpose`, foreground) — step 3 (cluster, rank, propose default actions, propose drop reasons). Returns the proposal block.

Spawn the subagent with `description: "Cluster and rank PR review comments"`.

If step 2 yields zero unresolved comments matching the filters, report that and stop. Don't spawn the subagent on nothing.

## Standards loaded on demand

These standards skills shape the work at specific moments — load each as its scope opens, not upfront.

Most load automatically via their description triggers; the explicit load points below guard against undertriggering:

- `~/.claude/skills/reviewer-agent/references/review-principles.md` — read while interpreting reviewer comments in step 3 (severity vs. nit, framing drop reasons, distinguishing actionable from informational).
- `code-standards` — load before any production edit while applying a cluster (step 5).
- `test-standards` — load when a cluster touches tests, or when applying a change needs a regression test (step 5).
- `doc-standards` — load before adding any comment, docstring, log line, or doc edit while applying a cluster (step 5).
- `debug-standards` — load when lint/test goes red in step 1c, or when a test fails for the wrong reason while applying a cluster (step 5).
- `commit-standards` — load at every commit boundary (step 1b offer-to-commit, step 5 per-cluster commits).

Lazy load keeps context lean; load at the right moment ensures the rules actually shape the output.

## Step 1: Validate preconditions (main)

All three must hold. If any fails, abort with the suggested fix — don't try to recover automatically.

### 1a. On the PR's branch

```bash
PR_BRANCH=$(gh pr view <n> --json headRefName -q .headRefName)
CUR_BRANCH=$(git branch --show-current)
```

If `PR_BRANCH != CUR_BRANCH`, abort:
> Not on PR branch. Run: `gh pr checkout <n>`

### 1b. Clean working tree

```bash
git status --porcelain
```

If non-empty, **offer to commit first**: list the dirty files, ask whether to commit them now (delegate the commit to `commit-standards`).

After the user commits or stashes manually, re-run the skill.

Don't proceed with a dirty tree — uncommitted work risks getting bundled into a cluster commit.

### 1c. Green baseline (lint + test)

Discover the runners (cheap probe, no full project scan):

| Marker present | Lint candidate | Test candidate |
|---|---|---|
| `package.json` | `npm run lint` if `scripts.lint` defined | `npm test` if `scripts.test` defined |
| `Makefile` | `make lint` if `^lint:` target | `make test` if `^test:` target |
| `pyproject.toml` | `ruff check .` / `flake8` | `pytest` |
| `Cargo.toml` | `cargo clippy` | `cargo test` |

If multiple match or none match, ask the user which commands to use.

Run lint then test:

```bash
<lint-cmd> > /tmp/apc-lint.txt 2>&1; echo "exit: $?"; tail -20 /tmp/apc-lint.txt
<test-cmd> > /tmp/apc-test.txt 2>&1; echo "exit: $?"; tail -30 /tmp/apc-test.txt
```

If either is red, abort — fix pre-existing breakage first so cluster commits don't conflate new regressions with old.

## Step 2: Fetch + filter unresolved comments (main)

### 2a. Resolve repo + own login

```bash
OWNER_REPO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name')
ME=$(gh api user -q .login)
```

`ME` powers the `(yours)` label later — not a filter.

### 2b. Inline review comments via GraphQL (need `isResolved`)

Query lives in `references/queries.graphql`. Invoke via:

```bash
gh api graphql -f query='...' -F owner="$OWNER" -F repo="$REPO" -F n=<n>
```

Keep only threads where `isResolved == false`. Flatten the comments inside.

### 2c. Top-level conversation comments via REST (no resolved concept)

```bash
gh api repos/$OWNER_REPO/issues/<n>/comments
```

These are always "open" by GitHub's model. Include all of them.

### 2d. Review summary bodies via REST

```bash
gh api repos/$OWNER_REPO/pulls/<n>/reviews
```

Include each review's `body` (when non-empty) plus its `state` (`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`) — `state` feeds step 3's relevance sort.

### 2e. Apply user filters

`by <logins>` matches **ownership**, not participation. The unit of ownership differs by source — see the table in the Usage section. Concretely:

- **inline threads** — keep the thread iff `comments[0].author.login ∈ {logins}`. When kept, **include all comments in the thread**.
  - Replies provide context for addressing the thread, even if the user didn't write them.
- **top-level comments** — keep where `user.login ∈ {logins}`.
- **review-summary bodies** — keep where the review's `user.login ∈ {logins}`.

`in <paths>` — keep where `path` starts-with any of the paths (folder match) or equals it (file match).
- Top-level/review-summary comments have no `path` and are kept only if **no** `in` filter was given.

If the result is empty after filtering, report and stop.

Example query for inline threads with `by` filter (jq):

```bash
jq --arg author "alice" '
  [.data.repository.pullRequest.reviewThreads.nodes[]
    | select(.isResolved == false)
    | select(.comments.nodes[0].author.login == $author)
  ]' inline.json
```

The `select(.comments.nodes[0].author.login == ...)` is the ownership check — `nodes[0]` is the thread-opener.

## Step 3: Cluster, rank, propose (subagent)

Hand the filtered comment list to the subagent with this prompt skeleton:

```
Input fields per comment: id, author, body, path, line, diffHunk, url,
source ("inline"|"top-level"|"review-summary"), state (review-summary only),
is_self (author == ME).

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

Emit the proposal block exactly per the format below.
```

## Output: proposal block format

Return this single editable block. The user edits in place — flips action markers, edits drop reasons, deletes clusters to skip — then sends back. **One round.**

```
## PR <n> — <total> unresolved comments in <K> clusters

### Cluster 1: <short title> [action: apply]
- Files: src/auth/login.ts, src/auth/session.ts
- Comments:
  - [c12345] (alice) src/auth/login.ts:42 — "the rate limit should also..."
    <url>
  - [c12389] (alice) src/auth/session.ts:88 — "same here"
    <url>
- Proposed drop reason (if flipped): rate-limit lives in the gateway, not the app
```

For `[action: answer]`, add an `Answer:` line. Top-level comments use `(top-level)` in `Files`; self-authored ones are labeled `(yours)`. See "Editing rules" for the full set.

### Editing rules (state these to the user)

- Change `[action: apply]` to `[action: answer]` or `[action: drop]` to flip.
- Edit the drop-reason text directly — what's there is the proposal.
- Delete a whole `### Cluster N` section to skip it entirely (no commit, no reply).
- For `answer`, add an `Answer:` line with the response text (the AI's clustering doesn't write your answers).
- Send the edited block back as a single message.

## Step 4: Parse the user's edited block (main)

Parse the returned block. For each surviving cluster, record:
- `action` ∈ {apply, answer, drop}
- `comment_ids` (list of `databaseId`)
- `urls` (for cross-linking in commit body)
- `drop_reason` (if drop) or `answer_body` (if answer) or nothing (if apply)

If parse fails (mangled markers, missing `Answer:` for answer clusters), surface the exact issue and ask the user to re-send. Don't guess.

## Step 5: Per-cluster commits (main, applied clusters only)

For each `apply` cluster, **in the order the user left them**:

1. Make the code changes that address the cluster's comments.
2. Stage **only** files relevant to this cluster (no `git add -A` — bundling unrelated files breaks "one logical change per commit").
3. Commit using `commit-standards` (delegate via the Skill tool). Message body should reference the comments:

   ```
   <type>(<scope>): <cluster title>

   Addresses:
   - https://github.com/.../pull/169#discussion_r12345
   - https://github.com/.../pull/169#discussion_r12389
   ```

4. Capture the commit SHA — needed for the reply link in step 7.

If a cluster's edits accidentally touch files outside its scope (drift), pause and ask the user whether to:

- (a) split into a separate `[Drift]` commit per CLAUDE.md, or
- (b) bundle if trivial.

Don't silently absorb.

## Step 6: Batch push (main)

After all `apply` clusters are committed:

```bash
git push
```

Single push. Confirm with the user before running — it's the irreversible step that triggers CI and notifies reviewers.

If the push is rejected (remote moved), abort and tell the user to `git pull --rebase`, then re-run from step 5. Don't auto-rebase — risks lost work.

## Step 7: Post replies (main)

For **every comment in every surviving cluster** (apply/answer/drop), post a reply. Loop, don't batch — each reply is permission-gated.

### 7a. Reply body templates — minimal by default

Reviewer wrote what they wrote. Acknowledge it landed, link the proof, move on. Anything more usually gets deleted post-post. Observed deletions (real edits):

- ❌ "Pegada boa — exatamente o cenário..." — unsolicited praise reads as canned-bot empathy.
- ❌ "Cobertura adicionada em <sha>: <url>. summarize() reusa o mesmo X, mas sem cenário pinned..." — re-explaining the reviewer's own point back to them is patronizing.

**Apply** — short ack + commit URL. Don't praise, don't re-explain, don't double-anchor the SHA.

```
<optional one-word ack> https://github.com/<OWNER_REPO>/pull/<n>/commits/<FULL_SHA>

🤖 _via Claude Code (`address-pr-comments`)_
```

Examples that survived: `Bem visto. Aplicado em <url>`, `Cobertura adicionada em <url>`, `Adicionado em <url>`. Ack is optional — bare URL works.

**Answer** — the user-supplied answer text, in the user's voice. **No AI signature** (see 7c).

```
<answer_body>
```

**Drop** — minimal drop reason.

```
Dropping this one — <drop_reason>

🤖 _via Claude Code (`address-pr-comments`)_
```

### 7b. Reply API per comment source

| Source | gh command |
|---|---|
| inline | `gh api -X POST repos/$OWNER_REPO/pulls/<n>/comments/<comment_id>/replies -f body='...'` |
| top-level | `gh api -X POST repos/$OWNER_REPO/issues/<n>/comments -f body='@<author> re: <comment_url> — <body>'` |
| review-summary | same as top-level (no per-review reply API) |

For top-level / review-summary replies, prefix with `@<original_author> re: <link>` — pings the commenter and preserves thread context.

### 7c. Signature rules — split by action

- `apply` replies: AI signature **mandatory**.
- `drop` replies: AI signature **mandatory**.
- `answer` replies: **NO signature**.
  - The answer carries the user's reasoning in the user's voice.
  - Tagging as AI-assisted dilutes ownership; reviewer may discount it (observed: user stripped signature on C3 of PR #2030).

Signature literal: `🤖 _via Claude Code (`address-pr-comments`)_`. Only exception to the no-emoji rule — Claude Code's visual convention earns it.

## Step 8: Final report (main)

Print a compact summary:

```
PR <n> address summary
- Applied: <count> clusters → <count> commits → pushed as <range>
- Answered: <count> clusters → <count> replies
- Dropped:  <count> clusters → <count> replies
- Skipped (deleted from proposal): <count> clusters
- Open threads remaining for you to resolve: <link to PR's "Files changed">
```

The user resolves the threads themselves after eyeballing the replies — that's deliberate, not an oversight.
