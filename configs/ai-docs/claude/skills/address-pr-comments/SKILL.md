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

**Ownership** (what `by` matches) is the author of an inline thread's **first comment** (replies never transfer it), of a top-level comment itself, or of a review for its summary body. Rationale: `references/reply-patterns.md`.

**Self-TODO gate (always applied, never a filter you pass):** an item is a candidate only if it is unresolved AND you (`ME`) already replied with `TODO:` somewhere in it.

This mirrors your own review workflow — you triage reviewer comments by hand and leave a `TODO: ...` marking a promised follow-up.

The skill executes those follow-ups; it never replies to fresh, untriaged reviewer comments on your behalf. Full rule: `references/fetch-cluster-propose.md#3d-self-todo-gate-always-applied-before-user-filters`.

Examples: `/address-pr-comments 169`, `/address-pr-comments 169 by alice`, `/address-pr-comments 169 by alice, bob in src/auth`.

## Scope

Operates on one live PR on the current repo's GitHub remote, self-comments included (labeled `(yours)`).

Never resolves threads, requests re-review, dismisses reviews, or touches another PR.

Leaving threads open is deliberate — the user closes them after reviewing the replies.

## Execution (Hybrid)

Subagents can't post replies, commit, or push — permission UIs live in main. Fetching + filtering + clustering is heavy and read-only.

So main runs steps 0–2 and 4–7, while step 3 goes to a background `general-purpose` subagent that returns only the proposal block — raw comment JSON never reaches main.

If it reports zero candidate comments, stop — don't proceed to step 4.

## Run-state file + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` — this run's durable working-state file (`<ts>` = `date +%Y%m%d-%H%M%S`, since the skill can run several times per session).

Persist as produced, never at the end: pre-flight answers first, then each cluster's chosen action, planned change (apply clusters), drop/skip reason, and commit SHA.

When the repo-green gate is on, also persist its baseline and final verdict — never log content — per `references/opt-in-gates.md`.

Once step 4 approves the clusters, create one TaskList task per **applied** cluster — only those produce a commit, which is CLAUDE.md's test for a Task.

Put machine-checkable state (`action`, `commit_sha`, `status`) in the task's `metadata`; keep narrative rationale in the run-state file.

## Standards loaded on demand

Load each as its scope opens, not upfront. Most fire automatically on their description triggers; these explicit load points guard against undertriggering:

- `code-standards` — before production edits in step 5.
- `test-standards` — when touching tests or needing a regression test (step 5).
- `doc-standards` — before editing code comments, docstrings, logs (step 5).
- `debug-standards` — when lint/test fails in step 1c or step 5.
- `commit-standards` — at every commit boundary (step 1b, step 5).

## Step 0: Pre-flight interview (main — before any other step)

Run `git status --porcelain` and probe for lint/test runners with 1c's table (read-only — run nothing yet). Then ask via **one `AskUserQuestion` call**, only the questions whose condition holds — never a freeform chat message.

Each option gets a `description` (what picking it does) and a `preview` (the extra detail behind "what you mean" — dirty-file list, the runner candidates found, what the gate actually runs) so the user can check the detail without a round trip. The recommended option is always first and labeled "(Recommended)", per this project's question-asking convention.

Candidate questions, in priority order (only those whose condition holds are sent):

1. **Dirty tree** (only if `git status --porcelain` printed output) — header `Dirty tree`.
   - `question`: "Working tree has uncommitted changes — what should I do before clustering?"
   - Options: **Commit now (Recommended)** — description: "commit via `commit-standards`, then continue"; preview: the dirty file list. / **Stop here** — description: "abort the skill so you can commit or stash by hand, then re-run"; preview: same file list.
2. **Green baseline check?** (always) — header `Baseline`.
   - `question`: "Record a lint+test baseline before any cluster edit, to catch pre-existing breakage?"
   - Options: **No — skip (Recommended)** — description: "faster; only worth it if the repo might already be red"; preview: "1c is skipped entirely; step 5 still runs whatever gate you pick below." / **Yes — capture baseline** — description: "runs 1c's lint+test probe now, aborts if either is already red"; preview: 1c's runner-discovery table from `references/opt-in-gates.md`.
