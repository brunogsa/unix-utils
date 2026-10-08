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

**Self-AI gate (always applied, never a filter you pass):** an item is a candidate only if unresolved AND you (`ME`) already replied with `AI:` somewhere in it - your own marker for a promised follow-up.

The marker is `AI:`, not `TODO:`, so humans read it as a note to your AI. The skill executes those follow-ups, never replying to untriaged comments. Full rule: `references/fetch-cluster-propose.md#3d-self-ai-gate-always-applied-before-user-filters`.

**CRITICAL - an `AI:` note is a PR-wide rule.** You leave it once, on one spot, and it binds every line this PR adds or changes - never just the thread it sits in.

Applying a cluster fixes every site with the same problem: step 3's subagent finds them (`references/fetch-cluster-propose.md#pr-wide-sweep-apply-clusters`), step 5 edits them all.

Examples: `/address-pr-comments 169`, `/address-pr-comments 169 by alice, bob in src/auth`.

## Scope

One live PR on the current repo's GitHub remote, self-comments included (labeled `(yours)`). Never resolves threads, requests re-review, dismisses reviews, or touches another PR - the user closes threads after reviewing the replies.

## Execution (Hybrid)

Subagents can't post replies, commit, or push (permission UIs live in main). Main runs steps 0-2 and 4-7; step 3's read-only fetch and clustering goes to a background subagent that returns only the proposal block.

If it reports zero candidate comments, stop before step 4.

## Run-state file + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` as this run's working-state file (`<ts>` = `date +%Y%m%d-%H%M%S`).

Persist as produced, never at the end: pre-flight answers, then each cluster's action, planned change (apply), drop/skip reason, and commit SHA.

When the repo-green gate is on, also persist its baseline and final verdict - never log content - per `references/opt-in-gates.md`.

Once step 4 approves the clusters, create one TaskList task per **applied** cluster (only those produce a commit). Put machine-checkable state (`action`, `commit_sha`, `status`) in the task's `metadata`; keep narrative rationale in the run-state file.

## Standards loaded on demand

Load each as its scope opens, not upfront:

- `code-standards` - before production edits in step 5.
- `test-standards` - when touching or adding tests (step 5).
- `doc-standards` - before editing comments, docstrings, logs (step 5).
- `debug-standards` - when lint/test fails in step 1c or 5.
- `commit-standards` - at every commit boundary (steps 1b, 5).

## Step 0: Pre-flight interview (main - before any other step)

Ask via **one `AskUserQuestion` call** of up to 5 candidate questions (dirty tree, baseline, checker cmd, green gate, tails) - only those whose condition holds, never freeform chat. Conditions, wording, options, batching: [`references/preflight-interview.md`](references/preflight-interview.md) - load it now.

## Step 1: Validate preconditions (main)

Run 1a-1d in order, fail-fast on the first failure (1c only when step 0 opted in). On a failure, abort with the suggested fix - never recover automatically.

### 1a. On the PR's branch

```bash
PR_BRANCH=$(gh pr view <n> --json headRefName -q .headRefName)
CUR_BRANCH=$(git branch --show-current)
```

If `PR_BRANCH != CUR_BRANCH`, abort:
> Not on PR branch. Run: `gh pr checkout <n>`

### 1b. Clean working tree

Step 0's persisted answer decides (`commit_now`, `proceed_without_committing`, `stop_here`) - mechanics in `references/preflight-interview.md`'s row 1.

### 1c. Green baseline (lint + test - opt-in)

On a yes to step 0's "Green baseline check?", load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the runner table and abort rule. Otherwise skip to 1d.

### 1d. Tails toggle

Not a pass/fail check - read step 0's persisted tails answer (consumed by step 7d). Default no if unanswered.

## Step 2: Resolve repo + own login (main)

```bash
OWNER_REPO=$(gh repo view --json owner,name -q '.owner.login + "/" + .name')
ME=$(gh api user -q .login)
```

Both go into the step-3 dispatch prompt - main never fetches comments itself. `ME` powers the `(yours)` label, not a filter.

## Step 3: Fetch, filter, cluster, rank, propose (subagent)

Dispatch `agent(subAgent=general-purpose, title=Fetch, cluster, and rank PR review comments, model=sonnet, effort=high)` in the background with this prompt, filling in `<n>`, `OWNER_REPO`, `ME`, and the parsed filters:

```
Read ~/.claude/skills/address-pr-comments/references/fetch-cluster-propose.md
and execute it yourself for PR <n> in <OWNER_REPO>, emitting the proposal
block in the exact format its final section gives. Ignore SKILL.md's other
steps - they run in the caller's session.

ME="<ME>". Filters: by=<logins or "none">, in=<paths or "none">.

Mark each comment's is_self = (author == ME); label it (yours) per the
proposal-block format. If nothing survives the filters, report zero
matches and stop - don't cluster.

Return ONLY the proposal block - never the raw fetched JSON.
```

Subsections 3a-3g live in `references/fetch-cluster-propose.md`; only the subagent reads them.

## Output: preview every cluster, then ask

The subagent returns per-cluster data in `references/fetch-cluster-propose.md`'s 3g format - main never relays it raw. Load [`references/reply-patterns.md`](references/reply-patterns.md) now: the previews quote its reply templates and signature rule.

**Preview first.** Before the first `AskUserQuestion`, print this block in chat for every cluster, so the user sees what each choice does to the code and the thread:

```
### Cluster N: <short title> (default: <action>)
- (<author>) <path:line> - <comment gist>, one line per comment
- Apply → <Rule>
  - <path:line> - <before → after, or short pseudocode>, one line per site
  - reply: <apply template, with <commit-url> as placeholder>
- Answer → reply: <Draft answer, signed>
- Drop → reply: <drop template with the proposed reason>
- Skip → no commit, no reply, thread stays open
```

