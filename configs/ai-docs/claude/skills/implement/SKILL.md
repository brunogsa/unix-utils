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

`<task-ids>` is one numeric task prefix or a comma-list of them — `5`, or `1, 2, 3` from the plan in CWD. 1 space after commas.
Each ID matches the **exact** numeric prefix of a plan heading, and matches exactly one — a plan whose ids collide is malformed, and §1.3's checker rejects it before anything runs.

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
  Each re-grounds from durable artifacts (the plan, the spec, `git log`), not session history.

Run subagents on **Sonnet** (execution is mechanical); keep orchestrator on stronger model. Tasks run **sequentially** — each reads the prior task's commits + the plan's notes first.

### A PR-label run is the same batch flow, repeated once per PR

`/implement PR-1, PR-2` resolves each label to its own task-id list, then runs **§3 through §9** once per PR, strictly in the order given.
All of §1 and §2 are shared by the whole list and never repeat.
So every PR's gate, tails, diff range, and PR body scope to that PR's own commits alone, never the whole list's.

The per-PR iteration order, the fail-fast stop predicate between PRs, label resolution, branch creation, and manifest writes all live in [`references/pr-awareness.md`](references/pr-awareness.md).
Load it when the arg is a PR-label; a plain `<task-ids>` run never does, and the sections below assume this without restating it.

### Chain-abort, with no human gate

- **Blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision):
  - Record it, **never guess past it**, and continue with the tasks that don't depend on it.
  - Once nothing runnable is left the run **halts** and waits for you (§5.5).
  - So you come back to a maximal batch and one list of blockers — never to a gate or a review package with a task still blocked.

- **Work that fails verification** → re-dispatch the same task with the failure as feedback; the verdict script decides how many attempts it gets (§5.2). Surface it only if it still fails.

## 1. Pre-flight (orchestrator)

This skill never merges or deletes a worktree on its own, whether §1.2 asked for one or not.

**§1.1–§1.5 and §2 run once per invocation**, in that order, before any execution.
§3 then starts each unit — the whole batch on a `<task-ids>` run, one PR at a time on a PR-label run.

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

Everywhere below, the plan and the spec refer to these resolved paths.

### 1.2. One up-front interview

Ask everything at once, in a single message, before any dispatch.
This is the only round of questions in the whole run — the batch is unattended from here to the review package.
Mid-run `.env` needs are self-served (copy from the original checkout) rather than asked.

- **Plan pick**, only when §1.1 found multiple candidates.
- **Run in a git worktree?** (yes/no) — on yes, §1.4 creates it from HEAD and symlinks files in.
- **Open a draft PR at batch end?** (yes/no).
- **Run refactor + auto-review batch-end tails?** (yes/no, default yes) — no skips §9.2–§9.4; §9.1's gate always runs.
- **Base-branch confirmation** — show `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` as the default; let the user confirm or override.

Record all answers (four, or five with plan-pick) before proceeding — §2.3 persists them to the state file.

### 1.3. Re-validate both dependency graphs — once, before any execution

Run both deterministic checkers on the resolved plan, before §2 seeds anything and before the first dispatch:

```bash
~/.claude/skills/spec-driven-development/scripts/check-tasks-dag.sh <plan-file>
~/.claude/skills/spec-driven-development/scripts/check-pr-dag.sh <plan-file>
```

**Both run exactly once per invocation, PR-label or not** — never again per task, per PR, or on any retry.
`check-pr-dag.sh` passes trivially on a plan with no PR Breakdown, or with the literal "Single PR." escape, so there is no mode to branch on.

Self-review already validated both graphs, but the plan stays hand-editable, so a later edit can reintroduce a cycle, a dangling dependency, or a duplicate id.
Catching that here, before any commit exists, is what makes every `Depends on` chain safe to walk.
§5.3's chain-abort and each PR's parent lookup both assume a valid DAG and never re-check it.

A non-zero exit stops the run: surface the script's own stderr diagnostic verbatim and fix the plan before re-invoking.

### 1.4. Worktree setup (only when §1.2 answered yes)

Creation and file-symlink mechanics live in [`references/worktree-setup.md`](references/worktree-setup.md). Load when §1.2 answered yes.

