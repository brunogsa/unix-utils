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

`/implement` is **fully async**: it runs the whole batch unattended and hands you the finished commits to review in one pass at the end.

There is no per-task human handshake — your batch-end review is the handshake.

Two roles:

- **Orchestrator** (this session) — owns pre-flight, the one-time plan review, decomposition, TaskList, plan.md status, per-task dispatch, post-commit verification, and the batch-end report.
  - It holds only plan + orchestration state, never a task's implementation context.

- **Task subagent** — one fresh context per task, run sequentially. It does the RED-GREEN work, self-verifies, commits, and returns a report.
  - A fresh context per task keeps the batch from rotting one long transcript; each subagent re-grounds from durable artifacts (plan.md, spec.md, `git log`), not session history.

Run task subagents on **Sonnet** — execution is mechanical once the plan is sound — and keep the orchestrator on the session's stronger model for planning and verification judgment.

Tasks run **sequentially**, never in parallel — it's async work, so latency isn't the point.

Sequential order is what lets each subagent read the prior task's commits and any plan.md notes before it starts.

### Chain-abort, with no human gate

A good spec/plan (the prerequisite for any `/implement` run) should make mid-batch stalls almost never fire. When one does:

- **Subagent blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision):
  - Record it, **never guess past it**, leave that task where it stopped, and continue with tasks that don't depend on it.
  - Every block lands in the batch-end report for you to clear in one pass.

- **Subagent's own work fails the orchestrator's post-commit verification** → re-dispatch the same task with the failure as feedback, up to twice.
  - Surface it only if it still fails. Execution correctness is the AI's job, not yours.

## 1. Pre-flight (orchestrator)

The user creates and manages git worktrees themselves — this skill assumes CWD is already where the task should run. It does not create, move into, or merge worktrees.

In a multi-task batch (`/implement 1, 2, 3`), **§1.1–§1.3 and §2 run once** at the start; **§1.4–§1.6 run once per task** as each becomes active.

### 1.1. Locate `plan.md` (and `spec.md`)

- Both present in CWD → proceed.
- Both missing → ask the user for paths. If none provided, **stop**.

