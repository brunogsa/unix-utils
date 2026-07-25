---
name: address-pr-comments
description: "Address unresolved PR review comments end-to-end: fetch (filter by author/file) → semantic cluster → one-round selection → commit-per-cluster → batch push → AI-signed inline replies."
disable-model-invocation: false
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

Why: see `references/reply-patterns.md` (Ownership rationale).

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

## Execution (Hybrid)

Subagents can't post replies, commit, or push — permission UIs live in main. Fetching + filtering + clustering is heavy and read-only. Split:

1. **Main context** — steps 0–2, 4–7 (pre-flight interview, preconditions, resolve repo/login, selection, commit, push, reply).
2. **Subagent** (`general-purpose`, background — the default) — step 3 (fetch, filter, cluster, rank, propose actions and drop reasons). Returns only the proposal block — raw comment JSON never reaches main.

Spawn the subagent with `model: "sonnet"` and `description: "Fetch, cluster, and rank PR review comments"`.

If the subagent reports zero unresolved comments matching the filters, stop — don't proceed to step 4.

## Scratchpad + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` — this run's durable working-state file (`<ts>` = run-start timestamp `date +%Y%m%d-%H%M%S` — the skill can run several times per session).

JSON, not prose — the pre-flight answers and per-cluster state read back as structured fields, mirroring the implement skill's run-state file.

Persist as produced, never at the end: the pre-flight answers first, then per-cluster state as it's decided — chosen action, drop/skip reason, resulting commit SHA.

On resume or after compaction, re-read this file and trust it over recalled context — a summary loses detail the file keeps verbatim.

Once the proposal step's clusters are approved (step 4), create one TaskList task per **applied** cluster — only those produce a commit, the CLAUDE.md test for a Task.

Put machine-checkable state (`action`, `commit_sha`, `status`) in each task's `metadata` field; keep narrative rationale in the scratchpad file, not duplicated across both.

Cross-reference the two surfaces by task id and file path only.

## Standards loaded on demand

These standards skills shape the work at specific moments — load each as its scope opens, not upfront.

Most load automatically via their description triggers; the explicit load points below guard against undertriggering:

- `code-standards` — before production edits in step 5.
- `test-standards` — when touching tests or needing a regression test (step 5).
- `doc-standards` — before editing code comments, docstrings, logs (step 5).
- `debug-standards` — when lint/test fails in step 1c or step 5.
- `commit-standards` — at every commit boundary (step 1b, step 5).

## Step 0: Pre-flight interview (main — the first thing, before any other step)

Discover cheaply, then ask everything that applies in ONE message — mirrors the implement skill's up-front interview. Nothing else runs before this interview.

```bash
git status --porcelain
```

Also probe for lint/test runners using 1c's table below (read-only — don't run anything yet).