When §1.2 answered no, skip this step; the batch-end package omits the merge-back reminder, since no worktree exists to merge back.

### 1.5. Resolve the PR-labels (only when the arg is a PR-label)

Resolve every `PR-N` in the arg to its task-id list now, before §2 seeds anything, so §2 can see the whole run.

Resolution and per-PR branch creation live in [`references/pr-awareness.md`](references/pr-awareness.md). Load it here.

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

The TaskList carries **status only**. Attempt counts, gate outcomes, and fix SHAs live in the JSON state file (§2.3), which is the single machine-checkable record and the only one the scripts read.

### 2.2. One reminder per batch-end step (they survive compaction)

After a batch's task entries, seed its batch-end steps as **separate** `[Reminder]` entries — the CLAUDE.md `[Reminder]` category, durable reminders of a later step, each producing no commit of its own.

One reminder per step, never one chain covering all of them: a task has a single `completed` flag, so a step-level skip or failure would have nowhere to land.

Seed exactly these five, in this order, prefixed with the owning `PR-N ·` on a PR-label run:

```
[Reminder] Batch-end 1/5: planned-test presence gate (§8)
[Reminder] Batch-end 2/5: repo-green gate — full suite + full lint, fix-loop until green (§9.1)
[Reminder] Batch-end 3/5: review tails ∥ then triage (§9.2–§9.4)
[Reminder] Batch-end 4/5: push + open the PR via create-pr (§9.5, only when pr.wanted)
[Reminder] Batch-end 5/5: package print, diffview pane (§9.5, success path only)
```

The PR is seeded **before** the package on purpose: §9.5 presents the batch only once the run actually succeeded, and on a PR-wanted run that means the PR is already open.

Flip each to `in_progress` when its step starts and `completed` when it lands; a step the interview turned off (tails, PR) completes with a one-line note that it was skipped by request.

Keep the subjects free of run-specific values like `BATCH_BASE_SHA` — a subject needing them could not be seeded upfront at all.

This complements the Stop hook — the hook blocks *stopping* early, these entries keep the remaining steps *in view*.

### 2.3. Write the state files and the scratchpad — now, then keep them current

Create the run's durable state **immediately after §2.2's reminders land** — before the first unit starts, never at the end.

Two artifacts, both written here and updated as the run goes:

- **One JSON state file per unit** — the machine-checkable record the scripts and the hooks read.
  - `/tmp/implement_<session_id>.json` on a plain `<task-ids>` run.
  - `/tmp/implement_<session_id>_pr<n>.json` per PR on a PR-label run (`_pr1`, `_pr2`, …) — one file per label in the arg, **all created now**, not lazily as each PR's turn comes up.
- **One markdown scratchpad** — `/tmp/implement_<session_id>.md`, the narrative surface the JSON has no shape for: decisions and their why, blocks with exactly what each needs, `[Scout]` notes, rejected approaches, artifact paths.

Each state file has exactly this shape:

```json
{
  "version": 2,
  "session_id": "<session_id>",
  "slug": "<slug>",
  "pr_label": "",
  "phase": "tasks",
  "start_sha": "<HEAD before this run touched anything>",
  "batch_base_sha": "",
  "tasks": [{ "id": "1", "status": "pending" }],
  "attempts": [],
  "gate_dispatches": 0,
  "tails": { "wanted": true, "refactor_report": "", "auto_review_report": "" },
  "worktree": { "created": false, "path": "", "branch": "" },
  "pr": { "wanted": false }
}
```

- `start_sha` is `git rev-parse HEAD` taken **before any branch is created and before any task is dispatched**, identical in every unit's file.
  - It is the run's anchor, naming where the repo stood when it began.
- `batch_base_sha` stays `""` until that unit actually starts (§3.2) — a dependent PR branches off its parent, so its base does not exist yet.
- One `tasks[]` entry per task-id that unit resolved, each `status: "pending"`; `worktree` / `pr` / `tails.wanted` come from §1.2's answers.
- `pr_label` is `""` on a plain run, else the `PR-N` that file belongs to.
- §5.2/§5.4 append `attempts[]` entries as `{ "task", "n", "result", "signature", "at" }`.