### 1.2. Detect base branch

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
```

Confirm the result with the user before proceeding. In autonomous mode: take the parameter as-is, no prompt; if absent, STOP.

### 1.3. Recap of work since base + capture `BATCH_BASE_SHA`

Capture the current HEAD as `BATCH_BASE_SHA` — the start of this invocation's commit range, reused by the subagent contract (§4) and the tail subagents (§8).

Read **full commit messages** (subjects + bodies) — bodies often carry the *why* that subjects don't:

```bash
git log <base>..HEAD > /tmp/implement-recap.log
```

Then read the file. Present the user a 3–5 line summary of what's been done.

Don't dump the full log to chat — the user gets orientation, and the per-task subagents re-derive their own context from `git log` at dispatch.

### 1.4. Match `<task-id>`

Exact-match against numeric prefixes in `plan.md` headings. On multiple matches (rare), ask the user which one.

### 1.5. Handle existing task state

- **Already `[Done]`** → ask: re-execute / skip / abort.
- **Already `[Doing]`** → ask: resume / restart / abort. Multiple `[Doing]` tasks at once is a smell — flag it.
- **Already `[Blocked]` / `[Deferred]`** → ask: resume / abort. (Resume picks up from existing TaskCreate items + `plan.md` context; the `[Doing]` flip happens on resume.)
- **Already `[Dropped]`** → ask: revive (clear status, restart) / abort.

### 1.6. Existing TaskCreate items

Run TaskList. If any items exist, list them **ON CHAT** and ask:

- Keep all
- Delete `completed` only
- Delete all
- Cancel `/implement`

Apply the choice before continuing — long lists may not fully render in the UI, so listing them in chat for explicit confirmation is part of the safety net.

## 2. Orchestration review — advisor, once before any dispatch

Call `advisor()` **once per invocation**, after pre-flight and before dispatching any task — an auto-review of the whole orchestration plan, not a per-task check.

Read the full `plan.md` and all batched task IDs first, so the call challenges the batch as a whole: approach soundness, task ordering, cross-task dependencies, and the verification strategy.

The transcript at this point carries plan.md, spec.md, the recap since base, and the batched IDs — enough for the advisor to challenge it.

Take the advice seriously:

- If the advisor flags a missed forcing case or dependency, fix the plan or the batch order before any dispatch.
- If it challenges the verify method, reconcile it now.
- Skipping or no-op'ing ("looks fine, proceeding") defeats the point.

This is the orchestrator's only advisor call. The subagent has its own, narrower lever for mid-execution forks (§4.2) — distinct from this planning-time review.

## 3. Decompose into TaskList (orchestrator, per task)

The orchestrator owns the TaskList — it is your macro-visibility surface, the plan of record.

The subagent reports against it and never creates its own items, so the plan stays legible in one place.

For each task as it becomes active, generate sub-step items based on **both**:

- The task's existing breadcrumb / sub-bullets in `plan.md` (e.g., `(migration; seed; baseline EXPLAIN; index-on EXPLAIN; compare)`)
- A fresh decomposition: one item per RED-GREEN cycle (one per most-forcing case from the task's acceptance criteria), plus verify / commit / finalize steps.

**CRITICAL: Create ALL known sub-steps in TaskList BEFORE dispatching the task's subagent.**

- Always include the tail steps (post-commit verify per §5, plan.md update) — known upfront.
- You need macro visibility of the task before any code is touched; known steps added late are a planning failure.
- Decomposition is planning, not implementation — it reads the plan slice and ACs, so it stays light and doesn't rot the orchestrator's context.

Why expand the cycles instead of looping: each RED-GREEN pair surviving as its own item means a `/clear` or session restart can resume cleanly.

A single "loop the rest" bullet erases that visibility.

### 3.1. TaskList structure: parent task + sub-steps

Create the parent task in TaskList **first** (if it does not exist), then each sub-step. The parent groups its sub-steps visually and provides a single place to flip task-level status.

### 3.2. Mid-flight sub-steps

A helper or drift that surfaces mid-task is handled inside the subagent's own context and reported back (§4.4).

The orchestrator reflects the outcome in its TaskList — it doesn't micromanage the subagent's RED-GREEN granularity.

The insertion + visual-regrouping mechanics (for the subagent's own tracking, or for an orchestrator resuming a task by hand) live in [`references/mid-flight-substeps.md`](references/mid-flight-substeps.md). Load on demand.

## 4. Dispatch the task subagent

Spawn one fresh-context subagent per task via the **Agent tool**, `subagent_type=general-purpose`, `model=sonnet`. Default to foreground so you can act on its report immediately; the run is async to the human regardless.

The subagent runs the **full per-task lifecycle** — it is not an edit-and-commit drone. Its prompt is the entire instruction set it receives, so the contract below must be self-contained.

### 4.1. Context contract

**Push** — embed verbatim in the prompt (what the orchestrator already holds):

- The task's `plan.md` slice: heading, brief, acceptance criteria, planned-test titles, verification command.
- The task's **Files (logical order)** list from plan.md as the **starting set** — not a cage; touch more when execution requires it, routing the delta per §4.3.
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

The subagent executes mechanically and does **not** call `advisor()` by default — the plan was already advisor-reviewed by the orchestrator (§2).

It calls `advisor()` **only** when a real design fork surfaces mid-execution that the plan didn't pre-decide and where guessing wrong is costly.

That's a decision, and the rule is "the AI escalates decisions" — but this one escalates to the stronger advisor model, not to the human, so it stays off your plate.

The advisor also triages the fork:

- **Soft** — pick a sensible default, proceed, and flag it in the report for batch review. Most forks are this.
- **Hard** — can't sensibly proceed → stop the task and return it as a block (§4.4). Rare.

### 4.3. Routing mid-execution discoveries

Anything the subagent uncovers that isn't its task's core work routes through one of three channels — there is no separate carry-forward digest, because the durable artifacts already carry it:

- **Drift** — a fix the task needs to proceed → fix it in place, inside the task's own commits; the commit body carries the *why*.
  - The next subagent inherits it from `git log` + the changed code.

- **Abstract-in-place** — a footgun that can be designed out trivially and in-scope → dissolve it into the code (a helper that makes the wrong call impossible) rather than recording it.
  - Prefer this: code doesn't rot like a note.
  - If the abstraction isn't trivial, it's a Scout / its own task instead — no speculative scope mid-task.

- **Scout** — a pre-existing, non-blocking issue, or a real gotcha that can't be abstracted away (environmental things like a required env var).
  - Do **not** touch it; return it to the orchestrator, which records it as a `[Scout]` note on plan.md's task breakdown.
  - plan.md is the carry-forward surface — durable, and read by the next subagent.

### 4.4. Report back

The subagent returns a structured report (text), never a silent "done":

- **Status**: `done` / `blocked`.
- **Commits**: the SHAs it created, with subjects.
- **Self-verification**: the verification command it ran and its result; the planned-test titles it added.
- **Deviations**: sub-steps it inserted mid-flight, any soft design-fork it resolved (with the choice made), Drift fixes folded in.
- **For the orchestrator to record**: `[Scout]` items to note on plan.md; any block, with exactly what's needed to clear it.

## 5. Verify, retry & advance (orchestrator)

This replaces the old two-party handshake. No human gate.

The orchestrator — fresh-context relative to the subagent's work, so a genuine second pair of eyes — verifies each task's result against the artifacts before advancing.

### 5.1. Verify the result against the diff

Per CLAUDE.md "verify subagent results against artifacts": confirm the reported commits exist (`git log <BATCH_BASE_SHA>..HEAD`), the diff matches what the report claims, and the verification command passes when re-run.

### 5.2. Gate 3 — planned-test presence (post-commit)

Run Gate 3 against the subagent's commit range — the orchestrator never saw the impl, so it is genuinely fresh-context and needs no nested sub-subagent.

Full procedure in [`references/gate-3-verification.md`](references/gate-3-verification.md). Load on demand.

### 5.3. On failure — bounded retry

If §5.1 or §5.2 fails (diff mismatch, verification red, planned tests missing), re-dispatch the **same task** as a fresh subagent with the specific failure as feedback. Cap at **2 retries**.

If it still fails, leave the task `[Doing]`, record the failure, and surface it in the batch-end report — don't loop forever, and don't hand-fix what the subagent should own.

Load `debug-standards` if you need to diagnose why it keeps failing.

### 5.4. On block

If the subagent returned `blocked` (§4.4), leave the task where it stopped, record the block, and advance to the next task that doesn't depend on it. Never guess past a human-needed block.

### 5.5. Advance

On a clean verify: flip plan.md to `[Done]` (§6), record the subagent's `[Scout]` notes on plan.md, then re-run §1.4–§1.6 + §3 for the next task. §1.1–§1.3 and §2 do not repeat.

## 6. Status markers (plan.md task title)

Status sits **right after the number, before any pre-existing tag** (e.g., Jira IDs). The orchestrator owns these edits — the subagent never touches plan.md status.

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

`plan.md` is session-scoped (gitignored per `spec-driven-development`). Status updates are file edits only, **never committed**.

### 6.1. Semantics

- `[Doing]` — actively in progress this session (dispatched, not yet verified-done).
- `[Done]` — finished, verified by the orchestrator, committed by the subagent.
- `[Blocked]` — external dependency unresolvable in this session (e.g., upstream API down, missing access). Pair with a `**QUESTION:**` marker that names what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT leave partial code committed under a misleading status.

Either the subagent's commits stand as coherent work (status is a separate concern) or the WIP is reverted first.

## 7. Commit model

The **subagent** produces the commits. A task lands **at least 1 commit** — RED + GREEN cycles share the base (tests + impl together). Refactors land as their own task.

Counts: 1 (clean), 2 (+refactor), 3 (+scout fix), etc. Never zero.

The skill never auto-invokes `/refactor` or `/auto-review` **mid-task** — those triggers belong to the user, or to the batch-end tail subagents in **report-only** mode (§8).

## 8. Batch-end review & tail subagents

After the last task transitions to `[Done]` (or the batch ends with blocked/failed tasks recorded), the orchestrator runs the tail subagents, then presents the batch for your async review.

That async review **is** the handshake this skill replaces the per-task gate with.

Queue **two** batch-level TaskList items (NOT sub-steps of any single task):

1. `[Side] Tail — /refactor over batch in fresh-context subagent (report-only)`
2. `[Side] Tail — /auto-review over batch in fresh-context subagent (report-only)`

Run them **sequentially**, in that order (refactor first so its findings can inform later passes). Both run once per `/implement` invocation regardless of batch size.

### 8.1. Scope

Each subagent reviews **only the batch's commit range**, not the whole branch. Resolve the range as `<BATCH_BASE_SHA>..HEAD` (captured in §1.3).

### 8.2. Spawn contract

Spawn each subagent via the **Agent tool**, `subagent_type=general-purpose`, foreground (never `run_in_background`). Pass the inputs below in the prompt body — these are the entire instruction set the subagent receives.

The prompt **must lead with this preamble verbatim** (line-for-line; the subagent's compliance with these rules is what enforces report-only behavior — there is no skill flag, no harness gate):

```
REPORT-ONLY MODE — STRICT CONTRACT

