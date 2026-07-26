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

- **Orchestrator** (this session) — pre-flight, plan review, TaskList (parent tasks only), dispatch, post-commit verification, batch-end report.
  Holds only orchestration state, never task implementation context.

- **Task subagent** — one fresh context per task, sequential: decompose into its own checklist file, RED-GREEN work, self-verify, commit, report.
  Each re-grounds from durable artifacts (plan_<slug>.md, spec_<slug>.md, `git log`), not session history.

Run subagents on **Sonnet** (execution is mechanical); keep orchestrator on stronger model. Tasks run **sequentially** — each reads the prior task's commits + plan_<slug>.md notes first.

### Chain-abort, with no human gate

A good spec/plan — required for any `/implement` run — makes mid-batch stalls almost never fire. When one does:

- **Subagent blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision):
  - Record it, **never guess past it**, leave that task where it stopped, and continue with tasks that don't depend on it.
  - Every block lands in the batch-end report for you to clear in one pass.

- **Subagent's own work fails the orchestrator's post-commit verification** → re-dispatch the same task with the failure as feedback; the verdict script decides how many attempts it gets (§5.3).
  - Surface it only if it still fails. Execution correctness is the AI's job, not yours.

## 1. Pre-flight (orchestrator)

The up-front interview (§1.2) asks whether this run creates its own git worktree.
On yes, §1.3 creates and populates it.
On no, this skill runs in the current checkout, and never merges or deletes a worktree on its own either way.

In a multi-task batch (`/implement 1, 2, 3`), **§1.1–§1.5 and §2 run once** at the start; **§1.6–§1.7 run once per task** as each becomes active.

In a PR-label list (`/implement PR-1, PR-2`), the boundary shifts: §1.1–§1.3 and §2 run once for the whole list; §2.1, §2.2 and §1.4–§9 repeat once per PR — see [`references/pr-awareness.md`](references/pr-awareness.md).

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
- **Run pre-dispatch orchestration review?** (yes/no, default no) — no skips §2, dispatching the first task after pre-flight.
- **Run refactor + auto-review batch-end tails?** (yes/no, default yes) — no skips §9.2–§9.4; §9.1's gate always runs.
- **Base-branch confirmation** — show `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` as the default; let the user confirm or override.

Record all answers (five, or six with plan-pick) before proceeding — §1.5 persists them to the state file.

### 1.3. Worktree setup (only when §1.2 answered yes)

Creation and file-symlink mechanics live in [`references/worktree-setup.md`](references/worktree-setup.md). Load when §1.2 answered yes.

When §1.2 answered no, skip this step; the batch-end package omits the merge-back reminder, since no worktree exists to merge back.

### 1.4. Recap of work since base + capture `BATCH_BASE_SHA`

