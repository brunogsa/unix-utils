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

**Self-AI gate (always applied, never a filter you pass):** an item is a candidate only if unresolved AND you (`ME`) already left a marked note in it. `AI!: <msg>` is a command and `AI?: <msg>` is a question; a bare legacy `AI:` is an alias of `AI!`.

Match the prefix case-insensitively, colon optional - the same semantics as `address-ai-comments`' "Marker semantics". The marker is not `TODO:`, so humans read it as a note to your AI, and untriaged comments never get a reply. Full rule: `references/fetch-cluster-propose.md#3d-self-ai-gate-always-applied-before-user-filters`.

**CRITICAL - an `AI!` note is a PR-wide rule.** You leave it once, on one spot, and it binds every line this PR adds or changes - never just the thread it sits in.

Applying a cluster fixes every site with the same problem: step 3's subagent finds them (`references/fetch-cluster-propose.md#pr-wide-sweep-apply-clusters`), step 7 edits them all. An `AI?` is answered, never swept.

Examples: `/address-pr-comments 169`, `/address-pr-comments 169 by alice, bob in src/auth`.

## Scope

One live PR on the current repo's GitHub remote, self-comments included (labeled `(yours)`). Never resolves threads, requests re-review, dismisses reviews, or touches another PR - the user closes threads after reviewing the replies.

## Execution (Hybrid)

Subagents can't post replies, commit, or push (permission UIs live in main). Main runs steps 0-2 and 4-7; step 3's read-only fetch and clustering goes to a background subagent that returns only the proposal block.

If it reports zero candidate comments, stop before step 4.

## Run-state file + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` as this run's working-state file (`<ts>` = `date +%Y%m%d-%H%M%S`).

Persist as produced, never at the end: pre-flight answers, then each cluster's action, planned change (apply), drop reason, reply text, and commit SHA.

When the repo-green gate is on, also persist its baseline and final verdict - never log content - per `references/opt-in-gates.md`.

Step 4 creates the TaskList. Put machine-checkable state (`action`, `commit_sha`, `status`, `kind`) in each task's `metadata`; keep narrative rationale in the run-state file.

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

Not a pass/fail check - read step 0's persisted tails answer (consumed by step 7b). Default no if unanswered.

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

## Step 4: Create the TaskList (main)

The subagent returns per-cluster data in `references/fetch-cluster-propose.md`'s 3g format - main never relays it raw. Right after it returns, before any chat or edit, create the TaskList so the debate and the plan share one durable ledger that survives compaction.

- One parent `[Task]` per cluster, titled with the cluster's short title.
- Under it, one `[Sub-Step]` per marker, with `metadata.kind` = `command` or `question` from the proposal's `[kind: ...]` tag.
- Put the cluster's `comment_ids` (`databaseId`), `thread_ids` (the deduped `Threads` line) and `urls` in the parent's `metadata`: `thread_ids` drives the reply step, `comment_ids`/`urls` feed the commit body and top-level reply prefix.

A parent with no commit of its own (an answer-only cluster) still gets a `[Task]`: it is the one handle the reply and the final report hang on.

This step ends only once every marker has its sub-step.

## Step 5: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below - step 7b's tails review this range. If step 0's "Repo-green gate after changes?" is on, capture the repo-green baseline now, before the first cluster edit - see [`references/opt-in-gates.md`](references/opt-in-gates.md).

For each `apply` cluster, **in the order the user left them**:

1. Edit every entry of the cluster's `sites`, not only the commented lines. Locate each by its content, not its line number - earlier cluster commits shift lines.

   A site whose content no longer matches is skipped and listed in step 8.

2. Stage **only** files relevant to this cluster - see `commit-standards` for the `git add` rules.

3. Commit using `commit-standards` (via Skill tool), titling it `<type>(<scope>): <cluster title>`.

   Its body lists the cluster's comment URLs under an `Addresses:` block and its edited sites under a `Sites:` block.

   Leave a blank line between the `Addresses:` label and its first URL - commitlint reads a URL's `#discussion_r…` fragment as an issue reference that starts the footer, and warns `footer-leading-blank` when no blank line precedes it.

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

### 7b. Optional refactor + auto-review tails (main, when step 1d's toggle is on)

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

When step 5's repo-green gate ran, append its verdict (`GREEN` / `GREEN-WITH-EXCEPTIONS` + Scout/Unclassifiable lists / `HALT` + surviving red). When step 7b ran, append its two report paths and top findings so the user sees them in the same pass.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative; regenerate it whenever the flow changes.
