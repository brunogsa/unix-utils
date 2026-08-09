---
name: implement
description: "Execute plan_<slug>.md tasks end-to-end as fresh-context subagents, fully async. Trigger: /implement <id(s)> or natural language (\"let's implement that\", \"implement this plan\") when a plan_<slug>.md exists."
disable-model-invocation: false
words-budget: 4096
---

## Usage

```
/implement <task-ids> | <PR-label(s)>
```

`<task-ids>` is one numeric task prefix or a comma-list (1 space after commas) — `5`, or `1, 2, 3` — from the plan in CWD.
Each ID matches the **exact** numeric prefix of exactly one plan heading; colliding ids make the plan malformed, and §1.3's checker rejects it.

`<PR-label(s)>` is `PR-N` or a comma-list, same convention — `PR-1`, or `PR-1, PR-2` — from the plan's PR Breakdown. Resolves to its own task-id list.
See [`references/pr-awareness.md`](references/pr-awareness.md), loaded whenever the arg is a PR-label.

## Execution model — orchestrator + per-task subagents

`/implement` is **fully async**: it runs the whole batch unattended and hands you the finished commits — no per-task human handshake, only the batch-end review.

Two roles:

- **Orchestrator** (this session) — pre-flight, TaskList, dispatch, post-commit verification, batch-end report.
  Holds only orchestration state, never task implementation context.
  It is the **only** role that spawns subagents; a task subagent never nests another one.

- **Task subagent** — one fresh context per task: decompose into its own checklist file, RED-GREEN work, self-verify, commit, report.
  Each re-grounds from durable artifacts (the plan, the spec when one exists, `git log`), not session history.

Run subagents on **Sonnet** (mechanical); keep orchestrator on stronger model.
Tasks run **sequentially** — each reads the prior task's commits + the plan's notes first.

### A PR-label run is the same batch flow, repeated once per PR

`/implement PR-1, PR-2` resolves each label to its own task-id list, then runs **§3 through §8** once per PR, strictly in order.
§1 and §2 never repeat per PR — they run once, shared by the whole list.

Per-PR iteration order, the fail-fast stop predicate, label resolution, branch creation and recording, and each PR's gate/quality-gate/diff scoping live in [`references/pr-awareness.md`](references/pr-awareness.md).
Load it only on a PR-label run.

### Chain-abort, with no human gate

- **Blocked on something only the human can resolve** (missing access, upstream API down, a genuinely open decision): record it and **never guess past it**.
  Continue with tasks that don't depend on it.
  Once nothing runnable is left, the run **halts** and waits for you (§5.5).

- **Work that fails verification** → re-dispatch the same task with the failure as feedback; the verdict script decides the attempt count (§5.2). Surface it only if it still fails.

## 1. Pre-flight (orchestrator)

This skill never merges or deletes a worktree on its own, whether §1.2 asked for one or not.

**§1.1–§1.5 and §2 run once per invocation**, in that order, before any execution; §3 then starts each unit.

### 1.1. Locate the plan (and spec)

Glob in CWD (top-level only):

```bash
ls -1 plan_*.md spec_*.md 2>/dev/null
```

Resolve candidates with this decision tree — it never prompts; ambiguity becomes the interview's plan-pick question (§1.2):

- **Exactly one plan and one spec** → use both; print the resolved paths.
- **Multiple plans (or multiple specs)** → the plan-pick question lists the matches numbered; pair each plan with the spec sharing its `<slug>`.

- **No plan found** → the interview asks for the path; if none provided, **stop**.
- **Plan but no spec** → proceed plan-only, the spec is optional context.

Everywhere below, the plan and the spec refer to these resolved paths.

### 1.2. One up-front interview

Ask everything at once, before any dispatch — the only round of questions in the whole run (it may take two `AskUserQuestion` calls; each caps at 4 options).
Mid-run `.env` needs are self-served (copied from the original checkout) rather than asked.

- **Plan pick**, only when §1.1 found multiple candidates.
- **Plan path**, only when §1.1 found no plan — if still not provided, stop (§1.1).
- **Run in a git worktree?** (yes/no) — on yes, §1.4 creates it from HEAD and symlinks files in.
- **Open a draft PR at batch end?** (yes/no) — this decides the PR only; §8.3 pushes the branch either way.

