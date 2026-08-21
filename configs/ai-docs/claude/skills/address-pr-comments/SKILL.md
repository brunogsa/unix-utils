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
| (omitted) | every candidate comment (see gate below), all authors, all files |

**Ownership** (what `by` matches) is the author of an inline thread's **first comment** (replies never transfer it), of a top-level comment, or of a review for its summary body. Rationale: `references/reply-patterns.md`.

**Self-TODO gate (always applied, never a filter you pass):** an item is a candidate only if unresolved AND you (`ME`) already replied with `TODO:` somewhere in it —
mirroring your own review workflow, where you triage reviewer comments by hand and leave a `TODO: ...` marking a promised follow-up. The skill executes those follow-ups; it never
replies to fresh, untriaged comments on your behalf. Full rule: `references/fetch-cluster-propose.md#3d-self-todo-gate-always-applied-before-user-filters`.

Examples: `/address-pr-comments 169`, `/address-pr-comments 169 by alice`, `/address-pr-comments 169 by alice, bob in src/auth`.

## Scope

Operates on one live PR on the current repo's GitHub remote, self-comments included (labeled `(yours)`). Never resolves threads, requests re-review, dismisses reviews, or touches another PR — leaving
threads open is deliberate, the user closes them after reviewing the replies.

## Execution (Hybrid)

Subagents can't post replies, commit, or push — permission UIs live in main. Fetching + filtering + clustering is heavy and read-only, so main runs steps 0–2 and
4–7, while step 3 goes to a background `general-purpose` subagent that returns only the proposal block — raw comment JSON never reaches main. If it reports zero candidate
comments, stop — don't proceed to step 4.

## Run-state file + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` — this run's durable working-state file (`<ts>` = `date +%Y%m%d-%H%M%S`, since the skill can run several times per session).

Persist as produced, never at the end: pre-flight answers first, then each cluster's chosen action, planned change (apply clusters), drop/skip reason, and commit SHA. When the repo-green gate
is on, also persist its baseline and final verdict — never log content — per `references/opt-in-gates.md`.

Once step 4 approves the clusters, create one TaskList task per **applied** cluster — only those produce a commit, which is CLAUDE.md's test for a Task. Put machine-checkable
state (`action`, `commit_sha`, `status`) in the task's `metadata`; keep narrative rationale in the run-state file.

## Standards loaded on demand

Load each as its scope opens, not upfront. Most fire automatically on their description triggers; these explicit load points guard against undertriggering:

- `code-standards` — before production edits in step 5.
- `test-standards` — when touching tests or needing a regression test (step 5).
- `doc-standards` — before editing code comments, docstrings, logs (step 5).
- `debug-standards` — when lint/test fails in step 1c or step 5.
- `commit-standards` — at every commit boundary (step 1b, step 5).

## Step 0: Pre-flight interview (main — before any other step)

Before any other step, ask via **one `AskUserQuestion` call** covering up to 5 candidate questions (dirty tree, baseline, checker cmd, green gate, tails) — only those whose condition
holds, never a freeform chat message. Full candidate table, conditions, exact wording, options, and the 4-per-call batching rule: [`references/preflight-interview.md`](references/preflight-interview.md) — load it now.

Persist the answers the moment they arrive; steps 1b–1d consume them and never ask again.

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

On a yes to step 0's "Green baseline check?", load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the runner-discovery table and the abort rule. Otherwise skip to 1d.

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

Subsections 3a–3g (fetch, gate, filter, cluster, rank, propose) live in `references/fetch-cluster-propose.md`; only the dispatched subagent reads them.

## Output: cluster decisions via AskUserQuestion