Capture HEAD as `BATCH_BASE_SHA` — the start of this invocation's commit range (reused in §4, §8, and §9).
Capture it **after** §1.3, so a new worktree's HEAD (same commit, different working directory) is what gets recorded.
In a PR-label list, capture it fresh per PR (right before that PR's branch decision), so each PR's gate/tails/diff scope to only its own commits — never the whole list's.

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
  "started_at": "<ISO-8601 now>",
  "presented_at": "",
  "tasks": [{ "id": "1", "status": "pending" }],
  "attempts": [],
  "gate_dispatches": 0,
  "tails": { "wanted": true, "refactor_report": "", "auto_review_report": "", "tokens": { "gate": 0, "refactor": 0, "auto_review": 0 } },
  "worktree": { "created": false, "path": "", "branch": "" },
  "pr": { "wanted": false },
  "orchestration_review": { "wanted": false }
}
```

- One `tasks[]` entry per matched task-id (`status: "pending"`); `worktree`/`pr`/`tails.wanted`/`orchestration_review.wanted` filled from §1.2's answers.
  - `pr_label` is `""` for a plain `<task-ids>` run, else the `PR-N` this file belongs to (`references/pr-awareness.md`).
  - §5.3/§5.5 append `attempts[]` entries as `{ "task", "n", "result", "signature", "tokens", "at" }`.
- **Found** → load [`references/preflight-state.md`](references/preflight-state.md) for the JSON-adoption mechanics that restore attempt counts and completed-task status.

### 1.6. Match `<task-id>`

Exact-match against numeric prefixes in `plan_<slug>.md` headings. On multiple matches (rare), ask the user which one.

### 1.7. Existing state (resume / dirty runs)

On a resume or re-run, reconcile any pre-existing task status and stray TaskList items before proceeding.
A clean first run skips this.
The reconciliation mechanics live in [`references/resume-reconcile.md`](references/resume-reconcile.md) — how this differs from §1.5's silent JSON adoption, and the per-state prompts (re-execute / resume / restart / revive).
Load it only on a resume or dirty run.

### 1.8. PR-label resolution & per-PR loop (only when the arg is a PR-label)

Runs at the start of **each** PR's iteration, before that PR's own §1.4 — each PR runs its own full §1.4–§9 batch, in order (branch → tasks → gate → PR).
Before the next PR's branch is created, every task in the batch must run and gate.

Before resolving the PR-N label, re-run `check-pr-dag.sh` against the live plan — it's symlink-shared and mutable for the rest of execution (§1.3), so self-review's earlier pass can go stale.

Stop before the next PR on any task ending terminal-without-`[Done]`, or a §9.1 gate failure; never skip ahead.

Full resolution, branch-creation, and stop-predicate mechanics live in [`references/pr-awareness.md`](references/pr-awareness.md). Load when the arg is a PR-label.

## 2. Orchestration review — fresh-context subagent, once before any dispatch

Runs only when §1.2's toggle is yes; on no, skip to §2.1, dispatch the first task.

Spawn a `deep-reviewer` subagent (Agent tool, `subagent_type=deep-reviewer` — its frontmatter pins model/effort, no override) once per invocation, after pre-flight and before dispatching.
Conduct an adversarial review of the whole batch (not per-task).
Fresh context: the plan was authored in-session, already convinced — reviewer sees only artifacts + question.

Challenge the batch as a whole: approach, ordering, dependencies, verification strategy. Take it seriously: fix the plan/batch if dependencies are missed; reconcile verification method challenges; skipping defeats the point.

This is the orchestrator's only plan-level review; the task subagent has its own mid-execution fork lever (§4.2).

### 2.1. Seed the batch-end `[Reminder]` task (survives compaction)

Right after the review and before the first dispatch, create **one `[Reminder]` task per batch-end** anchoring the whole §9 batch-end procedure in the TaskList.
Create it once per batch-end, never per task.
This is the CLAUDE.md `[Reminder]` category — a durable reminder to run a later step, producing no commit of its own.

**On a PR-label run this step repeats per PR**, seeded right after that PR's §1.4 captures its own `BATCH_BASE_SHA`, since §9 itself runs once per PR.
One reminder for the whole list would be struck `completed` at PR-1's §9.5, leaving PRs 2…N to run their batch-end with no compaction-surviving anchor.
This scenario — PRs 2…N lacking a compaction-surviving anchor — is the exact failure this task exists to prevent.
Seeding it after §1.4 is also what lets the subject carry that PR's real sha instead of the `<BATCH_BASE_SHA>` placeholder.

**Put the ordered step list in the task SUBJECT, not a description field** — only the subject re-surfaces in the turn-by-turn reminder.
A description needs an explicit `TaskGet` to read back, so after compaction it's as lost as the doc.
Encode the finalize checklist as an arrow chain in the subject — substituting the real sha for `<BATCH_BASE_SHA>`:

```
[Reminder] Batch-end §8-9: test-presence → repo-green → tails(refactor∥review) → triage → package → nvim DiffviewOpen <BATCH_BASE_SHA> → PR(create-pr, if wanted)
```

The steps map to §8's test-presence gate, §9.1's repo-green gate, then the two parallel review tails (§9.2 ∥ §9.3).
Triage runs (§9.4); then §9.5 prints the package, `open-in-tmux` opens the diff, and the `create-pr` PR runs last, only when `pr.wanted`.
That tail order is `references/batch-end-package.md`'s Finalize spine — the diff pane is editable, so a PR opened before it would ship a body the human never got to amend.

As each step lands, `TaskUpdate` the subject to mark it done — strike it or prefix `✓`.
This keeps showing which steps remain even after a compaction drops the doc-resident §9 steps from working memory.

Alongside the strike, `TaskUpdate` this task's `metadata` with the same per-step outcome — keys `test_presence`/`gate`/`tails`/`triage`/`package`/`diffview`/`pr`, in that execution order.
Each step's value is `"pending"` or `"done"` (`"skipped"` for `pr` when not wanted).
Triage, PR, and diffview completion have no JSON state-file equivalent — this metadata is their only durable, machine-checkable record.

Leave it `pending` through the task loop; flip it `in_progress` on entering §9 and `completed` only once the review package is presented (§9.5).
On a resume, before dispatch, check the TaskList for this task — a new session may not carry it.
If present, `TaskGet` its `metadata` first — the exact per-step record, sharper than `phase`'s coarse value.
If absent, re-create it and pre-strike the steps the state-file `phase` shows already done, since no metadata survived to read.

This complements the Stop hook: the hook blocks *stopping* before the batch is presented; this task keeps the steps *in view* so you run them unprompted.

### 2.2. Create all matched tasks in the TaskList upfront

Before dispatching task 1, create one TaskList entry for **every** task-id in this batch — not just the first one.
In a PR-label run, **this batch** means only the current PR's task-ids — §1.8's per-PR loop repeats this step fresh entering each PR, never every PR's tasks upfront.

Mark the first task `in_progress` and every other task `pending`. This shows the user the whole batch from the start, instead of tasks appearing one at a time as they activate.

Init each task's `metadata` to `{"pr_label": "<this run's pr_label, "" if none>", "attempt_count": 0, "gate_outcome": "pending", "fix_commit_shas": []}`.
§5.3–§5.5 update these fields as the task runs — never track them only in a prose subject/description or in chat scrollback.

## 3. Sub-step decomposition (subagent-owned, per task)

Sub-steps live in a **durable checklist file the subagent owns** — a `/tmp` markdown file — not the orchestrator's TaskList.

Two reasons: subagents have no TaskList/TodoWrite tool to create them, and keeping sub-steps off the orchestrator's list holds it at task-level macro visibility.

The orchestrator, per task, does this and no more (the parent task itself was already created for the whole batch in §2.2):

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

Spawn one fresh-context subagent per task via the **Agent tool** (`subagent_type=tdd-coder`, model omitted — the agent file pins sonnet and the subagent-model-guard hook enforces it), in the background (the default).

Cap the dispatch with a 1-hour `Monitor` timeout (`timeout_ms: 3600000` — the tool's documented maximum).
On expiry, call `TaskStop` on the subagent — the dispatch then resolves as a `timeout`, which §5.3 records and obeys exactly like a `fail`.

The harness re-invokes you with its report on completion, so you can still act on it.
Note the token count the Agent result reports for the run, defaulting to `0` when absent.
§5 records it into the attempt it creates — except on a self-reported block, which creates no attempt at all (§5.4).
Best-effort only; never gates the loop mid-run — overage surfaces later via the metrics script, not here.

The subagent runs the **full per-task lifecycle**.
Its invariant discipline — TDD rules, preloaded standards, checklist mechanics, routing channels, report shape — lives in the agent definition (`~/.claude/agents/tdd-coder.md`); the prompt pushes only the per-task data below.

### 4.1. Context contract

**Push** — embed verbatim in the prompt (the per-task data only the orchestrator holds):

- The task's `plan_<slug>.md` slice: heading, brief, acceptance criteria, planned-test titles, verification command.
- The task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.
- `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.
- The checklist file path (§3).