- **Use GH stacked PRs?** (yes/no, default yes) — asked only on a PR-label run whose draft-PR answer was yes; a no keeps one PR per plan-PR, `Mode: merge`.
  - On yes, §1.5's eligibility check still decides (`native` needs a linear PR DAG + the `gh-stack` extension); when it holds, every task ships as its own PR layer at batch end.

- **Run the quality-gate batch-end tail?** (yes/no, default yes) — on yes, §8.1 runs `/quality-gate --auto-solve`; on no, it's skipped and the package says so.
- **Capture a full-suite green baseline before starting?** (yes/no) — on yes, §1.6 runs the full suite now and records pre-existing failures for §8.2 to diff against.

- **Run the repo-green gate at batch end?** (yes/no, default yes) — on yes, §8.2 runs; on no, it's skipped and the package says so.
  - Independent of the quality-gate toggle, decided fresh each run.

- **Base-branch confirmation** — show `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` as the default; let the user confirm or override.

Record all answers before proceeding — §2.3 persists them to the state file.

### 1.3. Re-validate both dependency graphs — once, before any execution

Run both checkers on the resolved plan, before §2 seeds anything and before the first dispatch:

```bash
~/.claude/skills/spec-driven-development/scripts/check-tasks-dag.sh <plan-file>
~/.claude/skills/spec-driven-development/scripts/check-pr-dag.sh <plan-file>
```

**Both run once per invocation, PR-label or not** — never again per task, per PR, or on retry.
`check-pr-dag.sh` passes trivially on a plan with no PR Breakdown, or with the literal "Single PR." escape, so there is no mode to branch on.

The plan stays hand-editable, so a later edit can reintroduce a cycle, dangling dependency, or duplicate id — and §5.3's chain-abort and each PR's parent lookup never re-check it.

A non-zero exit stops the run: surface the script's own stderr diagnostic verbatim and fix the plan before re-invoking.

### 1.4. Worktree setup (only when §1.2 answered yes)

Creation and file-symlink mechanics live in [`references/worktree-setup.md`](references/worktree-setup.md). Load when §1.2 answered yes.

When §1.2 answered no, skip this step; the batch-end package omits the merge-back reminder.

### 1.5. Resolve the PR-labels (only when the arg is a PR-label)

Resolve every `PR-N` in the arg to its task-id list now, before §2 seeds anything, so §2 can see the whole run.

Resolution and per-PR branch creation live in [`references/pr-awareness.md`](references/pr-awareness.md). Load it here.

### 1.6. Capture the full-suite baseline (only when §1.2 answered yes)

Commands, ordering rationale, and where the result gets recorded live in [`references/full-suite-baseline.md`](references/full-suite-baseline.md). Load when §1.2 answered yes.

## 2. Seed the whole TaskList upfront, in execution order

Before dispatching anything, create every TaskList entry the run will need, top-to-bottom in the order it executes.
Read top-down, the list *is* the run's timeline.

Within each batch: **tasks first, then that batch's batch-end reminders**, since reminders fire after the last task lands.

On a PR-label list this covers **every** PR, in order: PR-1's tasks → PR-1's reminders → PR-2's tasks → PR-2's reminders, and so on.
The per-PR loop never repeats this step — showing the whole run upfront is the point.

### 2.1. One entry per task

Create one entry for **every** task-id the run resolved — never just the first.

Mark the run's first task `in_progress` and every other one `pending`.

On a PR-label run, prefix each subject with its owning label: `PR-2 · 5. <task title>` — the PR stays visible in the list, not hidden in metadata.

The TaskList carries **status only**; attempt counts, gate outcomes, and fix SHAs live in the JSON state file (§2.3).

### 2.2. One reminder per batch-end step (they survive compaction)

After a batch's task entries, seed its batch-end steps as **separate** `[Reminder]` entries, per CLAUDE.md's category.

One reminder per step, never one chain covering all of them — a single `completed` flag per task would hide a step-level skip or failure.

Seed exactly these four, in this order, prefixed with the owning `PR-N ·` on a PR-label run:

