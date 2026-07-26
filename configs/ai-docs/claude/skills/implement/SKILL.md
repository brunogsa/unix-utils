---
name: implement
description: "Execute plan_<slug>.md tasks end-to-end as fresh-context subagents, fully async. Trigger: /implement <id(s)> or natural language (\"let's implement that\", \"implement this plan\") when a plan_<slug>.md exists."
disable-model-invocation: false
words-budget: 5096
---

## Usage

```
/implement <task-ids> | <PR-label(s)>
```

`<task-ids>` is one numeric task prefix or a comma-list of them — `5`, or `1, 2, 3` from `plan_<slug>.md` in CWD. 1 space after commas.
Each ID matches the **exact** numeric prefix of a plan_<slug>.md heading. On ambiguity (rare), ask the user.

`<PR-label(s)>` is `PR-N` or a comma-list — `PR-1`, or `PR-1, PR-2` — from the plan's PR Breakdown, same comma-space convention. Resolves to its own task-id list.
See [`references/pr-awareness.md`](references/pr-awareness.md), loaded whenever the arg is a PR-label.

## Execution model — orchestrator + per-task subagents

`/implement` is **fully async**: it runs the whole batch unattended, handing you the finished commits to review in one pass.

There is no per-task human handshake — your batch-end review is the handshake.

Two roles:

- **Orchestrator** (this session) — pre-flight, TaskList, dispatch, post-commit verification, batch-end report.
  Holds only orchestration state, never task implementation context.
  It is also the **only** role that spawns subagents; a task subagent never nests another one.

- **Task subagent** — one fresh context per task, sequential: decompose into its own checklist file, RED-GREEN work, self-verify, commit, report.
  Each re-grounds from durable artifacts (plan_<slug>.md, spec_<slug>.md, `git log`), not session history.

Run subagents on **Sonnet** (execution is mechanical); keep orchestrator on stronger model. Tasks run **sequentially** — each reads the prior task's commits + plan_<slug>.md notes first.

### A PR-label run is the same batch flow, repeated once per PR

`/implement PR-1, PR-2` resolves each label to its own task-id list, then runs the **whole** batch flow — §1.4 through §9 — once per PR, strictly in the order given.

Only four steps are shared by the whole list and never repeat: §1.1 (locate plan/spec), §1.2 (interview), §1.3 (worktree setup), and §2 (TaskList seeding, which seeds every PR's entries upfront).

Each PR's own iteration then runs in this order: resolve its label → capture its `BATCH_BASE_SHA` (§1.4) → decide and create its branch.
From there: its task loop (§3–§7) → its gate (§8) → its batch-end and PR (§9).

So every PR's gate, tails, diff range, and PR body scope to that PR's own commits alone, never the whole list's.

Read this once here rather than as a caveat on each step below; the sections that follow assume it and don't restate it.

**Fail-fast between PRs:** proceed to the next PR only when every one of the current PR's tasks reached `[Done]` and §9.1's repo-green gate passed. Otherwise stop — the remaining PRs stay untouched.

Label resolution, branch creation, and manifest writes live in [`references/pr-awareness.md`](references/pr-awareness.md). Load it when the arg is a PR-label; a plain `<task-ids>` run never does.

### Chain-abort, with no human gate

A good spec/plan — required for any `/implement` run — makes mid-batch stalls almost never fire. When one does:

- **Subagent blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision):
  - Record it, **never guess past it**, leave that task where it stopped, and continue with tasks that don't depend on it.
  - Every block lands in the batch-end report for you to clear in one pass.

- **Subagent's own work fails the orchestrator's post-commit verification** → re-dispatch the same task with the failure as feedback; the verdict script decides how many attempts it gets (§5.2).
  - Surface it only if it still fails. Execution correctness is the AI's job, not yours.

## 1. Pre-flight (orchestrator)

The up-front interview (§1.2) asks whether this run creates its own git worktree.
On yes, §1.3 creates and populates it.
On no, this skill runs in the current checkout, and never merges or deletes a worktree on its own either way.

In a multi-task batch (`/implement 1, 2, 3`), **§1.1–§1.5 and §2 run once** at the start; **§1.6–§1.7 run once per task** as each becomes active.

### 1.1. Locate the plan (and spec)

Glob in CWD (top-level only):

