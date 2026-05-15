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
| `by alice, bob` | keep only comments authored by these gh logins |
| `in src/foo, src/bar` | keep only comments whose `path` matches these files/folders |
| (omitted) | all unresolved comments from all authors on all files |

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
- **Self-comments are included** — sometimes the user is addressing their own notes-to-self. The proposal block labels them `(yours)` so they're easy to spot.

## Reuse note

Mode B of `improve-principles-and-skills-from-user-feedback` solves PR-comment fetching for a different purpose (mining feedback for guideline updates).

This skill **duplicates** the `gh api` primitives intentionally:

- The two skills' fetch shapes diverge — this one needs GraphQL for `isResolved`; that one only needs REST.
- A shared module would couple two different lifecycles.

Duplication is the right call here.

## Execution (Hybrid)

Subagents cannot post replies, run commits, or push — those need permission UIs in the main context. But fetching + clustering + ranking is heavy and read-only. Split:

1. **Main context** — steps 1, 2, 4–7 (preconditions, fetch, selection, commit, push, reply).
2. **Subagent** (`general-purpose`, foreground) — step 3 (cluster, rank, propose default actions, propose drop reasons). Returns the proposal block.

Spawn the subagent with `description: "Cluster and rank PR review comments"`.

If step 2 yields zero unresolved comments matching the filters, report that and stop. Don't spawn the subagent on nothing.

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

If multiple match, ask which to use. If none match, ask the user to provide the commands.

Run lint then test (per CLAUDE.md "Save slow command output, verify from the file" pattern):

```bash
<lint-cmd> > /tmp/apc-lint.txt 2>&1; echo "exit: $?"; tail -20 /tmp/apc-lint.txt
<test-cmd> > /tmp/apc-test.txt 2>&1; echo "exit: $?"; tail -30 /tmp/apc-test.txt
```

If either is red, abort. Pre-existing breakage isn't this skill's problem — fix it first so cluster commits don't conflate new regressions with old ones.

## Step 2: Fetch + filter unresolved comments (main)

### 2a. Resolve repo + own login

```bash
OWNER_REPO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name')
ME=$(gh api user -q .login)
```

`ME` powers the `(yours)` label later — not a filter.

### 2b. Inline review comments via GraphQL (need `isResolved`)

```graphql
query($owner: String!, $repo: String!, $n: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $n) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 50) {
            nodes {
              databaseId
              author { login }
              body
              path
              line
              url
              diffHunk
            }
          }
        }
      }
    }
  }
}
```

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

Include each review's `body` (when non-empty) plus its `state` (`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`). The `state` feeds the relevance sort in step 3.

### 2e. Apply user filters

- `by <logins>` — keep where `author.login ∈ {logins}`.
- `in <paths>` — keep where `path` starts-with any of the paths (folder match) or equals it (file match).
  - Top-level/review-summary comments have no `path` and are kept only if **no** `in` filter was given.

If the result is empty after filtering, report and stop.

## Step 3: Cluster, rank, propose (subagent)

Hand the filtered comment list to the subagent with this prompt skeleton:

```
You receive a list of PR review comments. Produce a proposal block per the
output format below.

For each comment you receive these fields: id, author, body, path, line,
diffHunk, url, source ("inline"|"top-level"|"review-summary"), state (only
for review-summary), is_self (true if author == ME).

Tasks:
1. Semantic-cluster: group comments that address one logical change. Comments
   on the same file are a hint, not a rule — comments on different files can
   share a cluster if they describe one underlying issue.
2. Rank clusters by: severity (CHANGES_REQUESTED > general > nit) → cluster
   size → file recency (most recently modified first).
3. Per cluster, pick a default action:
   - `answer` if every comment is a question (heuristic: ends in "?", or
     starts with why/what/how/when/could/would/should/can/is/are/does, with
     no actionable request)
   - `apply` otherwise
   - Never default to `drop` — dropping is always an explicit user choice.
4. For each cluster, propose a one-line drop reason the user can use if they
   flip the action to `drop`. Be honest and specific (not "out of scope").

Emit the proposal block exactly per the format below.
```

## Output: proposal block format

Return this single editable block. The user edits in place — flips action markers, edits drop reasons, deletes whole clusters they don't want touched — then sends back. **One round.**

```
## PR <n> — <total> unresolved comments in <K> clusters

### Cluster 1: <short title> [action: apply]
- Files: src/auth/login.ts, src/auth/session.ts
- Comments:
  - [c12345] (alice) src/auth/login.ts:42 — "the rate limit should also..."
    https://github.com/.../pull/169#discussion_r12345
  - [c12389] (alice) src/auth/session.ts:88 — "same here"
    https://github.com/.../pull/169#discussion_r12389
- Proposed drop reason (if flipped): rate-limit lives in the gateway, not the app

### Cluster 2: <short title> [action: answer]
- Files: src/api/users.ts
- Comments:
  - [c12401] (bob) src/api/users.ts:120 — "why a Map and not a Set here?"
    https://github.com/.../pull/169#discussion_r12401
- Proposed drop reason (if flipped): N/A — pure question

### Cluster 3: <short title> [action: apply]
- Files: (top-level)
- Comments:
  - [c99001] (yours) PR conversation — "TODO: also bump the deps"
    https://github.com/.../pull/169#issuecomment-99001
- Proposed drop reason (if flipped): deferred to a follow-up PR
```

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

If the push is rejected (remote moved), abort and tell the user to `git pull --rebase` and re-run from step 5 onward. Don't auto-rebase — silent rebase risks losing work.

## Step 7: Post replies (main)

For **every comment in every surviving cluster** (apply, answer, and drop alike), post a reply. Loop, don't batch — each reply is a permission-gated API call.

### 7a. Reply body templates

**Apply** — link to the commit. Construct the URL from `OWNER_REPO` and the SHA captured in step 5:

```
Addressed in <SHORT_SHA>: https://github.com/<OWNER_REPO>/pull/<n>/commits/<FULL_SHA>

🤖 _via Claude Code (`address-pr-comments`)_
```

**Answer** — the user-supplied answer text:

```
<answer_body>

🤖 _via Claude Code (`address-pr-comments`)_
```

**Drop** — the (user-edited) drop reason:

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

For top-level / review-summary replies, prefix with `@<original_author> re: <link>` so the original commenter still gets pinged and the thread context is recoverable.

### 7c. Signature is mandatory

Every reply ends with the literal line `🤖 _via Claude Code (`address-pr-comments`)_`.

This is the **only** exception to the global no-emoji rule — keeping the existing Claude Code visual convention earns the trade.

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