You are spawned by /implement as an end-of-batch tail subagent. Your only
permitted output side effect is writing ONE markdown report file to CWD.

YOU MUST NOT:
- Run `git commit`, `git push`, or any state-mutating git command.
- Use the Edit, Write, or MultiEdit tools on any file except your single
  report file.
- Apply, fix, or suggest-and-then-apply any finding.
- Spawn nested subagents.

YOU MUST:
- Run the underlying skill (/refactor or /auto-review) in its
  analysis/findings phase only.
- Write the complete findings to the report path named below — overwriting
  any prior file at that path.
- Return a one-paragraph summary plus the report path. Nothing else.

Violating any of the MUST NOT items aborts the parent /implement.
```

After the preamble, include the skill-specific body:

- For the **refactor** subagent: "Invoke `/refactor` over `<BATCH_BASE_SHA>..HEAD`. Write findings to `./refactor_<YYYY-MM-DD_HH:MM>.md` in CWD."
- For the **auto-review** subagent: "Invoke `/auto-review <BATCH_BASE_SHA>` (per its `/auto-review HEAD~N` per-task scoping convention). Write findings to `./auto-review_<YYYY-MM-DD_HH:MM>.md` in CWD."

### 8.3. Failure handling

- **Subagent attempts a forbidden operation** (per preamble) → permission gate refuses; subagent's verdict surfaces as the failure.
  - Parent `/implement` reports the violation and continues to the next tail subagent (refactor failing does not block auto-review).
- **Subagent error / no report file written** → log it to chat with the agent's last message.
  - Do NOT retry inline (different from Gate 3): batch-end reports are reviewed asynchronously; a missing report is user-attention, not a retry loop.
- **Both reports written** → continue to §8.5.

### 8.4. Overwrite policy

Each invocation produces timestamped filenames (`refactor_<ts>.md`, `auto-review_<ts>.md`), so multiple `/implement` runs in the same CWD accumulate as separate files.

Gitignore patterns `refactor*.md` and `auto-review*.md` cover all timestamped variants.

### 8.5. Present the batch for review

Print to chat the single async pass the human reviews — the replacement for the per-task handshake:

- Per-task outcomes: `done` / `blocked` / `failed-after-retry`, each with its commit SHAs.
- The two tail-report paths.
- Every recorded `[Scout]` note and every block, with what each needs to clear.
