---
name: implement
description: "Execute one or more plan_<slug>.md tasks end-to-end as fresh-context subagents — run sequentially, fully async — managing decomposition, status, verification and commits. Trigger: /implement <id> or /implement <id1>, <id2>, ..."
disable-model-invocation: false
---

## Usage

```
/implement <task-ids>
```

`<task-ids>` is one numeric task prefix or a comma-list of them — `5`, or `1, 2, 3` from `plan_<slug>.md` in CWD. 1 space after commas.
Each ID matches the **exact** numeric prefix of a plan_<slug>.md heading. On ambiguity (rare), ask the user.

## Execution model — orchestrator + per-task subagents

`/implement` is **fully async**: it runs the whole batch unattended, handing you the finished commits to review in one pass.

There is no per-task human handshake — your batch-end review is the handshake.

Two roles:

- **Orchestrator** (this session) — pre-flight, plan review, TaskList (parent tasks only), dispatch, post-commit verification, batch-end report.
  Holds only orchestration state, never task implementation context.

- **Task subagent** — one fresh context per task, sequential: decompose into its own checklist file, RED-GREEN work, self-verify, commit, report.
  Each re-grounds from durable artifacts (plan_<slug>.md, spec_<slug>.md, `git log`), not session history.

Run subagents on **Sonnet** (execution is mechanical); keep orchestrator on stronger model.
Tasks run **sequentially** — each reads the prior task's commits + plan_<slug>.md notes first.

### Chain-abort, with no human gate

A good spec/plan (the prerequisite for any `/implement` run) should make mid-batch stalls almost never fire. When one does:

- **Subagent blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision):
  - Record it, **never guess past it**, leave that task where it stopped, and continue with tasks that don't depend on it.
  - Every block lands in the batch-end report for you to clear in one pass.

- **Subagent's own work fails the orchestrator's post-commit verification** → re-dispatch the same task with the failure as feedback; the verdict script decides how many attempts it gets (§5.3).
  - Surface it only if it still fails. Execution correctness is the AI's job, not yours.

## 1. Pre-flight (orchestrator)

The up-front interview (§1.2) asks whether this run creates its own git worktree; on yes, §1.3 creates and populates it.

On no, this skill runs in the current checkout as before, and never merges or deletes a worktree on its own either way.

In a multi-task batch (`/implement 1, 2, 3`), **§1.1–§1.5 and §2 run once** at the start; **§1.6–§1.7 run once per task** as each becomes active.

### 1.1. Locate the plan (and spec)

Glob in CWD (top-level only):

```bash
ls -1 plan_*.md spec_*.md 2>/dev/null
```

Resolve candidates with this decision tree — this step only gathers candidates and never prompts on its own; an ambiguous match becomes the interview's plan-pick question (§1.2):

- **Exactly one plan and one spec** → use both; print the resolved paths, no prompt.
- **Multiple plans (or multiple specs)** → the interview's plan-pick question lists the matches numbered; pair each plan with the spec sharing its `<slug>` when one exists.
- **No plan found** → the interview asks for the path. If none provided, **stop**.
- **Plan but no spec** → proceed plan-only; the spec is optional context.

Everywhere below, `plan_<slug>.md` / `spec_<slug>.md` refer to these resolved paths.

### 1.2. One up-front interview

Ask everything at once, in a single message, before any dispatch — this is the only round of questions until the review package.

The rare exceptions are §1.6's multiple-task-id-match disambiguation and §1.7's resume/dirty-run prompts — pre-existing task-activation checks, outside the up-front interview.

Mid-run `.env` needs are self-served (copy from the original checkout) rather than asked.

- **Plan pick**, only when §1.1 found multiple candidates.
- **Run in a git worktree?** (yes/no) — on yes, §1.3 creates it from HEAD and copies files in.
- **Open a draft PR at batch end?** (yes/no).
- **Base-branch confirmation** — show `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` as the default; let the user confirm or override.
  In autonomous mode: take the parameter as-is; if absent, STOP.

Record all answers (three, or four when the plan-pick question fired) before proceeding — §1.5 persists them into the state file.

### 1.3. Worktree setup (only when §1.2 answered yes)

Call `EnterWorktree` with no `path` argument.

`settings.json`'s `worktree.baseRef: "head"` makes the new worktree branch from the current HEAD, so this works from `main` or any feature branch — never from a fixed default branch.