```bash
ls -1 plan_*.md spec_*.md 2>/dev/null
```

Resolve candidates with this decision tree — it only gathers candidates, never prompts; an ambiguous match becomes the interview's plan-pick question (§1.2):

- **Exactly one plan and one spec** → use both; print the resolved paths, no prompt.
- **Multiple plans (or multiple specs)** → the interview's plan-pick question lists the matches numbered; pair each plan with the spec sharing its `<slug>` when one exists.
- **No plan found** → the interview asks for the path. If none provided, **stop**.
- **Plan but no spec** → proceed plan-only; the spec is optional context.

Everywhere below, `plan_<slug>.md` / `spec_<slug>.md` refer to these resolved paths.

### 1.2. One up-front interview

Ask everything at once, in a single message, before any dispatch.
This is the only round of questions until the review package.
Rare exceptions: §1.6's task-id disambiguation and §1.7's resume/dirty-run prompts — task-activation checks outside this interview.
Mid-run `.env` needs are self-served (copy from the original checkout) rather than asked.

- **Plan pick**, only when §1.1 found multiple candidates.
- **Run in a git worktree?** (yes/no) — on yes, §1.3 creates it from HEAD and symlinks files in.
- **Open a draft PR at batch end?** (yes/no).
- **Run refactor + auto-review batch-end tails?** (yes/no, default yes) — no skips §9.2–§9.4; §9.1's gate always runs.
- **Base-branch confirmation** — show `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` as the default; let the user confirm or override.

Record all answers (four, or five with plan-pick) before proceeding — §1.5 persists them to the state file.

### 1.3. Worktree setup (only when §1.2 answered yes)

Creation and file-symlink mechanics live in [`references/worktree-setup.md`](references/worktree-setup.md). Load when §1.2 answered yes.

When §1.2 answered no, skip this step; the batch-end package omits the merge-back reminder, since no worktree exists to merge back.

### 1.4. Recap of work since base + capture `BATCH_BASE_SHA`

Capture HEAD as `BATCH_BASE_SHA` — the start of this invocation's commit range (reused in §4, §8, and §9).
Capture it **after** §1.3, so a new worktree's HEAD (same commit, different working directory) is what gets recorded.

Read **full commit messages** and give a 3–5 line summary. Don't dump the log; subagents re-derive context from `git log` at dispatch.

### 1.5. State-file init (and resume adoption)

Check for an existing state file belonging to this `<slug>` **and** this run's `<pr_label>` (`""` for a plain task-id run, else the resolved `PR-N`):

```bash
jq -r --arg slug "<slug>" --arg pr "<pr_label>" \
  'select(.slug == $slug and ((.pr_label // "") == $pr)) | input_filename' \
  /tmp/implement_*.json 2>/dev/null
```

`// ""` matches a pre-change file with no `pr_label` key against a plain task-id run's empty `<pr_label>` — see `references/preflight-state.md`.

- **None found** → create `/tmp/implement_<session_id>.json` with exactly this shape:

```json
{
  "version": 1,
  "session_id": "<session_id>",
  "slug": "<slug>",
  "pr_label": "",
  "phase": "tasks",
  "batch_base_sha": "<BATCH_BASE_SHA>",
  "tasks": [{ "id": "1", "status": "pending" }],
  "attempts": [],
  "gate_dispatches": 0,
  "tails": { "wanted": true, "refactor_report": "", "auto_review_report": "" },
  "worktree": { "created": false, "path": "", "branch": "" },
  "pr": { "wanted": false }
}
```

- One `tasks[]` entry per matched task-id (`status: "pending"`); `worktree`/`pr`/`tails.wanted` filled from §1.2's answers.
  - `pr_label` is `""` for a plain `<task-ids>` run, else the `PR-N` this file belongs to (`references/pr-awareness.md`).
  - §5.2/§5.4 append `attempts[]` entries as `{ "task", "n", "result", "signature", "at" }`.
- **Found** → load [`references/preflight-state.md`](references/preflight-state.md) for the JSON-adoption mechanics that restore attempt counts and completed-task status.

### 1.6. Match `<task-id>`

Exact-match against numeric prefixes in `plan_<slug>.md` headings. On multiple matches (rare), ask the user which one.

### 1.7. Existing state (resume / dirty runs)

