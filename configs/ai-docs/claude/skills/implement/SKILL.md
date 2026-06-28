---
name: implement
description: "Execute one or more plan.md tasks end-to-end as fresh-context subagents — run sequentially, fully async — managing decomposition, status, verification and commits. Trigger: /implement <id> or /implement <id1>, <id2>, ..."
disable-model-invocation: true
---

## Usage

```
/implement <task-ids>
```

`<task-ids>` is one numeric task prefix or a comma-list of them — `5`, or `1, 2, 3` from `plan.md` in CWD. 1 space after commas.
Each ID matches the **exact** numeric prefix of a plan.md heading. On ambiguity (rare), ask the user.

## Execution model — orchestrator + per-task subagents

`/implement` is **fully async**: it runs the whole batch unattended, handing you the finished commits to review in one pass.

There is no per-task human handshake — your batch-end review is the handshake.

Two roles:

- **Orchestrator** (this session) — owns pre-flight, the one-time plan review, decomposition, TaskList, plan.md status, per-task dispatch, post-commit verification, and the batch-end report.
  - It holds only plan + orchestration state, never a task's implementation context.

- **Task subagent** — one fresh context per task, run sequentially: does the RED-GREEN work, self-verifies, commits, returns a report.
  - Each re-grounds from durable artifacts (plan.md, spec.md, `git log`), not session history — so a long batch never rots into one transcript.

Run subagents on **Sonnet** (execution is mechanical once the plan is sound); keep the orchestrator on the session's stronger model for planning and verification.

Tasks run **sequentially**, never in parallel (async work — latency isn't the point); sequential order lets each subagent read the prior task's commits and plan.md notes first.

### Chain-abort, with no human gate

A good spec/plan (the prerequisite for any `/implement` run) should make mid-batch stalls almost never fire. When one does:

- **Subagent blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision):
  - Record it, **never guess past it**, leave that task where it stopped, and continue with tasks that don't depend on it.
  - Every block lands in the batch-end report for you to clear in one pass.

- **Subagent's own work fails the orchestrator's post-commit verification** → re-dispatch the same task with the failure as feedback, up to twice.
  - Surface it only if it still fails. Execution correctness is the AI's job, not yours.

## 1. Pre-flight (orchestrator)

The user manages git worktrees; this skill assumes CWD is already where the task should run and never creates, moves into, or merges them.

In a multi-task batch (`/implement 1, 2, 3`), **§1.1–§1.3 and §2 run once** at the start; **§1.4–§1.5 run once per task** as each becomes active.

### 1.1. Locate `plan.md` (and `spec.md`)

- Both present in CWD → proceed.
- Both missing → ask the user for paths. If none provided, **stop**.