**Update both artifacts as they go — every flip, attempt, verdict, report path, and block the moment it happens.**
The Stop hook, the compact-reminder hook, and the verdict script all read them to know where the run stands, and a compaction or a kill keeps only what is already on disk.
Writing them at the end would leave them empty at the one moment they are needed.

**There is no resume path.** A leftover state file from an earlier run is stale, never adopted: delete it and start over.
An unattended batch that stopped needs a human decision anyway, so re-deriving half-finished state costs more than re-running it.

## 3. Start a unit (once per PR, or once for a `<task-ids>` run)

§1 and §2 ran for the whole invocation. §3 is the per-unit entry, run once before that unit's first dispatch and never again mid-loop.

### 3.1. Check out this unit's branch — once, here, by the orchestrator

**Only the orchestrator ever creates or switches a branch, and only at this point.**
No task subagent checks anything out; every task in the unit commits on the branch this step leaves checked out.
Deciding once, up front, is what keeps a unit's whole commit range on one branch — a mid-loop checkout would split a batch across two.

On a plain `<task-ids>` run there is nothing to do: the run stays on the current branch.

On a PR-label run, ask once, then act:

```bash
~/.claude/skills/implement/scripts/need-git-checkout.sh <plan-file> <PR-N> <worktree-path>
```

`no` → dispatch this PR's tasks on the current branch. `yes` → create this PR's branch now, per [`references/pr-branch-creation.md`](references/pr-branch-creation.md).

### 3.2. Capture `BATCH_BASE_SHA`, then recap what it sits on

Capture HEAD as `BATCH_BASE_SHA` **after** §3.1's checkout — the branch decides what this batch is measured against.
Write it into this unit's state file as `batch_base_sha`; §5, §8, and §9 all read it back from there rather than recomputing it.

Then recap the work this unit builds on, in 3–5 lines, from `git log <base-branch>..HEAD`.

**Read the commit messages, not the diff.** Commit bodies carry the *why* a diff cannot show, and this repo's commits are written to be rich.
Open the diff only for a commit whose message genuinely leaves you unable to tell what it did — never as the default pass.

Don't dump the log into chat; each task subagent re-derives its own context from `git log` at dispatch.

### 3.3. Match this unit's task-ids

Exact-match each task-id against the numeric prefixes of the plan's task headings.

A prefix matching more than one heading is a malformed plan, not a question for you.
§1.3's `check-tasks-dag.sh` already rejected duplicate ids, so a collision here means the plan changed underneath the run.
Stop and say so — never guess which heading was meant.

### 3.4. Activate a task

Per task, as it becomes the active one — the only orchestrator work between two dispatches:

- `TaskUpdate` that task to `in_progress`. Task-level status only; sub-steps never become TaskList items.
- Give it a **breadcrumb** — a coarse outline of its sub-steps (e.g. the plan's acceptance-criteria titles), so the list conveys the task's gist without RED-GREEN detail.
- Pick its checklist path, `/tmp/implement_substeps_<slug>_<id>.md`, and push that path into the dispatch prompt (§4.1).

**The orchestrator never writes that checklist file.**
The subagent writes it, from the dispatch prompt, before touching code — one item per RED-GREEN cycle, flipped done as each lands, plus an evidence section at the end.
Those mechanics live in `~/.claude/agents/tdd-coder.md`; edit that file and this section together.

Your only interest in it is that it **exists** and that §5.1's reviewer can read it — a contract, not scratch, since it is the evidence the whole verify is judged on.

### 3.5. Mid-flight sub-steps

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

- The task's plan slice: heading, brief, acceptance criteria, planned-test titles, verification command.
- The task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.
- `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.
- The checklist file path (§3.4) — the subagent writes that file itself, from this prompt.

Everything invariant — checklist write/resume mechanics, preloaded standards, commit rule, report shape, and pull-from-CWD items (plan/spec files, `git log`, source reads) — is baked into the tdd-coder agent definition; don't re-push it.

### 4.2. Mid-execution design forks — the subagent never spawns a reviewer

The task subagent **never** spawns a subagent of its own, reviewer or otherwise.
The harness would allow one more level; this skill spends none of it, so every dispatch stays visible, attributable, and bounded by §4's Monitor cap.

`tdd-coder.md` owns how it resolves a fork the plan didn't pre-decide; only the outcome reaches you (§4.4).
A **soft** fork arrives as a Deviation, the common case; a rare **hard** one arrives as `blocked`, which is already what a genuinely open decision means here.

The second opinion isn't lost, just deferred: §9.2–§9.3's tail pair reads the whole batch diff against spec and plan — a wider review than a mid-task reviewer seeing one fork in isolation.

### 4.3. Routing mid-execution discoveries

Anything the subagent uncovers outside its task's core work routes through one of three channels, all defined in `tdd-coder.md`:
**Drift** (fix in place), **abstract-in-place** (dissolve it into the code), **Scout** (leave it untouched and return it).

There is no separate carry-forward digest — the durable artifacts carry it.
A Drift fix travels in its commit body, which the next subagent reads via `git log`.

**Only Scouts need you.** Record each returned one as a `[Scout]` note on the plan's task breakdown, which is the surface the next subagent reads.

### 4.4. Report back

The subagent returns a structured report (text), never a silent "done" (shape mirrored in `~/.claude/agents/tdd-coder.md` — edit both together):

- **Status**: `done` / `blocked`.
- **Commits**: the SHAs it created, with subjects.
- **Self-verification**: the verification command it ran and its result; the planned-test titles it added.
- **Deviations**: sub-steps it inserted into its checklist mid-flight, soft design-forks resolved (with the choice), Drift fixes folded in.
- **For the orchestrator to record**: `[Scout]` items to note on the plan; any block, with exactly what's needed to clear it.

## 5. Verify, retry & advance (orchestrator)

No human gate. Every `done` report is judged by a fresh pair of eyes before the loop advances.

### 5.1. Verify the result — delegated, evidence-only

**The orchestrator does not verify the work itself, and nothing is re-run.**

Its own part is one cheap check: the checklist file exists at the path §3.4 assigned. A missing file is a straight `fail` — no dispatch needed.

Everything else goes to one `agent(subAgent=general-purpose, title=Verify task <N>: <task subject>, model=sonnet, effort=high)`, dispatched in the **foreground** — the loop cannot advance without its verdict.

Push into its prompt: the checklist file path, the subagent's report text verbatim (§4.4), the task's plan slice, and `BATCH_BASE_SHA`.

Ask for one verdict — `pass` or `fail` — with the specific mismatch quoted on a fail. It judges exactly three things:

- **Every checklist item is checked off.** An unchecked item means the subagent stopped short of its own plan.
- **The evidence section stands on its own** — it names the commits and pastes verification output showing the command passing.
- **The report and the evidence agree** — same commits, same tests, same deviations.

Its only repo tool call is a `git log <BATCH_BASE_SHA>..HEAD` existence check on the named SHAs.
It re-runs no tests, no lint, no verification command: the evidence is either sufficient on its face or it is not, and "not" is a `fail`.
That is the pressure keeping tdd-coder's evidence honest — a subagent that summarizes instead of pasting fails its own verify.

Why delegate: the orchestrator wrote the dispatch and holds the batch's assumptions, so its own read is that session's optimism a second time.
A fresh context sees only the file and the question, which is what makes the verdict worth having.

Either way the outcome becomes one recorded attempt and one script verdict — §5.2 on a failure or block, §5.4 on a pass. No path skips the script.

### 5.2. On failure or a block — record the attempt, obey the verdict

A failed §5.1 verify, a §4 timeout, and a subagent's self-reported `blocked` (§4.4) all take the same path: record the attempt with `result` set to `fail`, `timeout`, or `blocked`, then run:

```bash
~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>
```

Obey its verdict — `retry`, `stuck`, or `halt-budget`. The script alone decides how many retries a task gets, and a `blocked` attempt always verdicts `stuck`, since only the human can clear it.

`halt-budget` stops the run where it stands (§5.5). It never routes to the gates or the batch-end flow: a batch that burned its dispatch budget is a batch that didn't finish.

Full verdict semantics, attempt-recording fields, and the `debug-standards` load live in [`references/failure-verdict.md`](references/failure-verdict.md). Load only on a failed verify.

### 5.3. On `stuck` — mark terminal, chain-abort dependents, advance

Set that task to `status: "blocked"`, with `reason: "blocked"` when the attempt was a self-reported block and `reason: "stuck"` when it was repeated failures.

`status` drives flow — blocked tasks are excluded from the next pick — while `reason` keeps the finer stuck-vs-blocked label for the batch-end report.

`TaskUpdate` its TaskList status to `completed`; the tool has no `blocked` state, and the state file's `reason` is what distinguishes it.

**Chain-abort the task's dependents, before picking what runs next.** Read the plan's "Depends on" lines and walk them transitively.
Any task that depends on the one just marked terminal — directly, or through another dependent — also gets `status: "blocked"` and `reason: "blocked-upstream"`, plus TaskList status `completed`.
Mark them before the orchestrator looks for a next task, so none can be picked.
Flip the plan to `[Blocked]` for the terminal task and every dependent this just chain-aborted (§6).

**Pick the next task yourself — the script can't.** `next-task` only comes out of a `pass` attempt (§5.4), and this task didn't pass.
Scan `tasks[]` in order for the first entry whose `status` is neither `done` nor `blocked`, and re-run §3.4 on it.

Find none — every task is terminal, and at least one of them (this one) is terminal-without-`[Done]`.
**Do not go to the gates.** Go to §5.5 and halt.

### 5.4. On a clean verify — advance

Record the attempt with `result: "pass"` and the token count noted at dispatch (§4).

Flip that task to `status: "done"` and `reason: "done"` in the state file — before calling the verdict script, not after.
The script picks the next task by `status`, so a passed task left `pending` would later be re-selected as another task's "next" and redundantly re-dispatched.

Also flip the plan to `[Done]` (§6), record the subagent's `[Scout]` notes there, and `TaskUpdate` its TaskList status to `completed`.

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict:

- **`next-task`** → its `task` field names the next task-id; re-run §3.4 on it. §1, §2, and §3.1–§3.3 do not repeat.
- **`gates`** → **every** task in this unit is `done`. Set `phase: "gates"` and go to §8's test-presence gate.
- **`halted`** → every task is terminal but at least one ended blocked or stuck. Go to §5.5.
- **`halt-budget`** → the unit's dispatch budget is exhausted. Go to §5.5.

**Only this script sends a unit to the gates, and only when nothing is blocked.**
Never infer `gates` yourself from "the queue looks empty" — a queue empties for two very different reasons, and the script is the one that can tell them apart.

### 5.5. Halt — stop where you stand and wait for the human

This is the single exit every dead end in the run routes to. Entry, from anywhere:

- A `halted` or `halt-budget` verdict (§5.2, §5.4).
- §5.3's scan finding no runnable task left while some task is terminal-without-`[Done]`.
- §8's test-presence gate exhausting its fix attempts with titles still missing.
- §9.1's repo-green gate exhausting its fix attempts with a batch-caused failure still red.
- §9.5's PR dispatch failing when a PR was requested.

Then, wherever you came from:

- Set `phase: "halted"` in this unit's state file — and in every remaining unit's file too.
  - The Stop hook globs the whole session and blocks on any unit still at `tasks`.

- Write into the scratchpad, per blocked task, **exactly what a human must do to clear it** — that list is the whole point of stopping here.
- Leave this unit's remaining batch-end `[Reminder]` entries `pending`. They didn't run, and a pending entry is the honest record of that.
- **Run nothing further** — whichever of the gate, the tails, the triage, the package, the diffview, and the PR you hadn't reached yet stays unrun.
  - Each presupposes a finished batch: gating a partial one flags tests never meant to exist yet, and a package invites review of work that isn't there.

- On a PR-label run, the remaining PRs stay untouched — no branch, no dispatch.
- Say it in one short message: which tasks are blocked, and what each one needs. Nothing else.

Then stop. The Stop hook releases on `phase: "halted"`, so the session is allowed to end here and wait.

Clearing the blocker is a fresh `/implement`, not a resume: delete this unit's state file first (§2.3).

## 6. Status markers (plan task title)

The orchestrator owns the plan's status edits (`[Doing]` / `[Done]` / `[Blocked]` / `[Deferred]` / `[Dropped]`); the subagent never touches them.

Status is a file edit only, never committed (the plan is session-scoped per `spec-driven-development`).

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
A per-task one would verify each test at its own commit point and miss what a later task did to it, so the batch's final state is the only state worth checking.

**Entry: `phase` is `gates`**, which only §5.4's `gates` verdict sets, and only when every task in the unit is `done`. Never skip it to reach §9 faster.

**Read [`references/batch-test-presence-gate.md`](references/batch-test-presence-gate.md) on entry** — it owns the `deep-reviewer` dispatch contract, the title-matching procedure, the fix loop, and the budget invariant.

Missing titles are **fixed in a loop**, not once: re-dispatch the owning task's subagent, re-gate, repeat, under the same per-task attempt caps and 1-hour Monitor cap every other dispatch obeys.
A planned test is not optional, so one failed fix round is no reason to accept its absence — only the attempt cap is.

Exhausting those attempts with titles still missing is a block like any other: go to §5.5 and halt.
Only an all-found (or all-N/A) gate sets `phase: "tails"` and proceeds to §9.

## 9. Batch-end review & tail subagents

Reached only by a unit whose **every** task is `[Done]` and whose §8 gate passed; a unit that halted stopped back at §5.5 and never arrives here.

Run the batch-end flow over `<BATCH_BASE_SHA>..HEAD`, then present the whole batch for your async review — that review **is** the handshake this skill replaces the per-task gate with.

**Stage order: §9.1 → (§9.2 ∥ §9.3) → §9.4 → §9.5.** This is the only place that order is written down.

**Load [`references/batch-end-review.md`](references/batch-end-review.md) on entry.**
It expands every stage below — spawn contracts, failure handling, the package contents, the diffview command, and Finalize — and routes on to `batch-end-pr.md` for the PR.
Read it late, here: by batch end a compaction has usually dropped whatever you read earlier.

§9.1 always runs, regardless of the tails toggle (§1.2).

**Toggle yes (default):** dispatch both tails in the same turn (both `run_in_background`), wait for both, then §9.4.
Both are **mandatory**; the PR must not open until both reports are recorded.

**Toggle no:** skip §9.2–§9.4, go straight to §9.5 and state there that tails were skipped by request.
No retroactive re-run; invoke `/refactor` or `/auto-review` manually later.

This is a checklist, not a summary line: do each stage, don't collapse them.
Each bullet below carries the one invariant the reference must not be read as softening.

- **§9.1 — repo-green gate.** Full lint + full test suite, repo-wide, never scoped to touched files.
  A red repo is fixed **in a loop** through `agent(subAgent=tdd-coder, ...)` dispatches until green, under §4's Monitor and attempt caps.
  You never hand-fix, and never scope the gate down to make it pass.
  A failure the batch did not cause is a `[Scout]`: reported, left unfixed, and it does not hold the gate.
  Attempts exhausted with a batch-caused failure still red → §5.5.

- **§9.2–§9.3 — the deep-reviewer tail pair**, dispatched via [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../code-review-pipeline/references/deep-reviewer-tail-pair.md) with `<BASE_REF>` = `<BATCH_BASE_SHA>`.
  They run only once §9.1 came back green — a tail on a red repo reviews a state about to change under it.
  Record each report's **path** in the state file, and confirm the file is actually there.

- **§9.4 — triage.** Report-only, always. **This skill never applies a finding — not one, not a trivial one, not on request.**
  That keeps the diff the human reviews exactly the diff the tails reviewed.

- **§9.5 — finalize**, in order: PR manifest entry → open the PR → print the package → diffview pane → `phase: "presented"` and delete the state file.
  **One `agent(subAgent=create-pr, title=Open the batch PR)` owns the whole PR** — composing the body, pushing the branch, creating the PR. You never write a body and never push.
  Pass it the `spec_<slug>.md` + `plan_<slug>.md` §1.1 resolved, plus the resolved `PR-N` on a PR-label run — never auto-detected.
  **The package prints only on success.** A requested PR that failed to open is a §5.5 halt; a run with `pr.wanted: false` prints normally.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
