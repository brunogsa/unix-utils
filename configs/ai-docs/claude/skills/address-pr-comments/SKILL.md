---
name: address-pr-comments
description: "Address unresolved PR review comments end-to-end: fetch (filter by author/file) → semantic cluster → one-round selection → commit-per-cluster → batch push → AI-signed inline replies."
disable-model-invocation: false
---

# Address PR Comments

## Usage

`/address-pr-comments <PR#> [filters]`

`<PR#>` is required. Filters are freeform; parse semantically. Recognised forms:

| Form | Effect |
|---|---|
| `by alice, bob` | keep only items **owned** by these gh logins (see "ownership" below) |
| `in src/foo, src/bar` | keep only comments whose `path` matches these files/folders |
| (omitted) | every unresolved comment, all authors, all files |

**Ownership** (what `by` matches) is the author of an inline thread's **first comment** (replies never transfer it), of a top-level comment itself, or of a review for its summary body. Rationale: `references/reply-patterns.md`.

Examples: `/address-pr-comments 169`, `/address-pr-comments 169 by alice`, `/address-pr-comments 169 by alice, bob in src/auth`.

## Scope

Operates on one live PR on the current repo's GitHub remote, self-comments included (labeled `(yours)`).

Never resolves threads, requests re-review, dismisses reviews, or touches another PR.

Leaving threads open is deliberate — the user closes them after reviewing the replies.

## Execution (Hybrid)

Subagents can't post replies, commit, or push — permission UIs live in main. Fetching + filtering + clustering is heavy and read-only.

So main runs steps 0–2 and 4–7, while step 3 goes to a background `general-purpose` subagent that returns only the proposal block — raw comment JSON never reaches main.

Declare it as `agent(subAgent=general-purpose, title=Fetch, cluster, and rank PR review comments, model=sonnet, effort=medium)`.

If it reports zero unresolved comments matching the filters, stop — don't proceed to step 4.

## Run-state file + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` — this run's durable working-state file (`<ts>` = `date +%Y%m%d-%H%M%S`, since the skill can run several times per session).

Persist as produced, never at the end: pre-flight answers first, then each cluster's chosen action, drop/skip reason, and commit SHA.

On resume or after compaction, re-read it and trust it over recalled context.

Once step 4 approves the clusters, create one TaskList task per **applied** cluster — only those produce a commit, which is CLAUDE.md's test for a Task.

Put machine-checkable state (`action`, `commit_sha`, `status`) in the task's `metadata`; keep narrative rationale in the run-state file. Cross-reference the two by task id and file path only, never duplicating content.

## Standards loaded on demand

Load each as its scope opens, not upfront. Most fire automatically on their description triggers; these explicit load points guard against undertriggering:

- `code-standards` — before production edits in step 5.
- `test-standards` — when touching tests or needing a regression test (step 5).
- `doc-standards` — before editing code comments, docstrings, logs (step 5).
- `debug-standards` — when lint/test fails in step 1c or step 5.
- `commit-standards` — at every commit boundary (step 1b, step 5).

## Step 0: Pre-flight interview (main — before any other step)

Run `git status --porcelain` and probe for lint/test runners with 1c's table (read-only — run nothing yet). Then ask, in ONE message, only the questions whose condition holds:

- **Dirty tree** (only if git status printed output) — list the dirty files, ask whether to commit now.
- **Green baseline check?** (yes/no, default no) — always asked. Opt-in: 1c runs only on a yes.
- **Green baseline checker** (only if 1c's table matched multiple or none) — which lint/test commands establish the baseline; relevant only on an opt-in yes.
- **Refactor + auto-review tails after this batch?** (yes/no, default no) — always asked.

Persist the answers to the run-state file the moment they arrive — a mid-flow compaction must not lose them. Steps 1b–1d consume them and never ask again.

## Step 1: Validate preconditions (main)

Run 1a–1d in order, fail-fast on the first failure (1c only when step 0 opted in).

On a failure, abort with the suggested fix — never try to recover automatically.

### 1a. On the PR's branch

```bash
PR_BRANCH=$(gh pr view <n> --json headRefName -q .headRefName)
CUR_BRANCH=$(git branch --show-current)
```

If `PR_BRANCH != CUR_BRANCH`, abort:
> Not on PR branch. Run: `gh pr checkout <n>`

### 1b. Clean working tree

Never proceed with a dirty tree — uncommitted work risks getting bundled into a cluster commit.

Step 0's persisted answer says whether to commit now via `commit-standards`; once the user commits or stashes, re-run the skill.

### 1c. Green baseline (lint + test — opt-in)

Runs only on a yes to step 0's "Green baseline check?"; when declined or unanswered, skip this subsection entirely.

Discover the runners (cheap probe, no full project scan):

| Marker present | Lint candidate | Test candidate |
|---|---|---|
| `package.json` | `npm run lint` if `scripts.lint` defined | `npm test` if `scripts.test` defined |
| `Makefile` | `make lint` if `^lint:` target | `make test` if `^test:` target |
| `pyproject.toml` | `ruff check .` / `flake8` | `pytest` |
| `Cargo.toml` | `cargo clippy` | `cargo test` |

If multiple or no markers matched, use the persisted step-0 answer instead. Run lint then test:

```bash
<lint-cmd> > /tmp/apc-lint.txt 2>&1; echo "exit: $?"; tail -20 /tmp/apc-lint.txt
<test-cmd> > /tmp/apc-test.txt 2>&1; echo "exit: $?"; tail -30 /tmp/apc-test.txt
```

If either is red, abort — fix pre-existing breakage first so cluster commits don't conflate new regressions with old.

### 1d. Tails toggle

Not a pass/fail precondition — just read step 0's persisted answer on refactor + auto-review tails, which step 7d consumes. Default no if unanswered.

## Step 2: Resolve repo + own login (main)

```bash
OWNER_REPO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name')
ME=$(gh api user -q .login)
```

Both go into the step-3 dispatch prompt — main never fetches comments itself. `ME` powers the `(yours)` label, not a filter.

## Step 3: Fetch, filter, cluster, rank, propose (subagent)

Dispatch `agent(subAgent=general-purpose, title=Fetch, cluster, and rank PR review comments, model=sonnet, effort=medium)` in the background, with this prompt, filling in `<n>`, `OWNER_REPO`, `ME`, and the parsed filters:

```
Read ~/.claude/skills/address-pr-comments/references/fetch-cluster-propose.md
and execute it yourself for PR <n> in <OWNER_REPO>, emitting the proposal
block in the exact format its final section gives. Ignore SKILL.md's other
steps — those run in the caller's own session, not here.

ME="<ME>". Filters: by=<logins or "none">, in=<paths or "none">.

Mark each comment's is_self = (author == ME); label it (yours) per the
proposal-block format. If nothing survives the filters, report zero
matches and stop — don't cluster.

Return ONLY the proposal block in your final message — never the raw
fetched JSON.
```

The subsections (fetch, filter, cluster, rank, propose — 3a through 3e) live in `references/fetch-cluster-propose.md`; only the dispatched subagent reads them.

## Output: the proposal block

The subagent returns one editable block of `### Cluster N` sections (template in `references/fetch-cluster-propose.md`). Relay it verbatim; the user edits it in place and sends it back. **One round.**

### Editing rules (state these to the user)

- Flip `[action: apply]` to `[action: answer]` or `[action: drop]`.
- Edit the drop-reason text directly — what's there is only the proposal.
- Delete a whole `### Cluster N` section to skip it entirely (no commit, no reply).
- For `answer`, add an `Answer:` line — clustering doesn't write your answers.
- Send the edited block back as a single message.

## Step 4: Parse the user's edited block (main)

For each surviving cluster, record its `action`, `comment_ids` (`databaseId`), `urls` (for cross-linking in the commit body), and its `drop_reason` or `answer_body` where the action calls for one.

If parse fails (mangled markers, missing `Answer:` for answer clusters), surface the exact issue and ask the user to re-send. Don't guess.

Then create one TaskList task per applied cluster — see "Run-state file + TaskList state" above.

## Step 5: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below — step 7d's tails review this range.

For each `apply` cluster, **in the order the user left them**:

1. Make the code changes that address the cluster's comments.
2. Stage **only** files relevant to this cluster — see `commit-standards` for the `git add` rules.
3. Commit using `commit-standards` (delegate via the Skill tool), titling it `<type>(<scope>): <cluster title>` and listing the cluster's comment URLs under an `Addresses:` block in the body.

4. Capture the commit SHA into the cluster's TaskList metadata and the run-state file — step 7's reply link needs it.

If a cluster's edits accidentally touch files outside its scope (drift), never silently absorb it.

Pause and ask the user whether to split it into a separate `[Drift]` commit per CLAUDE.md, or bundle it if trivial.

Either answer only decides where the drift fix commits; the cluster's own commit flow resumes, then continues to the next cluster.

## Step 6: Batch push (main)

After all `apply` clusters are committed, run a single `git push`. Confirm with the user first — it's irreversible, triggers CI, and notifies reviewers.

This is the UNLESS case in CLAUDE.md's never-pre-ask rule: `git push` is commonly allowlisted, so this chat confirm is the only human gate.

If the push is rejected (remote moved), abort and surface it — the per-cluster commits stand as-is.

Ask the user to resolve the divergence manually (never auto-rebase), then re-attempt only the push, skipping step 5.

## Step 7: Post replies (main)

For **every comment in every surviving cluster** (apply/answer/drop), post a reply. Loop, don't batch — each reply is permission-gated.

On a permission denial, skip that reply and list it in step 8's report.

On a `gh api` failure, retry once, then skip and list it too. The loop always continues to the next comment — never stops.

### 7a. Reply body templates — minimal by default

Reviewer wrote what they wrote. Acknowledge it landed, link the proof, move on. See `references/reply-patterns.md` for observed deletions and survivors.

**Apply** — optional one-word ack + commit URL, nothing more. Don't praise, don't re-explain, don't double-anchor the SHA.

```
<optional one-word ack> https://github.com/<OWNER_REPO>/pull/<n>/commits/<FULL_SHA>

_via Claude Code (`address-pr-comments`)_
```

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

That `@<author> re: <link>` prefix pings the commenter and preserves thread context.

### 7c. Signature rules — split by action

`apply` and `drop` replies carry the AI signature **mandatorily**; `answer` replies carry **none**.

An answer is the user's reasoning in the user's voice, and an AI tag dilutes that ownership (see `references/reply-patterns.md`).

The inverse case — a comment addressed to Claude, answered in Claude's own voice — belongs to `gh-answer-claude-mentions`, not here.

Signature literal: `_via Claude Code (`address-pr-comments`)_`. Plain text only — the global no-emoji rule applies to posted replies too.

### 7d. Optional refactor + auto-review tails (main, when step 1d's toggle is on)

When the toggle is off, skip to step 8.

Otherwise dispatch the shared deep-reviewer tail pair — [`deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md).

Pass `<BASE_REF>` = `<BATCH_BASE_SHA>` and no `<SPEC_PLAN_PATHS>`, since this flow has no spec/plan.

The tails are report-only (the `deep-reviewer-write-guard.sh` PreToolUse hook enforces it), so they need no new lint/test gate.

## Step 8: Final report (main)

Print:

```
PR <n> address summary
- Applied: <count> clusters → <count> commits → pushed as <range>
- Answered: <count> clusters → <count> replies
- Dropped:  <count> clusters → <count> replies
- Skipped (deleted from proposal): <count> clusters
- Reply failures (permission/API skip): <count> comments
- Open threads remaining for you to resolve: <link to PR's "Files changed">
```

When step 7d ran, append its two report paths and top findings to this summary so the user sees them in the same pass.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