```
[Reminder] Batch-end 1/4: quality-gate tail with --auto-solve (§8.1, only when opted in)
[Reminder] Batch-end 2/4: repo-green gate — full suite + full lint, fix-loop until green (§8.2, only when opted in)
[Reminder] Batch-end 3/4: push the branch; record it on the PR line; open the PR via the pr-creator agent when pr.wanted (§8.3)
[Reminder] Batch-end 4/4: package print, closing review notification (§8.3, success path only)
```

All four run strictly in this order, each waiting for the previous to finish.

Flip each to `in_progress` when its step starts and `completed` when it lands; a step the interview turned off (quality-gate tail, repo-green gate, PR) completes with a one-line skipped-by-request note.
The push inside 3/4 has no toggle — it runs on every batch end, so that reminder never completes as skipped.

Keep the subjects free of run-specific values like `BATCH_BASE_SHA` — a subject needing them could not be seeded upfront.

### 2.3. Write the state files and the scratchpad — now, then keep them current

Create the run's durable state **immediately after §2.2's reminders land** — before the first unit starts, never at the end.

Two artifacts, both written here and updated as the run goes:

- **One JSON state file per unit** — the machine-checkable record the scripts and the hooks read.
  - `/tmp/implement_<session_id>.json` on a plain `<task-ids>` run.
  - `/tmp/implement_<session_id>_pr<n>.json` per PR on a PR-label run (`_pr1`, `_pr2`, …) — one per label in the arg, **all created now**, never lazily.