Everything invariant — checklist write/resume mechanics, preloaded standards, commit rule, report shape, and pull-from-CWD items (plan/spec files, `git log`, source reads) — is baked into the tdd-coder agent definition; don't re-push it.

### 4.2. On-demand fork review (subagent escape hatch)

The task subagent does **not** spawn a reviewer by default — the plan was already reviewed (§2).

The escape hatch itself lives in the agent definition.
On a mid-execution design fork the plan didn't pre-decide, tdd-coder spawns a fresh-context reviewer with explicit `model=opus` (judgment tier; the subagent-model-guard hook denies an unnamed model on an unpinned agent type).
This nested dispatch has no subagent_type pinned, so its turn bound is that agent definition's own maxTurns.
Never the orchestrator's 1-hour Monitor cap — that wraps only §4's and §8's top-level dispatches.

The orchestrator only sees the outcome:

- **Soft** fork — the subagent took the reviewer's default and flagged the choice under Deviations in its report (§4.4). Most forks are this.
- **Hard** fork — the subagent couldn't sensibly proceed and returned `blocked` (§4.4). Rare.

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

Unchecked items mean it stopped short of its own plan — treat that as a failed verify (§5.3) or a block (§5.4).

### 5.2. Planned-test presence check (post-commit)

Run the planned-test check against the subagent's commit range — the orchestrator didn't author the impl, so it can judge it inline; no nested subagent needed.