### 1.2. Detect base branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
```

Confirm with the user before proceeding. In autonomous mode: take the parameter as-is; if absent, STOP.

### 1.3. Recap of work since base + capture `BATCH_BASE_SHA`

Capture HEAD as `BATCH_BASE_SHA` — the start of this invocation's commit range, reused in §4 and §8.

Read **full commit messages** — bodies often carry the *why* subjects don't:

```bash
git log <base>..HEAD > /tmp/implement-recap.log
```

Then read it and give the user a 3–5 line summary of what's done.

Don't dump the full log to chat; the per-task subagents re-derive their own context from `git log` at dispatch.

### 1.4. Match `<task-id>`

Exact-match against numeric prefixes in `plan.md` headings. On multiple matches (rare), ask the user which one.

### 1.5. Existing state (resume / dirty runs)

On a resume or re-run, reconcile any pre-existing task status and stray TaskList items before proceeding. A clean first run skips this.

The per-state prompts (re-execute / resume / restart / revive) and the TaskList cleanup choices live in [`references/preflight-state.md`](references/preflight-state.md). Load when state exists.

## 2. Orchestration review — advisor, once before any dispatch

Call `advisor()` **once per invocation**, after pre-flight and before dispatching any task — an auto-review of the whole orchestration plan, not a per-task check.

Read the full `plan.md` and all batched IDs first, so the call challenges the batch as a whole: approach, task ordering, cross-task dependencies, verification strategy.

Take the advice seriously:

- If the advisor flags a missed forcing case or dependency, fix the plan or the batch order before any dispatch.
- If it challenges the verify method, reconcile it now.
- Skipping or no-op'ing ("looks fine, proceeding") defeats the point.

This is the orchestrator's only advisor call; the subagent has its own narrower lever for mid-execution forks (§4.2).

## 3. Decompose into TaskList (orchestrator, per task)

The orchestrator owns the TaskList — your macro-visibility surface. The subagent reports against it and never creates its own items, so the plan stays legible.

For each task as it becomes active, generate sub-step items based on **both**:

- The task's existing breadcrumb / sub-bullets in `plan.md` (e.g., `(migration; seed; baseline EXPLAIN; index-on EXPLAIN; compare)`)
- A fresh decomposition: one item per RED-GREEN cycle (one per most-forcing case from the task's acceptance criteria), plus verify / commit / finalize steps.

**CRITICAL: Create ALL known sub-steps in TaskList BEFORE dispatching the task's subagent.**

- Always include the tail steps (post-commit verify per §5, plan.md update) — known upfront.
- You need macro visibility before any code is touched; steps added late are a planning failure.
- Decomposition is planning, not implementation — it reads the plan slice and ACs, so it stays light.

Expand the cycles rather than loop: each RED-GREEN pair as its own item lets a `/clear` or restart resume cleanly — a single "loop the rest" bullet erases that.

### 3.1. TaskList structure: parent task + sub-steps

Create the parent task **first** (if absent), then each sub-step — it groups them visually and gives one place to flip task-level status.

### 3.2. Mid-flight sub-steps

A helper or drift surfacing mid-task is handled inside the subagent and reported back (§4.4); the orchestrator just reflects the outcome in its TaskList, not the subagent's RED-GREEN granularity.

The insertion + visual-regrouping mechanics live in [`references/mid-flight-substeps.md`](references/mid-flight-substeps.md). Load on demand.

## 4. Dispatch the task subagent

Spawn one fresh-context subagent per task via the **Agent tool** (`subagent_type=general-purpose`, `model=sonnet`), foreground so you can act on its report; the run is async regardless.

The subagent runs the **full per-task lifecycle**. Its prompt is the entire instruction set it receives, so the contract below must be self-contained.

### 4.1. Context contract

**Push** — embed verbatim in the prompt (what the orchestrator already holds):

- The task's `plan.md` slice: heading, brief, acceptance criteria, planned-test titles, verification command.
- The task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.
- `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.
- The sub-step list the orchestrator decomposed (§3), as the work plan to execute.
- Standards to load: `test-standards`, `code-standards`, `doc-standards`, `commit-standards` (and `debug-standards` if a test goes red for the wrong reason).
- The commit rule: follow `commit-standards`, including the `Co-Authored-By` trailer — the git-guard hook rejects commits without it, subagents included.
- The required report shape (§4.4).

**Pull** — tell the subagent to fetch these itself from CWD (keeps the prompt lean):

- Full `plan.md` and `spec.md`.
- `git log <BATCH_BASE_SHA>..HEAD` for the prior tasks' *why* (rich commit bodies), and any `[Scout]` notes a prior task appended to plan.md.
- The actual source files it needs to read.

### 4.2. On-demand advisor (subagent escape hatch)

The subagent does **not** call `advisor()` by default — the plan was already advisor-reviewed (§2).

It calls `advisor()` **only** for a real mid-execution design fork the plan didn't pre-decide, where guessing wrong is costly.

It escalates to the stronger advisor model, not to you — off your plate.

The advisor also triages the fork:

- **Soft** — pick a sensible default, proceed, and flag it in the report for batch review. Most forks are this.
- **Hard** — can't sensibly proceed → stop the task and return it as a block (§4.4). Rare.

### 4.3. Routing mid-execution discoveries

Anything the subagent uncovers outside its task's core work routes through one of three channels — no separate carry-forward digest; the durable artifacts carry it:

- **Drift** — a fix the task needs to proceed → fix it in place, in the task's own commits; the commit-body *why* carries to the next subagent via `git log`.