- **One markdown scratchpad** — `/tmp/implement_<session_id>.md`, the narrative surface the JSON has no shape for, per CLAUDE.md's scratchpad conventions: blocked-task notes (§5.5) and `[Scout]` entries.

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
  "tasks": [{ "id": "1", "status": "pending", "commits": [] }],
  "attempts": [],
  "gate_dispatches": 0,
  "baseline": { "wanted": false, "log_path": "", "failures": [] },
  "repo_green_gate": { "wanted": true },
  "quality_gate": { "wanted": true, "reports": [] },
  "worktree": { "created": false, "path": "", "branch": "" },
  "pr": { "wanted": false }
}
```

- `start_sha` is `git rev-parse HEAD` taken **before any branch or dispatch**, identical in every unit's file — the run's anchor.

- `batch_base_sha` stays `""` until that unit starts (§3.2) — a dependent PR branches off its parent, so its base does not exist yet.
- One `tasks[]` entry per task-id that unit resolved, each `status: "pending"`; `worktree` / `pr` / `quality_gate.wanted` / `repo_green_gate.wanted` come from §1.2's answers.
- §5.4 appends each accepted task's reported commit SHAs to its `commits` — `Mode: native` batch ends cut task-layer boundaries from them (`references/batch-end-pr.md`).
- `pr_label` is `""` on a plain run, else the `PR-N` that file belongs to.
- §5.2/§5.4 append `attempts[]` entries as `{ "task", "n", "result", "signature", "at" }`.
- `baseline.log_path` and `baseline.failures` are populated by §1.6, empty when `baseline.wanted` is `false`.

**Update both artifacts as they go** — every flip, attempt, verdict, report path, and block, the moment it happens.
The hooks and the verdict script read them, and a compaction or kill keeps only what's on disk.

**There is no resume path.** A leftover state file is stale and never adopted: delete it and start over — re-deriving half-finished state costs more than re-running it.

## 3. Start a unit (once per PR, or once for a `<task-ids>` run)

§3 is the per-unit entry: run it once before that unit's first dispatch, never again mid-loop.

### 3.1. Check out this unit's branch — once, here, by the orchestrator

**Only the orchestrator ever creates or switches a branch, and only here** — no task subagent ever checks anything out.
Every task in the unit commits on the branch this step leaves checked out.
Deciding once keeps a unit's commit range on one branch; a mid-loop checkout would split it across two.

On a plain `<task-ids>` run there is nothing to do: the run stays on the current branch.

On a PR-label run, ask once, then act:

```bash
~/.claude/skills/implement/scripts/need-git-checkout.sh <plan-file> <PR-N>
```

`no` → dispatch this PR's tasks on the current branch. `yes` → create this PR's branch now, per [`references/pr-branch-creation.md`](references/pr-branch-creation.md).

### 3.2. Capture `BATCH_BASE_SHA`, then recap what it sits on

Capture HEAD as `BATCH_BASE_SHA` **after** §3.1's checkout — the branch decides what this batch is measured against.
Write it into this unit's state file as `batch_base_sha`; §5 and §8 both read it back from there rather than recomputing it.

Then recap the work this unit builds on, in 3–5 lines, from `git log <base-branch>..HEAD`.

**Read the commit messages, not the diff** — bodies carry the *why* a diff can't show.
Open the diff only when a message alone can't tell you what it did.

Don't dump the log into chat; each task subagent re-derives its own context from `git log` at dispatch.

### 3.3. Match this unit's task-ids

Exact-match each task-id against the numeric prefixes of the plan's task headings.

A prefix matching more than one heading means the plan changed underneath the run — §1.3's `check-tasks-dag.sh` already rejected duplicate ids.
Stop and say so; never guess which heading was meant.

### 3.4. Activate a task

Per task, as it becomes the active one — the only orchestrator work between two dispatches:

- `TaskUpdate` that task to `in_progress`. Task-level status only; sub-steps never become TaskList items.
- Give it a **breadcrumb** — a coarse outline of its sub-steps (e.g. the plan's acceptance-criteria titles), so the list conveys the task's gist without RED-GREEN detail.

**The checklist file is the subagent's, end to end — the orchestrator neither names it, writes it, nor reads it back.**
The subagent derives its own path, writes it before touching code.
- One item per RED-GREEN cycle, flipped done as each lands, plus an evidence section.
- Resumes from it on a re-dispatch.

Those mechanics live in `~/.claude/agents/tdd-coder.md`; edit that file and this section together.

### 3.5. Mid-flight sub-steps

When a helper or drift surfaces mid-task, the subagent inserts new RED-GREEN lines into its checklist after the current step, then reports the deviation (§4.4).
The orchestrator's TaskList never changes except the parent task's status.

Insertion mechanics live in [`references/mid-flight-substeps.md`](references/mid-flight-substeps.md). Load on demand.

## 4. Dispatch the task subagent

Spawn one fresh-context `agent(subAgent=tdd-coder, title=Implement task <N>: <task subject>)` per task, in the background (the default).

Model is omitted: the agent file pins sonnet and the subagent-model-guard hook enforces it.

Cap the dispatch with a 1-hour `Monitor` timeout (`timeout_ms: 3600000` — the tool's documented maximum).
On expiry, call `TaskStop` on the subagent — the dispatch then resolves as a `timeout`, which §5.2 records and obeys exactly like a `fail`.

The subagent runs the full per-task lifecycle. Its invariant discipline — TDD rules, preloaded standards, checklist mechanics, routing channels, report shape — lives in `~/.claude/agents/tdd-coder.md`.
The prompt pushes only the per-task data below.

### 4.1. Context contract

**Push** — embed verbatim in the prompt (the per-task data only the orchestrator holds):

- The task's plan slice: heading, brief, acceptance criteria, planned-test titles, and its **task-scoped verification commands only**.
  - Strip any repo-wide/full-suite command (e.g. a full `test:agentic` run, a repo-wide `yarn lint`) before pushing.
  - A task subagent verifies only its own change, never the whole repo.
  - A stripped requirement isn't dropped silently: §8.2's gate re-covers it when on; when off, the batch-end package (§8.3) names what full-suite checks never ran.

- The task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.
- `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.

Everything invariant is baked into `tdd-coder.md` — checklist path and write/resume mechanics, preloaded standards, commit rule, report shape.
So are its pull-from-CWD items: plan, spec when one exists, `git log`, source reads. Do not re-push any of it.

### 4.2. Mid-execution design forks — the subagent never spawns a reviewer

`tdd-coder.md` owns how it resolves a fork the plan didn't pre-decide; only the outcome reaches you (§4.4).
A **soft** fork arrives as a Deviation; a rare **hard** one arrives as `blocked`.

