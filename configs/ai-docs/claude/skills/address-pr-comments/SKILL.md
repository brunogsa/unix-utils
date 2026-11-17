---
name: address-pr-comments
description: "Address unresolved PR review comments end-to-end: fetch (filter by author/file) → semantic cluster → TaskList → Q&A debate → subagent plan → commit-per-cluster → batch push → AI-signed inline replies."
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

**Self-AI gate (always applied, not a passed filter):** an item is a candidate only if unresolved, not answered by a later reply of yours, AND you (`ME`) left a marked note in it. `AI!: <msg>` is a command and `AI?: <msg>` is a question; a bare legacy `AI:` is an alias of `AI!`.

Humans read the marker as a note to your AI, and untriaged comments never get a reply. Full rule: `references/self-ai-gate.md`.

**CRITICAL - an `AI!` note is a PR-wide rule.** You leave it once, on one spot, and it binds every line this PR adds or changes - never just the thread it sits in.

Applying a cluster fixes every site with the same problem: step 3's subagent finds them (`references/fetch-cluster-propose.md#pr-wide-sweep-apply-clusters`), step 7 edits them all. An `AI?` is answered, never swept.

Examples: `/address-pr-comments 169`, `/address-pr-comments 169 by alice, bob in src/auth`.

## Scope

One live PR on the current repo's GitHub remote, self-comments included (labeled `(yours)`). Never resolves threads, requests re-review, dismisses reviews, or touches another PR; the user closes threads.

## Execution (Hybrid)

Subagents can't post replies, commit, or push (permission UIs live in main). Main runs every step except two drafts: step 3's read-only fetch and clustering goes to a background subagent returning only the proposal block, and step 6's plan to a Plan subagent that main then checks.

If step 3 reports zero candidate comments, stop before step 4.

Once step 5's debate closes the run asks the user nothing (they may be away): a rule below decides every later fork.

## Run-state file + TaskList state

At skill start, create `/tmp/address-pr-comments_<session_id>_<ts>.json` as this run's working-state file (`<ts>` = `date +%Y%m%d-%H%M%S`).

Persist as produced, never at the end: pre-flight answers, then each cluster's title, action, marker kinds, planned change, Rule and Sites as the debate leaves them (apply), drop reason, reply text, step 6's checked plan, and commit SHA. Step 6's subagent takes every decision from this file alone, so one missing here is missing from the plan.

When the repo-green gate is on, also persist its baseline and final verdict - never log content - per `references/opt-in-gates.md`.

Step 4 creates the TaskList. Put machine-checkable state (`action`, `commit_sha`, `status`, `kind`) in each task's `metadata`; keep narrative rationale in the run-state file.

## Step 0: Pre-flight interview (main - before any other step)

Ask via `AskUserQuestion` up to 6 candidate questions (branch switch, dirty tree, baseline, checker cmd, green gate, tails) - only those whose condition holds, never freeform chat. One call holds 4, so more than 4 take a second call. Probes, conditions, wording, options, batching: [`references/preflight-interview.md`](references/preflight-interview.md) - load it now.

## Step 1: Validate preconditions (main)

Run 1a-1d in order, fail-fast on the first failure (1c only when step 0 opted in). On a failure, abort with the suggested fix. The one recovery is the branch switch the user approved in step 0.

### 1a. Clean working tree

If step 0's branch answer is `stop_here`, abort now with the message in `references/branch-switch.md`, before committing anything.

Otherwise step 0's persisted dirty-tree answer decides (`commit_now`, `proceed_without_committing`, `stop_here`) - mechanics in `references/preflight-interview.md`'s row 1.

### 1b. On the PR's branch

```bash
PR_BRANCH=$(gh pr view <n> --json headRefName -q .headRefName)
CUR_BRANCH=$(git branch --show-current)
```

If `PR_BRANCH != CUR_BRANCH`, load [`references/branch-switch.md`](references/branch-switch.md): step 0's persisted branch answer decides whether to switch or abort.

### 1c. Green baseline (lint + test - opt-in)

On a yes to step 0's "Green baseline check?", load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the runner table and abort rule.

### 1d. Tails toggle

Not a pass/fail check - read step 0's persisted tails answer. Default no if unanswered.

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

On 1+ candidates, launch `/improve-from-user PR <OWNER_REPO>#<n>` per `~/.claude/skills/improve-from-user/references/lateral-learn.md`, in step 4's message.

## Step 4: Create the TaskList (main)

The subagent returns per-cluster data in `references/fetch-cluster-propose.md`'s 3g format - main never relays it raw. Right after it returns, before any chat or edit, create the TaskList so the ledger survives compaction.

- One parent `[Task]` per cluster, titled with the cluster's short title.
- Under it, one `[Sub-Step]` per marker, with `metadata.kind` = `command` or `question` from the proposal's `[kind: ...]` tag.
- Put the cluster's `comment_ids` (`databaseId`), `thread_ids` (the deduped `Threads` line) and `urls` in the parent's `metadata`: `thread_ids` drives the reply step, `comment_ids`/`urls` feed the commit body and top-level reply prefix.

A parent with no commit of its own (an answer-only cluster) still gets a `[Task]`: it is the one handle the reply and the final report hang on.

This step ends only once every marker has its sub-step.

## Step 5: Q&A + debate (main, in chat)