Then copy into the worktree, from the original checkout: `plan_<slug>.md`, `spec_<slug>.md` (both untracked, so `git worktree add`'s checkout never carries them), and any `.env*` files.

When §1.2 answered no, skip this step entirely; the batch-end package omits the merge-back reminder because no worktree exists to merge back.

### 1.4. Recap of work since base + capture `BATCH_BASE_SHA`

Capture HEAD as `BATCH_BASE_SHA` — the start of this invocation's commit range (reused in §4, §8, and §9).

Capture it **after** §1.3, so a new worktree's HEAD (same commit, different working directory) is what gets recorded.

Read **full commit messages** and give a 3–5 line summary. Don't dump the log; subagents re-derive context from `git log` at dispatch.

### 1.5. State-file init (and resume adoption)

Check for an existing state file belonging to this `<slug>`:

```bash
grep -l "\"slug\": \"<slug>\"" ~/.claude/implement-runs/*.json 2>/dev/null
```

- **None found** → create `~/.claude/implement-runs/<session_id>.json` per the schema in `plan_implement-loop.md`'s Technical Approach.
  - Top-level fields: `version`, `session_id`, `slug`, `phase: "tasks"`, `batch_base_sha`, `started_at`, `presented_at: ""`, `gate_dispatches: 0`, empty `tails`.
  - Plus `worktree` / `pr` filled from §1.2's answers, one `tasks[]` entry per matched task-id (`status: "pending"`), and empty `attempts[]`.
- **Found** → load [`references/preflight-state.md`](references/preflight-state.md) for the JSON-adoption mechanics that restore attempt counts and completed-task status.

### 1.6. Match `<task-id>`

Exact-match against numeric prefixes in `plan_<slug>.md` headings. On multiple matches (rare), ask the user which one.

### 1.7. Existing state (resume / dirty runs)

On a resume or re-run, reconcile any pre-existing task status and stray TaskList items before proceeding. A clean first run skips this.

This is orthogonal to §1.5's silent JSON adoption: once adopted, the verdict script (§4-5) already skips `done`/`blocked` tasks on its own.

So this step fires only for drift the JSON doesn't cover — a stale `plan_<slug>.md` marker, a stray TaskList item, or a dirty run with no matching JSON file at all.

The per-state prompts (re-execute / resume / restart / revive) and the TaskList cleanup choices live in [`references/preflight-state.md`](references/preflight-state.md). Load when state exists.

## 2. Orchestration review — fresh-context subagent, once before any dispatch

Spawn a review subagent **once per invocation**, after pre-flight and before dispatching — adversarial review of the whole batch (not per-task).
Fresh context: the plan was authored in-session, already convinced — reviewer sees only artifacts + question.

Challenge the batch as a whole: approach, ordering, dependencies, verification strategy.
Take it seriously: fix the plan/batch if dependencies are missed; reconcile verification method challenges; skipping defeats the point.

This is the orchestrator's only plan-level review; the task subagent has its own mid-execution fork lever (§4.2).

## 3. Sub-step decomposition (subagent-owned, per task)

Sub-steps live in a **durable checklist file the subagent owns** — a `/tmp` markdown file — not the orchestrator's TaskList.

Two reasons: subagents have no TaskList or TodoWrite tool to create them with, and keeping sub-steps off the orchestrator's list holds that list at task-level macro visibility.

The orchestrator, per task, does this and no more:

- Creates **one parent task** in its TaskList — task-level status, never sub-steps as separate items.
- Gives that task a **breadcrumb** — a coarse outline of its sub-steps (e.g. the plan's acceptance-criteria titles).
  - This ensures the TaskList conveys the task's gist at a glance, without the RED-GREEN detail.
- Picks the checklist path `/tmp/implement_substeps_<slug>_<id>.md` and pushes it into the subagent's prompt (§4.1).

The subagent owns everything below, at dispatch and before touching code:

- Writes its RED-GREEN decomposition to that file: one item per RED-GREEN cycle (per AC forcing case), plus the tail steps (post-commit verify per §5, plan_<slug>.md update).
- Flips each item done as it lands — the file is both its working plan and its progress log.
- Expands the cycles rather than looping one "do the rest" line, so a re-dispatched subagent picks up from the file instead of re-deriving the breakdown.

The file is a **contract, not scratch**: the orchestrator reads it during post-commit verification (§5.1) to confirm every sub-step ran as decomposed.

The breadcrumb and the checklist don't overlap: the breadcrumb is a static, orchestrator-authored gist for the TaskList; the checklist is the subagent's live, fine-grained log and the only verification source (§5.1).

### 3.1. Mid-flight sub-steps

When a helper or drift surfaces mid-task, the subagent inserts the new RED-GREEN lines into its checklist file right after the current step, then reports the deviation back (§4.4).
The orchestrator's TaskList never changes except the parent task's status.

The insertion mechanics live in [`references/mid-flight-substeps.md`](references/mid-flight-substeps.md). Load on demand.

## 4. Dispatch the task subagent

Spawn one fresh-context subagent per task via the **Agent tool** (`subagent_type=general-purpose`, `model=sonnet`), in the background (the default).

Cap the dispatch with a 1-hour `Monitor` timeout.
On expiry, call `TaskStop` on the subagent — the dispatch then resolves as a `timeout`, which §5.3 records and obeys exactly like a `fail`.
Whether the harness actually honors a 1-hour `Monitor` cap is an execution-time discovery — this documents the intent, not a verified guarantee.

The harness re-invokes you with its report on completion, so you can still act on it.
Note the token count the Agent tool result reports for the run, defaulting to `0` when it doesn't expose one.
§5 records it into the attempt it creates — except on a self-reported block, which creates no attempt at all (§5.4).
This is best-effort only and never gates the loop mid-run — overage surfaces later via the metrics script, not here.

The subagent runs the **full per-task lifecycle**. Its prompt is the entire instruction set it receives, so the contract below must be self-contained.

### 4.1. Context contract

**Push** — embed verbatim in the prompt (what the orchestrator already holds):

- The task's `plan_<slug>.md` slice: heading, brief, acceptance criteria, planned-test titles, verification command.
- The task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.
- `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.
- The checklist file path (§3): on a fresh dispatch, before coding, write the RED-GREEN breakdown there — one item per AC forcing case, plus post-commit-verify and plan_<slug>.md-update tail steps.
- On a re-dispatch that file already exists: read it and resume from the first unchecked item rather than rewriting it, so the progress log survives.
- The rule to keep that file current: flip each sub-step done as it lands, so the file stays an accurate progress log for the orchestrator to verify (§5.1).
- Standards to load: `test-standards`, `code-standards`, `doc-standards`, `commit-standards` (and `debug-standards` if a test goes red for the wrong reason).
- The commit rule: follow `commit-standards`, including the `Co-Authored-By` trailer — the git-guard hook rejects commits without it, subagents included.
- The required report shape (§4.4).

**Pull** — tell the subagent to fetch these itself from CWD (keeps the prompt lean):

- Full `plan_<slug>.md` and `spec_<slug>.md`.
- `git log <BATCH_BASE_SHA>..HEAD` for the prior tasks' *why* (rich commit bodies), and any `[Scout]` notes a prior task appended to plan_<slug>.md.
- The actual source files it needs to read.

### 4.2. On-demand fork review (subagent escape hatch)

The task subagent does **not** spawn a reviewer by default — the plan was already reviewed (§2).

It spawns a fresh-context review subagent **only** for a real mid-execution design fork the plan didn't pre-decide, where guessing wrong is costly.

Push the fork, the candidate options, and the relevant plan slice into the reviewer's prompt; omit the `model=sonnet` override so it runs on the stronger session model.

It escalates to that reviewer, not to you — off your plate.

The reviewer also triages the fork:

- **Soft** — pick a sensible default, proceed, and flag it in the report for batch review. Most forks are this.
- **Hard** — can't sensibly proceed → stop the task and return it as a block (§4.4). Rare.

### 4.3. Routing mid-execution discoveries

Anything the subagent uncovers outside its task's core work routes through one of three channels — no separate carry-forward digest; the durable artifacts carry it:

- **Drift** — a fix the task needs to proceed → fix it in place, in the task's own commits; the commit-body *why* carries to the next subagent via `git log`.

- **Abstract-in-place** — a footgun that can be designed out trivially and in-scope → dissolve it into the code (a helper that makes the wrong call impossible) rather than recording it.
  - If the abstraction isn't trivial, it's a Scout / its own task instead — no speculative scope mid-task.

- **Scout** — a pre-existing, non-blocking issue, or a real gotcha that can't be abstracted away (environmental things like a required env var).
  - Do **not** touch it; return it to the orchestrator, which records it as a `[Scout]` note on plan_<slug>.md's task breakdown.
  - plan_<slug>.md is the carry-forward surface, read by the next subagent.

### 4.4. Report back

The subagent returns a structured report (text), never a silent "done":

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

Unchecked items mean it stopped short of its own plan — treat that as a failed verify (§5.3) or a block (§5.4).

### 5.2. Planned-test presence check (post-commit)

Run the planned-test check against the subagent's commit range — the orchestrator never saw the impl, so it is genuinely fresh-context and needs no nested sub-subagent.

Full procedure in [`references/planned-test-verification.md`](references/planned-test-verification.md). Load on demand.

### 5.3. On failure — record and obey the verdict

If §5.1 or §5.2 fails (diff mismatch, verification red, planned tests missing), or the dispatch hit the 1-hour timeout (§4), record the attempt.
On a verify failure, set `result` to `fail` and `signature` to the failure text verbatim — the error output, or the list of missing planned tests.
On a timeout, set `result` to `timeout` and `signature` to the literal string `timeout` — there's no diff to inspect, since the subagent never reported back.
Either way, also record the token count noted at dispatch (§4) — the run still cost tokens even though it didn't pass.

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict — the script alone decides how many retries a task gets; no cap is written here.

- **`retry`** → re-dispatch the **same task** as a fresh subagent, passing the recorded failure as feedback.
- **`stuck`** → the script judged this task's failures aren't converging (too many attempts, or a repeating failure signature) — go to §5.4, which marks it terminal.
- **`halt-budget`** → the batch's dispatch budget is exhausted. Halt the loop and go to §9's batch-end review with whatever work is done so far.
  - This is the same backstop §5.5 can hit on a pass — it's checked before this call even looks at the fail/timeout result.

Load `debug-standards` if you need to diagnose why a task keeps failing before its next retry.

### 5.4. Mark terminal, chain-abort dependents, advance

A task becomes terminal without a `[Done]` two ways: the subagent self-reports `blocked` (§4.4), or §5.3's verdict is `stuck`. Handle both the same way from here.

**A self-reported block bypasses the script entirely.** `implement-loop-state.sh` only accepts `result` of `pass`, `fail`, or `timeout` — recording `blocked` as an attempt result crashes it.
So on a block, skip the attempt record and the script call: set `status: "blocked"` and `reason: "blocked"` on that task directly.

**A `stuck` verdict is already backed by a recorded fail/timeout attempt (§5.3).** Set that same task to `status: "blocked"` and `reason: "stuck"`.
`status` drives flow — blocked tasks are excluded from the next pick — while `reason` keeps the finer stuck-vs-blocked label for the batch-end report.

**Chain-abort the task's dependents, before picking what runs next.** Read `plan_<slug>.md`'s "Depends on" lines and walk them transitively.
Any task that depends on the one just marked terminal — directly, or through another dependent — also gets `status: "blocked"` and `reason: "blocked-upstream"`.
This is what makes chain-abort hold: if A goes terminal and B depends on A, B is marked before the orchestrator looks for a next task.
So B can never be picked — the same walk catches a C that depends on B, one hop further out.
Flip `plan_<slug>.md` to `[Blocked]` for the terminal task and every dependent this just chain-aborted (§6).

**Pick the next task yourself — the script can't.** `next-task` only comes out of a `pass` attempt (§5.5), and this task didn't pass.
Scan `tasks[]` in order for the first entry whose `status` is neither `done` nor `blocked`, and re-run §1.6–§1.7 + §3 on it.
This is a plain list filter, not loop math — no count or threshold enters into it, so it stays out of the script's job.
Find none — every task is terminal. Set `phase: "gates"` and move to §8's batch test-presence gate.

### 5.5. Advance

On a clean verify (§5.1, §5.2): record the attempt with `result: "pass"` and the token count noted at dispatch (§4).

Flip that task to `status: "done"` and `reason: "done"` in the state file — before calling the verdict script, not after.
The order matters for later tasks, not this one: picture tasks A and B, with A already passed.
Evaluating B's own verdict call filters `remaining` by `status`, so a still-`pending` A is not excluded and gets re-selected as B's "next" task — a redundant re-dispatch.
Flipping A to `done` first is what keeps it out.

Also flip `plan_<slug>.md` to `[Done]` (§6) and record the subagent's `[Scout]` notes there.

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict:

- **`next-task`** → its `task` field names the next task-id; re-run §1.6–§1.7 + §3 on it. §1.1–§1.5 and §2 do not repeat.
- **`gates`** → every task is terminal, and the last one to get there passed.
  - Set `phase: "gates"` — the same phase §5.4's queue-empty scan reaches when the last task was blocked or stuck instead.
- **`halt-budget`** → the batch's dispatch budget is exhausted. Halt the loop and go to §9's batch-end review with whatever work is done so far.

## 6. Status markers (plan_<slug>.md task title)

The orchestrator owns plan_<slug>.md status edits (`[Doing]` / `[Done]` / `[Blocked]` / `[Deferred]` / `[Dropped]`); the subagent never touches them.

Status is a file edit only, never committed (plan_<slug>.md is session-scoped per `spec-driven-development`).

The full marker table, placement rule, and per-state semantics live in [`references/status-markers.md`](references/status-markers.md). Load when flipping status or handling a non-`[Done]` terminal state.

## 7. Commit model

The **subagent** produces the commits. A task lands **at least 1 commit** — RED + GREEN cycles share the base (tests + impl together). Refactors land as their own task.

Counts: 1 (clean), 2 (+refactor), 3 (+scout fix), etc. Never zero.

Never auto-invoke `/refactor` or `/auto-review` **mid-task** — those belong to the user, or to the batch-end tail subagents in **report-only** mode (§9).

## 8. Batch test-presence gate

This gate runs once after the loop, before §9's tails.
It verifies every planned test the plan declared actually landed in the batch's commits.

§5.2's per-task check could run inline because the orchestrator never saw that task's implementation.
That no longer holds at batch scope — by now the orchestrator has watched every task's results flow through it, so it is no longer an unbiased judge.
This gate is therefore a fresh-context `deep-reviewer` dispatch, not an inline orchestrator check.

**Entry.** Run this when `phase` is `gates` — the state §5.4's queue-empty scan and §5.5's `gates` verdict both set.
A `halt-budget` verdict never reaches here: it routes straight to §9 from §5.3/§5.5, upstream of this gate, so the gate has no budget branch of its own.

**Dispatch.** Spawn ONE `deep-reviewer` subagent via the Agent tool — fresh context, Opus + max effort, which is that agent type's built-in tier.
Pass it the resolved `plan_<slug>.md` path, the diff range `<BATCH_BASE_SHA>..HEAD`, and the batch's task IDs.
Read those IDs from the state file's `tasks[]` — the plan file holds every task, including ones this batch never ran.

**What the deep-reviewer does.** Iterate exactly the batch task IDs it was handed — never every `### N.` heading in the plan, which lists tasks other runs owned.
For each ID `<N>`, run `~/.claude/skills/spec-driven-development/scripts/extract-planned-tests-for-task.sh <plan-path> <N>` to get that task's planned-test titles.
Exit-code handling matches the per-task procedure — see [`references/planned-test-verification.md`](references/planned-test-verification.md) for the exit-2 / exit-1 / empty-stdout meanings, rather than restating them.
Grep the `<BATCH_BASE_SHA>..HEAD` diff for each title as a deterministic pre-pass.
Apply an AI semantic check ONLY to the titles grep didn't match.
Return a per-title `found` / `missing` verdict, plus the list of tasks that declared `**Tests (planned)**: N/A`.

**All found, or every task N/A — the gate passes.**
If every task was N/A, note the explicit TDD opt-out so §9's package can state it.
Set `phase` to `tails` and proceed to §9.

**Any missing — run one fix round, try-once.**
For each task with missing titles, re-dispatch THAT task's subagent (fresh, per §4) with its missing titles as feedback.
The subagent owns writing them (RED → GREEN); you never hand-write tests.
Increment `gate_dispatches` in the state file by one per fix dispatch.
Then re-gate ONCE — a second `deep-reviewer` pass, same contract.

- Re-gate all found → pass; set `phase: "tails"` and go to §9.

- Re-gate still missing → record the still-missing titles for §9's package, then set `phase: "tails"` and go to §9 so the package surfaces them. Do NOT loop, do NOT hand-fix.

**Budget note.** This gate never calls `implement-loop-state.sh`.
The `gate_dispatches` it increments are accounted by the script's budget backstop at §9's next verdict call, which returns `halt-budget` there if the ceiling was blown.
Keeping the accounting in the script is the invariant — do not "helpfully" add a script call here.

## 9. Batch-end review & tail subagents

After the last task is terminal (`[Done]`, blocked, or the batch halted on budget/stuck), run the batch-end flow over `<BATCH_BASE_SHA>..HEAD`, then present the whole batch for your async review.

That async review **is** the handshake this skill replaces the per-task gate with.

The flow, in one pass: repo-green check; two report-only `deep-reviewer` tails (`/refactor` then `/auto-review`); triage; metrics; package print + diffview pane; opt-in draft PR, then finalize.

Every step — ordering, spawn contract, failure handling, finalize — is owned in full by [`references/batch-end.md`](references/batch-end.md). Load at batch end.