A cluster with no `Planned change` (a question) shows `Apply → no change proposed - describe one via Other`.

**Then ask.** One question per cluster: `header` = `Cluster N`; `question` = the cluster's short title plus a one-line summary. Four options, always in this order, default first and labeled "(Recommended)". Each option's `preview` is the comment lines plus that option's own lines from the block above:

- **Apply** - description: the subagent's one-line `Planned change`.
- **Answer** - description: "post the drafted answer, signed - or type your own via Other, posted unsigned."
- **Drop** - description: the subagent's proposed one-line drop reason.
- **Skip** - description: "leave this cluster out entirely - no commit, no reply, thread stays open."

`AskUserQuestion` caps at 4 per call - batch clusters 4 at a time, in back-to-back calls until every cluster is asked, as one unbroken round.

The built-in "Other" overrides a default: typed text becomes the `answer_body` (`answer`, posted unsigned), a replacement `planned_change` or `rule` (`apply`), or a custom `drop_reason` (`drop`) - infer which from the text's shape; ask a one-line clarification only when genuinely ambiguous.

## Step 4: Parse the AskUserQuestion answers, then create TaskList tasks (main)

For each cluster, map its answer to an `action` (`apply`/`answer`/`drop`; `skip` clusters get no task, no reply) plus `comment_ids` (`databaseId`), `thread_ids` (the deduped `Threads` line), and `urls`. `thread_ids` drives step 7's replies; `comment_ids`/`urls` feed the commit body and top-level reply prefix.

Add `planned_change`, `rule`, and `sites` on apply clusters (they guide step 5's edit), plus the `drop_reason` or `answer_body` the action needs, from the subagent's default or the user's "Other" text.

On an `answer` cluster, record `answer_source`: `draft` when the user picked plain "Answer", `user` when they typed via "Other" - step 7's signature rule reads it.

A plain "Answer" on a cluster with no `Draft answer` leaves nothing to post - ask for those texts in one follow-up `AskUserQuestion` round, 4 per call.

**Before touching any code in step 5**, create one TaskList task per applied cluster - see "Run-state file + TaskList state". This step ends only once every applied cluster has its task.

## Step 5: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below - step 7d's tails review this range. If step 0's "Repo-green gate after changes?" is on, capture the repo-green baseline now, before the first cluster edit - see [`references/opt-in-gates.md`](references/opt-in-gates.md).

For each `apply` cluster, **in the order the user left them**:

1. Edit every entry of the cluster's `sites`, not only the commented lines. Locate each by its content, not its line number - earlier cluster commits shift lines.

   A site whose content no longer matches is skipped and listed in step 8.

2. Stage **only** files relevant to this cluster - see `commit-standards` for the `git add` rules.

3. Commit using `commit-standards` (via Skill tool), titling it `<type>(<scope>): <cluster title>`.

   Its body lists the cluster's comment URLs under an `Addresses:` block and its edited sites under a `Sites:` block.

4. Capture the commit SHA into the cluster's TaskList metadata and the run-state file - step 7's reply link needs it.

If a cluster's edits touch files outside its scope (drift), never silently absorb it - ask whether to split it into a separate `[Drift]` commit per CLAUDE.md or bundle it if trivial. Either way the cluster's own flow then resumes.

### Repo-green gate (opt-in, after all apply clusters are committed, before step 6's push)

Runs only when step 0's "Repo-green gate after changes?" is on - otherwise go straight to step 6. Load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the gate dispatch and verdict handling. On `HALT`, stop here - never push broken commits, and never hand-fix a failure the gate returned.

## Step 6: Batch push (main)

After all `apply` clusters are committed, run a single `git push` - no confirmation prompt. Step 1a verified the branch and the user approved each cluster, so the push is the batch's completion, not a new decision.

If the push is rejected (remote moved), abort and surface it - the commits stand. Ask the user to resolve the divergence manually (never auto-rebase), then re-attempt only the push, skipping step 5.

## Step 7: Post replies (main)

For **every reply target in every surviving cluster** (apply/answer/drop), post one reply. Loop, don't batch - each reply is permission-gated.

A reply target is one entry of the cluster's `thread_ids`, one top-level comment, or one review-summary body - never an individual comment inside an inline thread, or the same body posts several times.

On a permission denial, skip that reply and list it in step 8's report. On a `gh api` failure, retry once, then skip and list it too - the loop never stops.

### 7a. Reply mechanics - load before the first reply

Templates per action, the `gh api` call per reply-target kind, and the signature rule (none only on an answer the user typed) are in [`references/reply-patterns.md`](references/reply-patterns.md) - reload it if a compaction dropped it. Main reads it directly, never a subagent.

The inverse case - a comment addressed to Claude, answered in Claude's own voice - belongs to `gh-answer-claude-mentions`, not here.

### 7d. Optional refactor + auto-review tails (main, when step 1d's toggle is on)

When the toggle is off, skip to step 8. Otherwise load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the tail-pair dispatch and its arguments.

## Step 8: Final report (main)

Print:

```
PR <n> address summary
- Applied: <count> clusters → <count> commits → pushed as <range>
- Sites skipped (content no longer matched): <path:line list, or none>
- Answered: <count> clusters → <count> replies
- Dropped:  <count> clusters → <count> replies
- Skipped (deleted from proposal): <count> clusters
- Reply failures (permission/API skip): <count> targets
- Open threads remaining for you to resolve: <link to PR's "Files changed">
```

When step 5's repo-green gate ran, append its verdict (`GREEN` / `GREEN-WITH-EXCEPTIONS` + Scout/Unclassifiable lists / `HALT` + surviving red). When step 7d ran, append its two report paths and top findings so the user sees them in the same pass.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative; regenerate it whenever the flow changes.