Send one message (the order `address-ai-comments` step 4 uses) that answers **every** `AI?` first, from its `Draft answer`, then challenges each `AI!` you disagree with, seeded by its `Concern:`. Tie each item to its `path:line`. List the proposal's `Dropped as already answered` items; one the user names by number or URL is a candidate again.

It also lists every `apply` cluster's Rule and Sites, contested or not, and ends by saying that closing the debate approves every commit, the push and every reply.

The user wants to be challenged: a command that looks wrong, over-reaching, or already handled gets named out loud, never quietly queued.

Debate rules:

- Mark a question's sub-step done only when the user says it is clear, since an unread answer gets misstated in the reply.

- A bare "ok" while several items are open gets a clarifying question naming the open items - never a guess at which one it closes.

- A conclusion the user names ("change X", "tell the reviewer Y", "drop it") becomes a planned command or reply right away, persisted to the run-state file, with no GitHub round-trip.

- That conclusion gets its own `[Sub-Step]` under the cluster's `[Task]`.

- Leave only on a user reply that comes once every question is done and no challenge is open - even with nothing to debate, since that reply is the approval.

That close is the user's last look and the single gate for those irreversible writes: `settings.json` runs bypassPermissions, so none fires a prompt.

## Step 6: Plan subagent (dispatched by main)

Dispatch `agent(subAgent=Plan, title=Draft the PR comment address plan, model=sonnet, effort=medium)` in the foreground - sonnet, since it composes reply previews - with this prompt:

```
Read ~/.claude/skills/address-pr-comments/references/plan-draft.md and
follow it for the run-state file <absolute run-state path>.
```

Nobody else reviews the plan, so check it against the run-state file: the same clusters, intents and `apply` Sites, and a reply preview or "no reply - <reason>" on every `AI?` cluster.

Fix a mismatch from that file; if the agent errors or returns no plan, build the plan from it in main - never re-dispatch or ask.

Persist the checked plan to the run-state file, where steps 7, 9 and 10 re-read it after a compaction, then post one chat line - `next: commits, push, replies per the plan in <run-state path>` - and start step 7.

## Step 7: Per-cluster commits (main, applied clusters only)

If step 1d's toggle is on, capture `BATCH_BASE_SHA=$(git rev-parse HEAD)` before the first commit below - step 9b's tails review this range. If step 0's "Repo-green gate after changes?" is on, capture the repo-green baseline now, before the first cluster edit - see [`references/opt-in-gates.md`](references/opt-in-gates.md).

For each `apply` cluster, **in the plan's order**:

1. Edit every entry of the cluster's `sites`, not only the commented lines. Locate each by its content, not its line number - earlier cluster commits shift lines.

   A site whose content no longer matches is skipped and listed in step 10.

2. Stage **only** files relevant to this cluster - see `commit-standards` for the `git add` rules.

3. Commit using `commit-standards` (via Skill tool), titling it `<type>(<scope>): <cluster title>`.

   Its body lists the cluster's comment URLs under an `Addresses:` block and its edited sites under a `Sites:` block.

   Leave a blank line between the `Addresses:` label and its first URL - commitlint reads a URL's `#discussion_r…` fragment as an issue reference that starts the footer, and warns `footer-leading-blank` when no blank line precedes it.

4. Capture the commit SHA into the cluster's TaskList metadata and the run-state file - step 9's reply link needs it. Mark the cluster's command sub-steps done.

If a cluster's edits touch files outside its scope (drift), always split them into a separate `[Drift]` commit per the `task-breakdown` skill and list it in step 10's report. The user is away, and a separate commit stays revertable.

### Repo-green gate (opt-in, after all apply clusters are committed, before step 8's push)

Runs only when step 0's "Repo-green gate after changes?" is on - otherwise go straight to step 8. Load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the gate dispatch and verdict handling. On `HALT`, stop here - never push broken commits, and never hand-fix a failure the gate returned.

## Step 8: Batch push (main)

After all `apply` clusters are committed, run a single `git push` - no confirmation prompt. Step 5's debate close covered the push.

If the push is rejected (remote moved), abort and surface it - the commits stand. Never auto-rebase: the user resolves the divergence manually, then only the push is re-attempted, skipping step 7.

## Step 9: Post replies (main)

Before the first reply, load [`references/reply-patterns.md`](references/reply-patterns.md) - step 6's subagent read never reached main - and reload it if a compaction dropped it. It holds the reply loop, templates, `gh api` calls and the signature rule.

### 9b. Optional refactor + auto-review tails (main, when step 1d's toggle is on)

When the toggle is off, skip to step 10. Otherwise load [`references/opt-in-gates.md`](references/opt-in-gates.md) for the tail-pair dispatch and its arguments.

## Step 10: Final report (main)

Print:

```
PR <n> address summary
- Applied: <count> clusters → <count> commits → pushed as <range>
- Sites skipped (content no longer matched): <path:line list, or none>
- Answered: <count> clusters → <count> replies
- Dropped:  <count> clusters → <count> replies
- No reply (per plan): <count> clusters
- Drift commits: <SHA list, or none>
- Reply failures: <target URL + unposted reply text, or none>
- Open threads remaining for you to resolve: <link to PR's "Files changed">
```

When step 7's repo-green gate ran, append its verdict (`GREEN` / `GREEN-WITH-EXCEPTIONS` + Scout/Unclassifiable lists / `HALT` + surviving red). When step 9b ran, append its two report paths and top findings.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative; regenerate it whenever the flow changes.