Full procedure in [`references/planned-test-verification.md`](references/planned-test-verification.md). Load on demand.

### 5.3. On failure — record and obey the verdict

On a failed §5.1/§5.2 verify or a §4 timeout, record the attempt, then run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey its verdict — `retry`, `stuck`, or `halt-budget`.

The script alone decides how many retries a task gets.

Also `TaskUpdate` that task's TaskList `metadata`: increment `attempt_count` and set `gate_outcome: "red"` — mirrors the JSON attempt record so a `TaskGet` shows the same failure without opening the state file.

Full verdict semantics, attempt-recording fields, and the `debug-standards` load live in [`references/failure-verdict.md`](references/failure-verdict.md). Load only on a failed verify.

### 5.4. Mark terminal, chain-abort dependents, advance

A task becomes terminal without a `[Done]` two ways: the subagent self-reports `blocked` (§4.4), or §5.3's verdict is `stuck`. Handle both the same way from here.

**A self-reported block bypasses the script entirely.** `implement-loop-state.sh` only accepts `result` of `pass`, `fail`, or `timeout` — recording `blocked` as an attempt result crashes it.
So on a block, skip the attempt record and the script call: set `status: "blocked"` and `reason: "blocked"` on that task directly.
Also `TaskUpdate` its TaskList `metadata.gate_outcome` to `"red"` directly — §5.3 never ran, so nothing set it yet.

**A `stuck` verdict is already backed by a recorded fail/timeout attempt (§5.3).** Set that same task to `status: "blocked"` and `reason: "stuck"`.
`status` drives flow — blocked tasks are excluded from the next pick — while `reason` keeps the finer stuck-vs-blocked label for the batch-end report.

Either way, `TaskUpdate` that task's TaskList status to `completed` — the tool has no `blocked` state; `metadata.gate_outcome: "red"` is what a `TaskGet` reads to tell a blocked task from a passed one.

**Chain-abort the task's dependents, before picking what runs next.** Read `plan_<slug>.md`'s "Depends on" lines and walk them transitively.
Any task that depends on the one just marked terminal — directly, or through another dependent — also gets `status: "blocked"` and `reason: "blocked-upstream"`.
Mark it before the orchestrator looks for a next task so it can never be picked.
Flip `plan_<slug>.md` to `[Blocked]` for the terminal task and every dependent this just chain-aborted (§6).
Also `TaskUpdate` each chain-aborted dependent's TaskList `metadata.gate_outcome` to `"red"` and status to `completed` — it never dispatched, so nothing else would ever close it out.

**Pick the next task yourself — the script can't.** `next-task` only comes out of a `pass` attempt (§5.5), and this task didn't pass.
Scan `tasks[]` in order for the first entry whose `status` is neither `done` nor `blocked`, and re-run §1.6–§1.7 + §3 on it.
§1.7 here is a direct pick, not a resume — its resume-reconcile mechanics apply only to an actual stale or dirty run.
Find none — every task is terminal. Set `phase: "gates"` and move to §8's batch test-presence gate.