- **Abstract-in-place** — a footgun that can be designed out trivially and in-scope → dissolve it into the code (a helper that makes the wrong call impossible) rather than recording it.
  - If the abstraction isn't trivial, it's a Scout / its own task instead — no speculative scope mid-task.

- **Scout** — a pre-existing, non-blocking issue, or a real gotcha that can't be abstracted away (environmental things like a required env var).
  - Do **not** touch it; return it to the orchestrator, which records it as a `[Scout]` note on plan.md's task breakdown.
  - plan.md is the carry-forward surface, read by the next subagent.

### 4.4. Report back

The subagent returns a structured report (text), never a silent "done":

- **Status**: `done` / `blocked`.
- **Commits**: the SHAs it created, with subjects.
- **Self-verification**: the verification command it ran and its result; the planned-test titles it added.
- **Deviations**: sub-steps inserted mid-flight, soft design-forks resolved (with the choice), Drift fixes folded in.
- **For the orchestrator to record**: `[Scout]` items to note on plan.md; any block, with exactly what's needed to clear it.

## 5. Verify, retry & advance (orchestrator)

No human gate. The orchestrator — fresh-context relative to the subagent's work, a genuine second pair of eyes — verifies each task's result against the artifacts before advancing.

### 5.1. Verify the result against the diff

Per CLAUDE.md "verify subagent results against artifacts": confirm the reported commits exist (`git log <BATCH_BASE_SHA>..HEAD`), the diff matches the report, and the verification command passes on re-run.

### 5.2. Planned-test presence check (post-commit)

Run the planned-test check against the subagent's commit range — the orchestrator never saw the impl, so it is genuinely fresh-context and needs no nested sub-subagent.

Full procedure in [`references/planned-test-verification.md`](references/planned-test-verification.md). Load on demand.

### 5.3. On failure — bounded retry

If §5.1 or §5.2 fails (diff mismatch, verification red, planned tests missing), re-dispatch the **same task** as a fresh subagent with the specific failure as feedback. Cap at **2 retries**.

If it still fails, leave the task `[Doing]`, record the failure, and surface it in the batch-end report; don't hand-fix what the subagent should own.

Load `debug-standards` if you need to diagnose why it keeps failing.

### 5.4. On block

If the subagent returned `blocked` (§4.4), leave the task where it stopped, record the block, and advance to the next independent task. Never guess past a human-needed block.

### 5.5. Advance

On a clean verify: flip plan.md to `[Done]` (§6), record the subagent's `[Scout]` notes on plan.md, then re-run §1.4–§1.5 + §3 for the next task. §1.1–§1.3 and §2 do not repeat.

## 6. Status markers (plan.md task title)

The orchestrator owns plan.md status edits (`[Doing]` / `[Done]` / `[Blocked]` / `[Deferred]` / `[Dropped]`); the subagent never touches them.

Status is a file edit only, never committed (plan.md is session-scoped per `spec-driven-development`).

The full marker table, placement rule, and per-state semantics live in [`references/status-markers.md`](references/status-markers.md). Load when flipping status or handling a non-`[Done]` terminal state.

## 7. Commit model

The **subagent** produces the commits. A task lands **at least 1 commit** — RED + GREEN cycles share the base (tests + impl together). Refactors land as their own task.

Counts: 1 (clean), 2 (+refactor), 3 (+scout fix), etc. Never zero.

Never auto-invoke `/refactor` or `/auto-review` **mid-task** — those belong to the user, or to the batch-end tail subagents in **report-only** mode (§8).

## 8. Batch-end review & tail subagents

After the last task is `[Done]` (or the batch ends with blocked/failed tasks recorded), run two report-only tail subagents over the batch range `<BATCH_BASE_SHA>..HEAD` — `/refactor` then `/auto-review`.

Then present the whole batch for your async review.

That async review **is** the handshake this skill replaces the per-task gate with.

The full procedure — queued items, spawn contract, report-only preamble, failure handling, batch-review summary — lives in [`references/batch-end.md`](references/batch-end.md). Load at batch end.