On a resume or re-run, reconcile any pre-existing task status and stray TaskList items before proceeding.
A clean first run skips this.
The reconciliation mechanics live in [`references/resume-reconcile.md`](references/resume-reconcile.md) — how this differs from §1.5's silent JSON adoption, and the per-state prompts (re-execute / resume / restart / revive).
Load it only on a resume or dirty run.

### 1.8. Resolve the PR-labels (only when the arg is a PR-label)

Resolve every `PR-N` in the arg to its task-id list now, before §2 seeds anything, so §2 can see the whole run.

Resolution, the defensive DAG re-check that precedes it, and per-PR branch creation all live in [`references/pr-awareness.md`](references/pr-awareness.md). Load it here.

## 2. Seed the whole TaskList upfront, in execution order

Before dispatching anything, create every TaskList entry the run will need, top-to-bottom in the order they actually execute.
Read from the top, the list *is* the run's timeline — nothing appears later, out of order, as it becomes relevant.

Within each batch that means **tasks first, then that batch's batch-end reminders**, because the reminders fire after the last task lands.

On a PR-label list this covers **every** PR, in the order given: PR-1's tasks → PR-1's reminders → PR-2's tasks → PR-2's reminders, and so on.
This is the one step the per-PR loop does not repeat — showing the whole run from the start is the entire point.
A fail-fast stop simply leaves the later PRs' entries `pending`.

### 2.1. One entry per task

Create one entry for **every** task-id the run resolved — never just the first.

Mark the run's very first task `in_progress` and every other one `pending`.

On a PR-label run, prefix each subject with its owning label — `PR-2 · 5. <task title>`.
That keeps a task's PR readable in the list itself, rather than hidden in a metadata field.

The TaskList carries **status only**. Attempt counts, gate outcomes, and fix SHAs live in the JSON state file (§1.5), which is the single machine-checkable record and the only one the scripts read.

### 2.2. One reminder per batch-end step (they survive compaction)

After a batch's task entries, seed its batch-end steps as **separate** `[Reminder]` entries — the CLAUDE.md `[Reminder]` category, durable reminders of a later step, each producing no commit of its own.

One reminder per step, never one chain covering all of them.
A task has a single `completed` flag, so a combined entry could only track its steps by rewriting its own subject, and a step-level skip or failure would have nowhere to land.

Seed exactly these five, in this order, prefixed with the owning `PR-N ·` on a PR-label run:

```
[Reminder] Batch-end 1/5: planned-test presence gate (§8)
[Reminder] Batch-end 2/5: repo-green gate — full suite + full lint (§9.1)
[Reminder] Batch-end 3/5: review tails ∥ then triage (§9.2–§9.4)
[Reminder] Batch-end 4/5: package print, diffview pane (§9.5)
[Reminder] Batch-end 5/5: draft PR via create-pr (§9.5, only when pr.wanted)
```

The `N/5` prefix is the step order itself, so the sequence survives even if the list is re-sorted or partially rendered.

Flip each to `in_progress` when its step starts and `completed` when it lands; a step the interview turned off (tails, PR) completes with a one-line note that it was skipped by request.

Keep the subjects free of run-specific values like `BATCH_BASE_SHA` — the state file holds those, and a subject that needs them could not be seeded before the PR that captures them.

This complements the Stop hook: the hook blocks *stopping* before the batch is presented, while these entries keep the remaining steps *in view* so you run them unprompted.

On a resume, check the TaskList for these five before dispatching — a new session may not carry them.
If they are absent, re-create them and pre-complete the ones the state-file `phase` shows already done.

## 3. Sub-step decomposition (subagent-owned, per task)

Sub-steps live in a **durable checklist file the subagent owns** — a `/tmp` markdown file — not the orchestrator's TaskList.

Two reasons: subagents have no TaskList/TodoWrite tool to create them, and keeping sub-steps off the orchestrator's list holds it at task-level macro visibility.

The orchestrator, per task, does this and no more (the parent task itself was already created for the whole run in §2.1):