Ask, in one message, only the questions whose condition holds:
- **Dirty tree** (only if git status printed output) — list the dirty files, ask whether to commit now.
- **Green baseline checker** (only if 1c's table matched multiple or none) — ask which lint/test commands establish 1c's green baseline.
- **Refactor + auto-review tails after this batch?** (yes/no, default no) — always asked.

The moment answers arrive, persist them to `/tmp/address-pr-comments_<session_id>_<ts>.json` — see "Scratchpad + TaskList state" above. A mid-flow compaction must not lose them.

Steps 1b, 1c, and 1d below consume these persisted answers; they don't ask again.

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

Use the persisted step-0 answer — if the tree was dirty, it says whether to commit now via `commit-standards`.

After the user commits or stashes, re-run the skill.

Don't proceed with a dirty tree — uncommitted work risks getting bundled into a cluster commit.

### 1c. Green baseline (lint + test)

Discover the runners (cheap probe, no full project scan):

| Marker present | Lint candidate | Test candidate |
|---|---|---|
| `package.json` | `npm run lint` if `scripts.lint` defined | `npm test` if `scripts.test` defined |
| `Makefile` | `make lint` if `^lint:` target | `make test` if `^test:` target |
| `pyproject.toml` | `ruff check .` / `flake8` | `pytest` |
| `Cargo.toml` | `cargo clippy` | `cargo test` |

If multiple or no markers matched, use the persisted step-0 answer for which commands to use.

Run lint then test:

```bash
<lint-cmd> > /tmp/apc-lint.txt 2>&1; echo "exit: $?"; tail -20 /tmp/apc-lint.txt
<test-cmd> > /tmp/apc-test.txt 2>&1; echo "exit: $?"; tail -30 /tmp/apc-test.txt
```

If either is red, abort — fix pre-existing breakage first so cluster commits don't conflate new regressions with old.

### 1d. Tails toggle

Use the persisted step-0 answer for whether to run refactor + auto-review tails.

This isn't a pass/fail precondition. The answer lives in `/tmp/address-pr-comments_<session_id>_<ts>.json` for step 7d, surviving compaction — default no if unanswered.

## Step 2: Resolve repo + own login (main)

```bash
OWNER_REPO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name')
ME=$(gh api user -q .login)
```

`OWNER_REPO` and `ME` go into the step-3 dispatch prompt — main never fetches comments itself.

`ME` powers the `(yours)` label later — not a filter.

## Step 3: Fetch, filter, cluster, rank, propose (subagent)

Dispatch a `general-purpose` subagent (model `"sonnet"`, background) with this prompt, filling in `<n>`, `OWNER_REPO`, `ME`, and the parsed filters:

```
Read ~/.claude/skills/address-pr-comments/references/step-3-fetch-cluster-propose.md
and execute it yourself for PR <n> in <OWNER_REPO>, then read SKILL.md's
"Output: proposal block format" section and emit the result in that
exact format. Ignore every other step in SKILL.md — those run in the
caller's own session, not here.

ME="<ME>". Filters: by=<logins or "none">, in=<paths or "none">.

Mark each comment's is_self = (author == ME); label it (yours) per the
proposal-block format. If nothing survives the filters, report zero
matches and stop — don't cluster.

Return ONLY the proposal block in your final message — never the raw
fetched JSON.
```

The subsections (fetch, filter, cluster, rank, propose — 3a through 3e) live in `references/step-3-fetch-cluster-propose.md`; only the dispatched subagent reads them.

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

Once parsing succeeds, create the TaskList tasks — see "Scratchpad + TaskList state" above — one per applied cluster.

## Step 5: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below — step 7d's tails review this range.

For each `apply` cluster, **in the order the user left them**:

1. Make the code changes that address the cluster's comments.
2. Stage **only** files relevant to this cluster — see `commit-standards` for the `git add` rules.
3. Commit using `commit-standards` (delegate via the Skill tool). Message body should reference the comments:

   ```
   <type>(<scope>): <cluster title>

   Addresses:
   - https://github.com/.../pull/169#discussion_r12345
   - https://github.com/.../pull/169#discussion_r12389
   ```

4. Capture the commit SHA — needed for the reply link in step 7, and record it in the cluster's TaskList task metadata plus the scratchpad file.

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

This is the UNLESS case in CLAUDE.md's never-pre-ask rule: `git push` is commonly allowlisted, so this one chat confirm is the only human gate.

If the push is rejected (remote moved), abort and tell the user to `git pull --rebase`, then re-run from step 5. Don't auto-rebase — risks lost work.

## Step 7: Post replies (main)

For **every comment in every surviving cluster** (apply/answer/drop), post a reply. Loop, don't batch — each reply is permission-gated.

### 7a. Reply body templates — minimal by default

Reviewer wrote what they wrote. Acknowledge it landed, link the proof, move on. See `references/reply-patterns.md` for observed deletions and survivors.

**Apply** — short ack + commit URL. Don't praise, don't re-explain, don't double-anchor the SHA.

```
<optional one-word ack> https://github.com/<OWNER_REPO>/pull/<n>/commits/<FULL_SHA>

_via Claude Code (`address-pr-comments`)_
```

Ack is optional — bare URL works.

**Answer** — the user-supplied answer text, in the user's voice. **No AI signature** (see 7c).

```
<answer_body>
```

**Drop** — minimal drop reason.

```
Dropping this one — <drop_reason>

_via Claude Code (`address-pr-comments`)_
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
  - Tagging as AI-assisted dilutes ownership (see `references/reply-patterns.md`).
  - The inverse case — a comment addressed to Claude, answered in Claude's own voice with a mandatory `Claude:` prefix — belongs to `gh-answer-claude-mentions`, not here.

Signature literal: `_via Claude Code (`address-pr-comments`)_`. Plain text only — the global no-emoji rule applies to posted replies too.

### 7d. Optional refactor + auto-review tails (main, when step 1d's toggle is on)

Skip this subsection entirely when the toggle is off — go straight to step 8.

Dispatch the shared deep-reviewer tail pair — [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md) — with `<BASE_REF>` = `<BATCH_BASE_SHA>`.
No `<SPEC_PLAN_PATHS>` — this flow has no spec/plan.

No new lint/test gate is needed — step 1c's green-baseline check already covers this batch.

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

When step 7d ran, append its two report paths and top findings to this summary so the user sees them in the same pass.

The user resolves the threads themselves after eyeballing the replies — that's deliberate, not an oversight.