3. **Green baseline checker** (only if 1c's table matched multiple markers or none — e.g. both `package.json` and `Makefile` present, or neither) — header `Checker cmd`.
   - `question`: "Which lint/test commands should establish the baseline?"
   - Options: one per matched candidate (or the most likely guess when none matched), each showing the exact command in its preview; the user can always type a custom command via the tool's built-in "Other".
   - Only consumed if the previous question ends up "Yes" — send it regardless, ignore it otherwise, rather than a second round-trip.
4. **Repo-green gate after changes?** (always) — header `Green gate`.
   - `question`: "Run the repo's full lint+test suite before the first cluster edit and again before push, fixing any batch-caused regression?"
   - Options: **No — skip (Recommended)** — description: "faster; skip straight to push after commits"; preview: "step 5 goes straight from commits to step 6's push." / **Yes — gate on green** — description: "blocks the push until green; pre-existing red is reported, never fixed"; preview: the gate's baseline/gate mechanics from `references/opt-in-gates.md`.
5. **Refactor + auto-review tails after this batch?** (always) — header `Tails`.
   - `question`: "After pushing, run the refactor + auto-review tail pair over this batch's commit range?"
   - Options: **No — skip (Recommended)** — description: "stop at step 8's report"; preview: "n/a." / **Yes — run tails** — description: "dispatches the shared code-reviewer tail pair, report-only"; preview: `code-reviewer-tail-pair.md`'s scope.

`AskUserQuestion` caps at 4 questions per call. Dirty-tree + baseline + gate + tails already fill 4 slots when the tree is dirty — in that case, send the checker-command question (if its own condition holds) as an immediate second `AskUserQuestion` call, before doing anything else. Otherwise everything fits in one call.

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

Per cluster: `header` = `Cluster N`; `question` = the cluster's short title plus a one-line summary of what it's about. Four options, always in this order, default action first and labeled "(Recommended)":

- **Apply** — description: the subagent's one-line `Planned change`. `preview`: every comment in the cluster (author, `(yours)` if self, file:line, body, url) plus the deduped `Threads` list — this is the "let me check what you mean in more detail" view.
- **Answer** — description: "reply with your own reasoning instead of changing code — pick Other below and type it, since I can't write your answer for you." `preview`: same full comment context as Apply.
- **Drop** — description: the subagent's proposed one-line drop reason. `preview`: same full comment context.
- **Skip** — description: "leave this cluster out entirely — no commit, no reply, thread stays open." `preview`: same full comment context.

`AskUserQuestion` caps at 4 questions per call — batch clusters 4 at a time, issuing consecutive calls back-to-back (no other work interleaved) until every cluster has been asked. This is the "one round" from the user's point of view: every cluster's decision arrives in the same unbroken back-and-forth, just chunked by the tool's own limit.

The tool's built-in "Other" is how the user overrides a default: typed text becomes the `answer_body` (when the picked/implied action is `answer`), a replacement `planned_change` (`apply`), or a custom `drop_reason` (`drop`) — infer which from the text's shape; ask a one-line inline clarification rather than guess when it's genuinely ambiguous.

## Step 4: Parse the AskUserQuestion answers, then create TaskList tasks (main)

For each cluster, map its answer to an `action` (`apply`/`answer`/`drop`; `skip` clusters are dropped from the run entirely, no task, no reply) plus `comment_ids` (`databaseId`), `thread_ids` (the deduped `Threads` line), and `urls` for cross-linking in the commit body.

`thread_ids` drives step 7's replies; `comment_ids` and `urls` stay for the commit body and the top-level reply prefix.

Add `planned_change` on apply clusters (it guides step 5's edit), plus whichever of `drop_reason` or `answer_body` the action needs, from the subagent's default or the user's "Other" text per the rule above.

If a cluster's final action is `answer` and the user picked the plain "Answer" option rather than typing a reply via "Other", the answer body is still missing — the model cannot invent it. Batch these into one follow-up `AskUserQuestion` round (one question per such cluster, `header: Cluster N`, no preset options — the point is to capture free text via "Other"), 4 per call, before proceeding.

**Before touching any code or running any command in step 5**, create one TaskList task per applied cluster — see "Run-state file + TaskList state" above.

This step ends only once every applied cluster has its task.

## Step 5: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below — step 7d's tails review this range.

If step 0's "Repo-green gate after changes?" is on, capture the repo-green baseline now, before the first cluster edit below — see [`references/opt-in-gates.md`](references/opt-in-gates.md).

For each `apply` cluster, **in the order the user left them**:

1. Make the code changes that address the cluster's comments.
2. Stage **only** files relevant to this cluster — see `commit-standards` for the `git add` rules.
3. Commit using `commit-standards` (delegate via the Skill tool), titling it `<type>(<scope>): <cluster title>` and listing the cluster's comment URLs under an `Addresses:` block in the body.

4. Capture the commit SHA into the cluster's TaskList metadata and the run-state file — step 7's reply link needs it.

If a cluster's edits accidentally touch files outside its scope (drift), never silently absorb it.

Pause and ask the user whether to split it into a separate `[Drift]` commit per CLAUDE.md, or bundle it if trivial.

Either answer only decides where the drift fix commits; the cluster's own flow then resumes.

### Repo-green gate (opt-in, after all apply clusters are committed, before step 6's push)

Runs only when step 0's "Repo-green gate after changes?" is on — otherwise go straight to step 6.

Load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the gate dispatch and its verdict handling. On `HALT`, stop here — never push broken commits, and never hand-fix a failure the gate returned.

## Step 6: Batch push (main)

After all `apply` clusters are committed, run a single `git push` — no confirmation prompt. Step 1a already verified the PR's branch is the current branch, and step 5's clusters were each explicitly approved by the user; pushing them is the batch's completion, not a new decision.

If the push is rejected (remote moved), abort and surface it — the per-cluster commits stand as-is.

Ask the user to resolve the divergence manually (never auto-rebase), then re-attempt only the push, skipping step 5.

## Step 7: Post replies (main)

For **every reply target in every surviving cluster** (apply/answer/drop), post one reply. Loop, don't batch — each reply is permission-gated.

A reply target is one entry of the cluster's `thread_ids`, one top-level comment, or one review-summary body — never an individual comment inside an inline thread.

Threads are the unit because a kept thread contributes all its comments (`references/fetch-cluster-propose.md#3e`); replying per comment would post the same body three times into one thread.

On a permission denial, skip that reply and list it in step 8's report.

On a `gh api` failure, retry once, then skip and list it too — the loop never stops.

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

### 7b. Reply API per reply target

**Inline** — one GraphQL mutation per `thread_id`:

```bash
gh api graphql -f query='
mutation($tid: ID!, $body: String!) {
  addPullRequestReviewThreadReply(
    input: { pullRequestReviewThreadId: $tid, body: $body }
  ) { comment { url } }
}' -f tid="<thread_id>" -f body="<reply_body>"
```

The mutation takes a thread, not a comment, so the duplicate-reply mistake is unrepresentable rather than merely forbidden.

**Top-level and review-summary** — REST, since GitHub exposes no thread object for either:

| Source | gh command |
|---|---|
| top-level | `gh api -X POST repos/$OWNER_REPO/issues/<n>/comments -f body='@<author> re: <comment_url> — <body>'` |
| review-summary | same as top-level (no per-review reply API) |

That `@<author> re: <link>` prefix pings the commenter and preserves thread context.

These post a fresh conversation comment rather than threading. That is GitHub's model, not a shortcut — no API threads them.

### 7c. Signature rules — split by action

`apply` and `drop` replies carry the AI signature **mandatorily**; `answer` replies carry **none**.

An answer is the user's reasoning in the user's voice, and an AI tag dilutes that ownership (see `references/reply-patterns.md`).

The inverse case — a comment addressed to Claude, answered in Claude's own voice — belongs to `gh-answer-claude-mentions`, not here.

Signature literal: `_via Claude Code (`address-pr-comments`)_`. Plain text only — the global no-emoji rule applies to posted replies too.

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

When step 5's repo-green gate ran, append its verdict (`GREEN` / `GREEN-WITH-EXCEPTIONS` + Scout/Unclassifiable lists / `HALT` + surviving red) to this summary.

When step 7d ran, append its two report paths and top findings to this summary so the user sees them in the same pass.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