- Marks that task `in_progress` in the TaskList — task-level status, never sub-steps as separate items.
- Gives that task a **breadcrumb** — a coarse outline of its sub-steps (e.g. the plan's acceptance-criteria titles).
  - So the TaskList conveys the task's gist at a glance, without RED-GREEN detail.
- Picks the checklist path `/tmp/implement_substeps_<slug>_<id>.md` and pushes it into the subagent's prompt (§4.1).

The subagent owns everything below, at dispatch and before touching code (its side of these mechanics is also encoded in `~/.claude/agents/tdd-coder.md` — edit both together):

- Writes its RED-GREEN decomposition to that file: one item per RED-GREEN cycle (per AC forcing case), plus the tail steps (post-commit verify per §5, plan_<slug>.md update).
- Flips each item done as it lands — the file is both its working plan and its progress log.
- Expands the cycles rather than a single "do the rest" line, so a re-dispatched subagent resumes from the file instead of re-deriving the breakdown.

The file is a **contract, not scratch**: the orchestrator reads it during post-commit verification (§5.1) to confirm every sub-step ran as decomposed.

### 3.1. Mid-flight sub-steps

When a helper or drift surfaces mid-task, the subagent inserts the new RED-GREEN lines into its checklist file right after the current step, then reports the deviation back (§4.4).
The orchestrator's TaskList never changes except the parent task's status.

Insertion mechanics live in [`references/mid-flight-substeps.md`](references/mid-flight-substeps.md). Load on demand.

## 4. Dispatch the task subagent

Spawn one fresh-context `agent(subAgent=tdd-coder, title=Implement task <N>: <task subject>)` per task, in the background (the default).

Model is omitted because the agent file pins sonnet and the subagent-model-guard hook enforces it.

Cap the dispatch with a 1-hour `Monitor` timeout (`timeout_ms: 3600000` — the tool's documented maximum).
On expiry, call `TaskStop` on the subagent — the dispatch then resolves as a `timeout`, which §5.2 records and obeys exactly like a `fail`.

The harness re-invokes you with its report on completion, so you can still act on it.

The subagent runs the **full per-task lifecycle**.
Its invariant discipline — TDD rules, preloaded standards, checklist mechanics, routing channels, report shape — lives in the agent definition (`~/.claude/agents/tdd-coder.md`); the prompt pushes only the per-task data below.

### 4.1. Context contract

**Push** — embed verbatim in the prompt (the per-task data only the orchestrator holds):

- The task's `plan_<slug>.md` slice: heading, brief, acceptance criteria, planned-test titles, verification command.
- The task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.
- `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.
- The checklist file path (§3).

Everything invariant — checklist write/resume mechanics, preloaded standards, commit rule, report shape, and pull-from-CWD items (plan/spec files, `git log`, source reads) — is baked into the tdd-coder agent definition; don't re-push it.

### 4.2. Mid-execution design forks — the subagent never spawns a reviewer

The task subagent **never** spawns a subagent of its own, reviewer or otherwise.
The harness would allow one more level; this skill spends none of it, so every dispatch stays visible, attributable, and bounded by §4's Monitor cap.

On a mid-execution design fork the plan didn't pre-decide, tdd-coder resolves it one of two ways and hands the outcome back:

- **Soft** fork — it takes the sensible default, proceeds, and flags the choice under Deviations in its report (§4.4). Most forks are this.
  - The second opinion isn't lost, just deferred: §9.2–§9.3's tail pair reads the whole batch diff against spec and plan.
    That is a wider review than a mid-task reviewer seeing one fork in isolation.

- **Hard** fork — it cannot sensibly proceed and returns `blocked` (§4.4). Rare.
  - This needs no new channel: a genuinely open decision is already what `blocked` means here, and it reaches you in the batch-end package like any other block.

### 4.3. Routing mid-execution discoveries

Anything the subagent uncovers outside its task's core work routes through one of three channels — no separate carry-forward digest; the durable artifacts carry it:

- **Drift** — a fix the task needs to proceed → fix it in place, in the task's own commits; the commit-body *why* carries to the next subagent via `git log`.

- **Abstract-in-place** — a footgun that can be designed out trivially and in-scope → dissolve it into the code (a helper that makes the wrong call impossible) rather than recording it.
  - If the abstraction isn't trivial, it's a Scout / its own task instead — no speculative scope mid-task.

- **Scout** — a pre-existing, non-blocking issue, or a real gotcha that can't be abstracted away (environmental things like a required env var).
  - Do **not** touch it; return it to the orchestrator, which records it as a `[Scout]` note on plan_<slug>.md's task breakdown.
  - plan_<slug>.md is the carry-forward surface, read by the next subagent.

### 4.4. Report back

The subagent returns a structured report (text), never a silent "done" (shape mirrored in `~/.claude/agents/tdd-coder.md` — edit both together):

- **Status**: `done` / `blocked`.
- **Commits**: the SHAs it created, with subjects.
- **Self-verification**: the verification command it ran and its result; the planned-test titles it added.
- **Deviations**: sub-steps it inserted into its checklist mid-flight, soft design-forks resolved (with the choice), Drift fixes folded in.
- **For the orchestrator to record**: `[Scout]` items to note on plan_<slug>.md; any block, with exactly what's needed to clear it.

## 5. Verify, retry & advance (orchestrator)

No human gate. The orchestrator — fresh-context relative to the subagent's work, a genuine second pair of eyes — verifies each task's result against the artifacts before advancing.

### 5.1. Verify the result against the diff

Per CLAUDE.md "verify subagent results against artifacts": confirm the reported commits exist (`git log <BATCH_BASE_SHA>..HEAD`), the diff matches the report, and the verification command passes on re-run.

Also read the subagent's checklist file (§3): every sub-step should be checked off before you trust the `done` report.

Unchecked items mean it stopped short of its own plan — treat that as a failed verify (§5.2).

Whatever the outcome, it becomes one recorded attempt and one script verdict — §5.2 for a failure or a block, §5.4 for a pass. There is no path that skips the script.

### 5.2. On failure or a block — record the attempt, obey the verdict

A failed §5.1 verify, a §4 timeout, and a subagent's self-reported `blocked` (§4.4) all take the same path: record the attempt with `result` set to `fail`, `timeout`, or `blocked`, then run:

```bash
~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>
```

Obey its verdict — `retry`, `stuck`, or `halt-budget`. The script alone decides how many retries a task gets, and a `blocked` attempt always verdicts `stuck`, since only the human can clear it.

Full verdict semantics, attempt-recording fields, and the `debug-standards` load live in [`references/failure-verdict.md`](references/failure-verdict.md). Load only on a failed verify.

### 5.3. On `stuck` — mark terminal, chain-abort dependents, advance

Set that task to `status: "blocked"`, with `reason: "blocked"` when the attempt was a self-reported block and `reason: "stuck"` when it was repeated failures.

`status` drives flow — blocked tasks are excluded from the next pick — while `reason` keeps the finer stuck-vs-blocked label for the batch-end report.

`TaskUpdate` its TaskList status to `completed`; the tool has no `blocked` state, and the state file's `reason` is what distinguishes it.

**Chain-abort the task's dependents, before picking what runs next.** Read `plan_<slug>.md`'s "Depends on" lines and walk them transitively.
Any task that depends on the one just marked terminal — directly, or through another dependent — also gets `status: "blocked"` and `reason: "blocked-upstream"`, plus TaskList status `completed`.
Mark them before the orchestrator looks for a next task, so none can be picked.
Flip `plan_<slug>.md` to `[Blocked]` for the terminal task and every dependent this just chain-aborted (§6).

**Pick the next task yourself — the script can't.** `next-task` only comes out of a `pass` attempt (§5.4), and this task didn't pass.
Scan `tasks[]` in order for the first entry whose `status` is neither `done` nor `blocked`, and re-run §1.6–§1.7 + §3 on it.
§1.7 here is a direct pick, not a resume — its resume-reconcile mechanics apply only to an actual stale or dirty run.
Find none — every task is terminal. Set `phase: "gates"` and move to §8's batch test-presence gate.

### 5.4. On a clean verify — advance

Record the attempt with `result: "pass"` and the token count noted at dispatch (§4).

Flip that task to `status: "done"` and `reason: "done"` in the state file — before calling the verdict script, not after.
The script picks the next task by `status`, so a passed task left `pending` would later be re-selected as another task's "next" and redundantly re-dispatched.

Also flip `plan_<slug>.md` to `[Done]` (§6), record the subagent's `[Scout]` notes there, and `TaskUpdate` its TaskList status to `completed`.

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict:

- **`next-task`** → its `task` field names the next task-id; re-run §1.6–§1.7 + §3 on it. §1.1–§1.5 and §2 do not repeat.
- **`gates`** → every task is terminal, and the last one to get there passed.
  - Set `phase: "gates"` — the same phase §5.3's queue-empty scan reaches when the last task was blocked or stuck instead.
- **`halt-budget`** → the batch's dispatch budget is exhausted. Halt the loop and go to §9's batch-end review with whatever work is done so far.

## 6. Status markers (plan_<slug>.md task title)

The orchestrator owns plan_<slug>.md status edits (`[Doing]` / `[Done]` / `[Blocked]` / `[Deferred]` / `[Dropped]`); the subagent never touches them.

Status is a file edit only, never committed (plan_<slug>.md is session-scoped per `spec-driven-development`).

Status sits **right after the number, before any pre-existing tag** (e.g., Jira IDs).

| State | Title format |
|---|---|
| Initial | `### N. Title (...)` |
| In progress | `### N. [Doing] Title (...)` |
| Done | `### N. [Done] Title (...)` |
| Blocked | `### N. [Blocked] Title (...)` |
| Deferred | `### N. [Deferred] Title (...)` |
| Dropped | `### N. [Dropped] Title (...)` |
| With pre-existing tag | `### N. [Doing][JIRA-123] Title (...)` |

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks.

### Semantics

- `[Doing]` — actively in progress this session (dispatched, not yet verified-done).
- `[Done]` — finished, verified by the orchestrator, committed by the subagent.
- `[Blocked]` — external dependency unresolvable in this session (e.g., upstream API down, missing access). Pair with a `**QUESTION:**` marker that names what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT leave partial code committed under a misleading status.

Either the subagent's commits stand as coherent work (status is a separate concern) or the WIP is reverted first.

### PR-level status markers (PR Breakdown line, PR-label runs only)

One level up: a PR-label run's own PR Breakdown line gets the same `[<status>]` prefix at its own §9.
Only `[Done]` in practice, inline, never scripted. Format/timing: `references/batch-end-pr.md`'s "PR manifest entry & PR-level status marker".

## 7. Commit model

The **subagent** produces the commits.

A task lands **at least 1 commit** — RED + GREEN cycles share the base (tests + impl together).

A refactor lands as its own commit, never folded into the base.

Counts: 1 (clean), 2 (+refactor), 3 (+drift fix), etc. Never zero. Scouts are never committed by the subagent — they route to the orchestrator per §4.3.

Never auto-invoke `/refactor` or `/auto-review` **mid-task** — those belong to the user, or to the batch-end tail subagents in **report-only** mode (§9).

## 8. Batch test-presence gate

A mandatory GATE, once after the loop and before §9's tails: every planned test the plan declared must actually be present in the batch's final commits.

This is the batch's **only** planned-test check.
Checking per task would verify each one at its own commit point and still miss what a later task did to those tests afterward.
So the batch's final state is the only state worth checking.

**Entry: `phase` is `gates`** — the state §5.3's queue-empty scan and §5.4's `gates` verdict both set. Never skip it to reach §9 faster.

**Read [`references/batch-test-presence-gate.md`](references/batch-test-presence-gate.md) on entry** — it owns the `deep-reviewer` dispatch contract, that subagent's own title-matching procedure, the try-once fix round, and the budget invariant.

Either outcome — pass, or still-missing recorded for §9's package — ends with `phase: "tails"` and proceeds to §9.

## 9. Batch-end review & tail subagents

After the last task is terminal (`[Done]`, blocked, or the batch halted on budget/stuck), run the batch-end flow over `<BATCH_BASE_SHA>..HEAD`, then present the whole batch for your async review.

That async review **is** the handshake this skill replaces the per-task gate with.

The stages are ordered §9.1 → (§9.2 ∥ §9.3) → §9.4 → §9.5.
§9.1 always runs, regardless of the tails toggle (§1.2).

**Toggle yes (default):** the two tails run **in parallel** — dispatch both in the same turn (both `run_in_background`), wait for both, then §9.4.
Both are **mandatory**; the PR (§9.5) must not open until both reports are recorded.

**Toggle no:** skip §9.2–§9.4, go straight to §9.5, and state there that tails were skipped by request.
No retroactive re-run; invoke `/refactor` or `/auto-review` manually later.

This is a checklist, not a summary line: do each stage, don't collapse them.

### 9.1. Repo-green GATE — full suite, non-negotiable

Confirm the batch's final state is green before reviewing it. This is a hard GATE on the **PR**: it must not open while the repo is red or unrun.

The package (§9.5) still prints on a red repo — flagged "repo not green".
So the human sees the tail reports, the Scouts, and the gate result instead of a silent halt.

Run the **entire** repository's tests and lint — **not** scoped to touched files.
Scoped runs are a mid-development convenience only; the batch-end gate always runs everything, because a batch can break a workspace it never edited (shared types, lib consumers, contract tests).

- Full test suite across **all** workspaces, per the repo's own test guidance.
  - When a repo documents that its raw full suite is unstable (e.g. a Jest worker leak that SIGSEGVs the whole run), use the repo's prescribed stable runner (e.g. a per-spec/agentic runner).
  - Never downgrade the gate to a scoped subset to dodge the instability.
- Full lint across **all** workspaces (the repo-wide lint target, not the per-workspace one).
- Capture both to a file and verify exit code + tail (slow commands per CLAUDE.md).

A red repo here is never something to hand-fix silently — [`references/batch-end-review.md`](references/batch-end-review.md) owns the outcome split, and is the only place it is spelled out.
Its split, recapped: cheap failures (lint autofix, a trivial assertion update) get their own commit; structural failures become `[Scout]` items, unfixed, and flag the package "repo not green".

Record the full-suite result (pass/fail + counts) into the package so the human sees the gate actually ran over everything.

### 9.2-9.3. Deep-reviewer tail pair (mandatory, report-only)

Dispatch both tails via the shared reference [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md).
Set `<BASE_REF>` = `<BATCH_BASE_SHA>` and `<SPEC_PLAN_PATHS>` = the resolved `spec_<slug>.md`/`plan_<slug>.md`.

Record each report's **path** into `.tails.refactor_report`/`.tails.auto_review_report` — the file on disk is canonical, not a state-file copy.

**Both report files must exist on disk before proceeding (when tails were requested).**
If either tail's state field is still `""`, or the file it names is absent, that tail hasn't run.
Go back and run it; do not reach §9.5 with a missing tail report.

Implement-specific queuing/state-file mechanics: [`references/batch-end-review.md`](references/batch-end-review.md).

### 9.4. Triage

Follow the shared reference's triage section: read both reports, synthesize one prioritized summary, and present every finding — including ones that look low-risk — as an apply-offer.

**Never fold a finding into a batch-end commit on your own initiative.**
The auto-apply loop is opt-in, and that opt-in only comes from the user asking directly.
This is either by naming findings to apply after seeing this package (the reference's "Applying a single finding, on explicit request"), or by running `/loop-auto-review` themselves separately for the full loop-until-dry treatment.

### 9.5. Package and opt-in draft PR

Print the batch-end package for the user's one-pass async review: commit-by-commit reading guide, the two tail reports (with your triage verdicts), and any blocks/scouts.

Open the draft PR only when §1.2 recorded `pr.wanted: true`, targeting the confirmed base branch, and only when §9.1's gate came back green.

Opening the PR is the last of the batch-end steps — it runs after the package print and the diffview pane, and presupposes §9.1–§9.4 all ran.

**Never hand-write the PR body — always generate it via a fresh `agent(subAgent=create-pr, title=Draft batch PR description)`, scoped to drafting only.**
The agent's own skill would push and create the PR itself; cap its dispatch to the drafted file so the orchestrator still owns the push and the existing-PR fallback.
A hand-authored body is a defect. Exact dispatch, conventions, and required content: `references/batch-end-pr.md`'s "Draft PR (opt-in)".

**Pass the exact `spec_<slug>.md` + `plan_<slug>.md` this batch resolved in §1.1, plus the resolved `PR-N` on a PR-label run — never auto-detected.**

Set the terminal phase per `references/batch-end-review.md`'s Finalize step.
Use `presented` (and delete the state file) only when every task is `done`.
Use `halted` (and keep it for resume) on a budget hit or any `blocked`/`stuck` task.

The §9.1 → (§9.2 ∥ §9.3) → §9.4 → §9.5 order above is the only place the batch-end sequence is written down; the references expand each step rather than restating the order.

Spawn contracts, failure handling, the package contents, and Finalize are owned by [`references/batch-end-review.md`](references/batch-end-review.md), which routes on to `batch-end-pr.md` for the PR. Load at batch end.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