The subagent returns structured per-cluster data (`references/fetch-cluster-propose.md`'s 3g format) — main never relays it to the user as raw text to hand-edit. Instead, build one `AskUserQuestion` question per cluster.

Per cluster: `header` = `Cluster N`; `question` = the cluster's short title plus a one-line summary. Four options, always in this order, default first and labeled "(Recommended)":

- **Apply** — description: the subagent's one-line `Planned change`. `preview`: every comment in the cluster (author, `(yours)` if self, file:line, body, url) plus the deduped `Threads` list.
- **Answer** — description: "reply with your own reasoning instead of changing code — pick Other below and type it." `preview`: same full context as Apply.
- **Drop** — description: the subagent's proposed one-line drop reason. `preview`: same full context.
- **Skip** — description: "leave this cluster out entirely — no commit, no reply, thread stays open." `preview`: same full context.

`AskUserQuestion` caps at 4 per call — batch clusters 4 at a time, issuing consecutive calls back-to-back until every cluster has been asked. This is the "one round":
every decision arrives in the same unbroken back-and-forth, just chunked by the tool's limit.

The built-in "Other" is how the user overrides a default: typed text becomes the `answer_body` (`answer`), a replacement `planned_change` (`apply`), or a custom `drop_reason` (`drop`) — infer which
from the text's shape; ask a one-line clarification rather than guess when genuinely ambiguous.

## Step 4: Parse the AskUserQuestion answers, then create TaskList tasks (main)

For each cluster, map its answer to an `action` (`apply`/`answer`/`drop`; `skip` clusters are dropped entirely, no task, no reply) plus `comment_ids` (`databaseId`), `thread_ids` (the deduped `Threads` line), and
`urls` for cross-linking in the commit body. `thread_ids` drives step 7's replies; `comment_ids`/`urls` stay for the commit body and top-level reply prefix.

Add `planned_change` on apply clusters (guides step 5's edit), plus whichever of `drop_reason`/`answer_body` the action needs, from the subagent's default or the user's "Other" text.

If a cluster's action is `answer` and the user picked plain "Answer" rather than typing via "Other", the answer body is missing — the model can't invent it.
Batch these into one follow-up `AskUserQuestion` round (one question per such cluster, `header: Cluster N`, no preset options, just "Other"), 4 per call, before proceeding.

**Before touching any code in step 5**, create one TaskList task per applied cluster — see "Run-state file + TaskList state" above. This step ends only once every
applied cluster has its task.

## Step 5: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below — step 7d's tails review this range. If step 0's "Repo-green gate after
changes?" is on, capture the repo-green baseline now, before the first cluster edit — see [`references/opt-in-gates.md`](references/opt-in-gates.md).

For each `apply` cluster, **in the order the user left them**:

1. Make the code changes that address the cluster's comments.
2. Stage **only** files relevant to this cluster — see `commit-standards` for the `git add` rules.
3. Commit using `commit-standards` (via Skill tool), titling it `<type>(<scope>): <cluster title>` and listing the cluster's comment URLs under an `Addresses:` block in the body.
4. Capture the commit SHA into the cluster's TaskList metadata and the run-state file — step 7's reply link needs it.

If a cluster's edits accidentally touch files outside its scope (drift), never silently absorb it — pause and ask the user whether to split it into a separate
`[Drift]` commit per CLAUDE.md, or bundle it if trivial. Either answer only decides where the drift fix commits; the cluster's own flow then resumes.

### Repo-green gate (opt-in, after all apply clusters are committed, before step 6's push)

Runs only when step 0's "Repo-green gate after changes?" is on — otherwise go straight to step 6. Load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the gate dispatch and its verdict handling.
On `HALT`, stop here — never push broken commits, and never hand-fix a failure the gate returned.

## Step 6: Batch push (main)

After all `apply` clusters are committed, run a single `git push` — no confirmation prompt. Step 1a already verified the PR's branch, and step 5's clusters were each
explicitly approved by the user; pushing them is the batch's completion, not a new decision.

If the push is rejected (remote moved), abort and surface it — the per-cluster commits stand as-is. Ask the user to resolve the divergence manually (never auto-rebase), then
re-attempt only the push, skipping step 5.

## Step 7: Post replies (main)

For **every reply target in every surviving cluster** (apply/answer/drop), post one reply. Loop, don't batch — each reply is permission-gated.

A reply target is one entry of the cluster's `thread_ids`, one top-level comment, or one review-summary body — never an individual comment inside an inline thread, since a
kept thread contributes all its comments (`references/fetch-cluster-propose.md#3e`) and replying per comment would post the same body three times into one thread.

On a permission denial, skip that reply and list it in step 8's report.

On a `gh api` failure, retry once, then skip and list it too — the loop never stops.

### 7a. Reply mechanics — load before the first reply

Templates per action, the `gh api` call per reply-target kind, and the signature rule (mandatory on `apply`/`drop`, none on `answer`) are all in [`references/reply-patterns.md`](references/reply-patterns.md) — load it now,
main reads it directly (never a subagent).

The inverse case — a comment addressed to Claude, answered in Claude's own voice — belongs to `gh-answer-claude-mentions`, not here.

### 7d. Optional refactor + auto-review tails (main, when step 1d's toggle is on)

When the toggle is off, skip to step 8. Otherwise load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the tail-pair dispatch and its arguments.

## Step 8: Final report (main)

Print:

```
PR <n> address summary
- Applied: <count> clusters → <count> commits → pushed as <range>
- Answered: <count> clusters → <count> replies
- Dropped:  <count> clusters → <count> replies
- Skipped (deleted from proposal): <count> clusters
- Reply failures (permission/API skip): <count> targets
- Open threads remaining for you to resolve: <link to PR's "Files changed">
```

When step 5's repo-green gate ran, append its verdict (`GREEN` / `GREEN-WITH-EXCEPTIONS` + Scout/Unclassifiable lists / `HALT` + surviving red). When step 7d ran, append its two report
paths and top findings so the user sees them in the same pass.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