The second opinion isn't lost, just deferred: §8.1's quality-gate tail reads the whole batch diff against the plan, and the spec when one exists.

### 4.3. Routing mid-execution discoveries

Anything uncovered outside the task's core work routes through one of three channels, defined in `tdd-coder.md`:
**Drift** (fix in place), **abstract-in-place** (dissolve it into the code), **Scout** (leave it untouched and return it).

There is no separate carry-forward digest: a Drift fix travels in its commit body, which the next subagent reads via `git log`.

**Only Scouts need you.** Record each returned one as a `[Scout]` note on the plan's task breakdown.

### 4.4. Report back

The subagent returns a structured report (text), never a silent "done" (shape mirrored in `~/.claude/agents/tdd-coder.md` — edit both together):

- **Status**: `done` / `blocked`.
- **Commits**: the SHAs it created, with subjects.
- **Self-verification**: the verification command it ran and its result; the planned-test titles it added.
- **Deviations**: sub-steps it inserted into its checklist mid-flight, soft design-forks resolved (with the choice), Drift fixes folded in.
- **For the orchestrator to record**: `[Scout]` items to note on the plan; any block, with exactly what's needed to clear it.

## 5. Accept, retry & advance (orchestrator)

No human gate, and no per-task review — the loop advances on the subagent's own report; the batch's review happens once at the end, over the whole diff (§8.1).

### 5.1. Accept the result — the reported commits exist

**The orchestrator does not verify the work itself, re-runs nothing, reads no checklist, and dispatches no reviewer.**

Its one check: every SHA the subagent reported under **Commits** (§4.4) resolves to a real commit in this repo.

```bash
git cat-file -e <sha>^{commit}
```

Run it once per reported SHA; exit 0 on all of them is the pass.

**Check that they exist, never what they contain** — no diff read, no message read, no count against the plan's commit sketch.
It catches only a report naming commits that were never made; content is §8.1's job.

- **`done`, every reported SHA resolves** → record the attempt as `result: "pass"`, `signature: "n/a"`, and go to §5.4.
- **`done`, any reported SHA missing** → §5.2, same as any other failure.
- **`done` with no commits reported at all** → §5.2 as well; a task that changed nothing had nothing to report done.

A `blocked` report (§4.4) or a §4 timeout skips the check entirely and goes straight to §5.2.

Either way the outcome becomes one recorded attempt and one script verdict — §5.2 on failure/block, §5.4 on pass. No path skips the script.

### 5.2. On failure or a block — record the attempt, obey the verdict

Entry: a reported commit that doesn't resolve (§5.1), a §4 timeout, or a self-reported `blocked` (§4.4) — all three take the same path.

Recording the attempt, running `implement-loop-state.sh`, and obeying its `retry` / `stuck` / `halt-budget` verdict live in [`references/failure-and-halt.md`](references/failure-and-halt.md).
That file also covers verdict semantics, attempt-recording fields, and the `debug-standards` load. Load only on a failure or a block.

### 5.3. On `stuck` — mark terminal, chain-abort dependents, advance

Entry: `implement-loop-state.sh` verdicted `stuck` (§5.2).

Marking the task terminal, chain-aborting its dependents transitively, flipping the plan to `[Blocked]`, and picking (or failing to pick) the next task all live in [`references/failure-and-halt.md`](references/failure-and-halt.md).
Load only on a `stuck` verdict.

### 5.4. On an accepted `done` — advance

Record the attempt with `result: "pass"`, and append the subagent's reported commit SHAs to that task's `commits` in the state file.

Flip that task to `status: "done"` and `reason: "done"` in the state file — before calling the verdict script, not after.
The script picks the next task by `status`, so a passed task left `pending` gets re-selected and re-dispatched later.

Also flip the plan to `[Done]` (§6), record the subagent's `[Scout]` notes there, and `TaskUpdate` its TaskList status to `completed`.

Run `~/.claude/skills/implement/scripts/implement-loop-state.sh <state-file>` and obey the verdict:

- **`next-task`** → its `task` field names the next task-id; re-run §3.4 on it. §1, §2, and §3.1–§3.3 do not repeat.
- **`gates`** → **every** task in this unit is `done`. Set `phase: "gates"` and go to §8's batch end.
- **`halted`** → every task is terminal but at least one ended blocked or stuck. Go to §5.5.
- **`halt-budget`** → the unit's dispatch budget is exhausted. Go to §5.5.

**Only this script sends a unit to the gates, and only when nothing is blocked.**
Never infer `gates` yourself from "the queue looks empty" — a queue empties for two different reasons; only the script can tell them apart.

### 5.5. Halt — stop where you stand and wait for the human

The single exit every dead end in the run routes to.
The full entry list, state-file phase, scratchpad notes, which remaining steps stay unrun, and the release condition all live in [`references/failure-and-halt.md`](references/failure-and-halt.md).
Load it on any dead end.

## 6. Status markers (plan task title)

The orchestrator owns the plan's status edits (`[Doing]` / `[Done]` / `[Blocked]` / `[Deferred]` / `[Dropped]`); the subagent never touches them.

Status is a file edit only, never committed (the plan is session-scoped per `spec-driven-development`).

Status sits **right after the number, before any pre-existing tag** (e.g., Jira IDs): `### N. [<status>] Title (...)`, status omitted entirely in the initial state.
A pre-existing tag stacks after it: `### N. [Doing][JIRA-123] Title (...)`.

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks with it.

### Semantics

- `[Doing]` — actively in progress this session (dispatched, not yet verified-done).
- `[Done]` — finished, verified by the orchestrator, committed by the subagent.
- `[Blocked]` — external dependency unresolvable in this session (e.g., upstream API down, missing access). Pair with a `**QUESTION:**` marker that names what's needed to unblock.

- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT leave partial code committed under a misleading status — either the subagent's commits stand as coherent work, or the WIP is reverted first.

### PR-level status markers (PR Breakdown line, PR-label runs only)

A PR-label run's own PR Breakdown line gets the same `[<status>]` prefix at its own §8.3.
Only `[Done]` in practice, inline, never scripted. Format/timing: `references/batch-end-pr.md`'s "Branch record & PR-level status marker".

## 7. Commit model

The **subagent** produces the commits: a task lands **at least 1 commit**, never zero.
RED + GREEN cycles share the base (tests + impl together), and a refactor lands as its own commit, never folded into the base.

Scouts are never committed by the subagent — they route to the orchestrator per §4.3.

Never auto-invoke `/refactor`, `/auto-review`, `/test-sdd`, or `/quality-gate` **mid-task** — those belong to the user, or to §8.1's batch-end quality-gate tail.

## 8. Batch end — quality gate, repo-green gate, push, PR & package

**Entry: `phase` is `gates`**, set only by §5.4's `gates` verdict, and only when every task in this unit is `done`.

Run the batch-end flow over `<BATCH_BASE_SHA>..HEAD`, then present the whole batch for your async review.

**Stage order: §8.1 → §8.2 → §8.3**, strictly serial, each waiting for the previous to land:

- **§8.1 — the quality-gate tail.** One `/quality-gate --auto-solve` run, scoped to this unit's task-ids. Skipped when §1.2's quality-gate toggle said no.

- **§8.2 — repo-green gate.** Full lint + full test suite, repo-wide, fixed in a loop until green. Skipped entirely when §1.2's gate toggle said no.

- **§8.3 — push, branch record, PR, package & finalize.** The push is unconditional; only the PR is opt-in.

§8.2 runs after §8.1 so the repo-green gate is the batch's last word: it measures a tree that already holds whatever `--auto-solve` applied.

§8.3 runs last so the PR description is composed once against the batch's final diff, never as a pre-fix draft.

`/quality-gate` carries this run's **only** planned-test check, through its `test-sdd` leg, and that leg reads the batch's final state.
A per-task check would verify each task at its own commit point and miss what a later task did to those tests.

Every dispatch contract, failure-handling rule, package content, and the Finalize step order live in [`references/batch-end-review.md`](references/batch-end-review.md).
It covers §5.5 halts on a red repo, a failed push, or a failed PR dispatch, and routes to `batch-end-pr.md` for the PR.
**Load on entry, read late** — by batch end, compaction has usually dropped whatever you read earlier.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