### 5.5. Advance

On a clean verify (§5.1, §5.2): record the attempt with `result: "pass"` and the token count noted at dispatch (§4).

Flip that task to `status: "done"` and `reason: "done"` in the state file — before calling the verdict script, not after.
The script picks the next task by `status`, so a passed task left `pending` would later be re-selected as another task's "next" and redundantly re-dispatched.

Also flip `plan_<slug>.md` to `[Done]` (§6) and record the subagent's `[Scout]` notes there.

Also `TaskUpdate` that task's TaskList `metadata`: `gate_outcome: "green"`, `fix_commit_shas` from §4.4's reported SHAs, then flip its TaskList status to `completed`.

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict:

- **`next-task`** → its `task` field names the next task-id; re-run §1.6–§1.7 + §3 on it. §1.1–§1.5 and §2 do not repeat.
- **`gates`** → every task is terminal, and the last one to get there passed.
  - Set `phase: "gates"` — the same phase §5.4's queue-empty scan reaches when the last task was blocked or stuck instead.
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

§5.2 checked each task at its own commit point and can't see what later tasks did to those tests afterward.

**Entry: `phase` is `gates`** — the state §5.4's queue-empty scan and §5.5's `gates` verdict both set. Never skip it to reach §9 faster.

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

Record each report's **path** into `.tails.refactor_report`/`.tails.auto_review_report` (the file on disk is canonical, not a state-file copy) and its token count into `.tails.tokens.refactor`/`.tails.tokens.auto_review`.

**Both report files must exist on disk before proceeding (when tails were requested).**
If either tail's state field is still `""`, or the file it names is absent, that tail hasn't run.
Go back and run it; do not reach §9.5 with a missing tail report.

Implement-specific queuing/state-file mechanics: [`references/batch-end-review.md`](references/batch-end-review.md).

### 9.4. Triage

Follow the shared reference's triage section: read both reports, synthesize one prioritized summary, and present every finding — including ones that look low-risk — as an apply-offer.

**Never fold a finding into a batch-end commit on your own initiative.**
The auto-apply loop is opt-in, and that opt-in only comes from the user asking directly.
This is either by naming findings to apply after seeing this package (the reference's "Applying a single finding, on explicit request"), or by running `/loop-auto-review` themselves separately for the full loop-until-dry treatment.

### 9.5. Package, metrics, and opt-in draft PR

Print the batch-end package for the user's one-pass async review: commit-by-commit reading guide, the two tail reports (with your triage verdicts), any blocks/scouts, and the metrics summary.

Open the draft PR only when §1.2 recorded `pr.wanted: true`, targeting the confirmed base branch, and only when §9.1's gate came back green.

Opening the PR is the last of the batch-end steps — it runs after the package print and the diffview pane, and presupposes §9.1–§9.4 all ran.

**Never hand-write the PR body — always generate it via a fresh `create-pr` agent dispatch (`subagent_type=create-pr`), scoped to drafting only.**
The agent's own skill would push and create the PR itself; cap its dispatch to the drafted file so the orchestrator still owns the push and the existing-PR fallback.
A hand-authored body is a defect. Exact dispatch, conventions, and required content: `references/batch-end-pr.md`'s "Draft PR (opt-in)".

**Pass the exact `spec_<slug>.md` + `plan_<slug>.md` this batch resolved in §1.1, plus the resolved `PR-N` on a PR-label run — never auto-detected.**

Set the terminal phase per `references/batch-end-package.md`'s Finalize step.
Use `presented` (and delete the state file) only when every task is `done`.
Use `halted` (and keep it for resume) on a budget hit or any `blocked`/`stuck` task.

Every step — ordering, spawn contract, failure handling, finalize — is owned in full by [`references/batch-end-review.md`](references/batch-end-review.md), which routes on to its `batch-end-package.md` and `batch-end-pr.md` siblings. Load at batch end.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
