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

Each ID must match the exact numeric prefix of one plan heading; colliding ids make the plan malformed, and §1.3's checker rejects it.

`<PR-label(s)>` is `PR-N` or a comma-list, same convention — `PR-1`, or `PR-1, PR-2` — from the plan's PR Breakdown, resolving to its own task-id list.

See [`references/pr-awareness.md`](references/pr-awareness.md), loaded whenever the arg is a PR-label.

## Execution model — orchestrator + per-task subagents

`/implement` is **fully async**: it runs the whole batch and hands you the finished commits — the only handshake is the batch-end review. Two roles:

- **Orchestrator** (this session) — pre-flight, TaskList, dispatch, post-commit verification, batch-end report. Holds only orchestration state, never task context, and is the **only** role that spawns subagents; a subagent never nests another.

- **Task subagent** — one fresh context per task: decompose into its own checklist file, RED-GREEN work, self-verify, commit, report.
  - Re-grounds from durable artifacts (the plan, spec when one exists, `git log`), not session history.

Run subagents on **Sonnet** (mechanical); keep orchestrator on stronger model.

§5.4 picks each next dispatch: tasks with satisfied dependencies and no shared files go out **in parallel**, every other one sequentially.

### Two delivery shapes, chosen at §1.2 — never by the plan

A **unit** is one `PR-N` entry, or the whole `<task-ids>` run when the plan has no PR Breakdown.

**Not stacked** (the default) makes the unit one PR whose tasks are commits inside it; **stacked** is opt-in and makes each task its own PR, layered into one stack.

Stacked is opt-in because it turns the whole unit strictly sequential — every layer branches off the previous layer's tip, so §5.4's parallel dispatch is off for the run.

The plan reads the same either way — [`references/stacked-by-task.md`](references/stacked-by-task.md) owns the choice and everything it changes.

### A PR-label run is the same batch flow, repeated once per PR

`/implement PR-1, PR-2` resolves each label to its own task-id list, then runs **§3 through §8** once per PR, strictly in order.

§1 and §2 never repeat per PR — they run once, shared by the whole list.

Per-PR iteration order, the fail-fast stop predicate, label resolution, branch creation and recording, and each PR's gate/quality-gate/diff scoping live in [`references/pr-awareness.md`](references/pr-awareness.md). Load it only on a PR-label run.

### Chain-abort, with no human gate

- **Blocked on something only the human can resolve** (missing access, upstream API down, open decision): record it, never guess past it.
  - Keep running the tasks that don't depend on it until nothing runnable is left (§5.5).

- **Work that fails verification** → re-dispatch the same task with the failure as feedback; the verdict script decides the attempt count (§5.2), surfaced only if it still fails.

## 1. Pre-flight (orchestrator)

This skill **never merges or deletes §1.2's worktree**; `parallel-worktrees` carves the same exception for it.

**§1.1–§1.6 and §2 run once per invocation**, in that order, before execution; §3 starts each unit.

### 1.1. Locate the plan (and spec)

Glob in CWD (top-level only):

```bash
ls -1 plan_*.md spec_*.md 2>/dev/null
```

Resolve candidates with this decision tree — it never prompts; ambiguity becomes the interview's plan-pick question (§1.2):

- **Exactly one plan and one spec** → use both; print the resolved paths.
- **Multiple plans (or multiple specs)** → the plan-pick question lists the matches numbered; pair each plan with the spec sharing its `<slug>`.
- **No plan found** → the interview asks for the path; if none provided, **stop**.
- **Plan but no spec** → proceed plan-only, spec is optional context.

Everywhere below, plan and spec refer to these resolved paths.

### 1.2. One up-front interview

Ask everything at once, before any dispatch — the only round of questions in the whole run (it takes two or three `AskUserQuestion` calls; each caps at 4 questions and 4 options).

Mid-run `.env` needs are self-served (copied from the original checkout) rather than asked.

- **Plan pick**, only when §1.1 found multiple candidates.
- **Plan path**, only when §1.1 found no plan — if still not provided, stop (§1.1).
- **Run in a git worktree?** (yes/no) — on yes, §1.4 creates it from HEAD and symlinks files in.
- **Open a draft PR at batch end?** (yes/no) — decides the PR only; §8.1 pushes the branch either way.
- **Deliver each task as its own stacked PR?** (yes/no, default no) — opt-in, because a stacked unit gives up §5.4's parallel dispatch for the whole run.
  - On `yes` only, load [`references/stacked-by-task.md`](references/stacked-by-task.md): it owns two gates that can overrule the yes, the layer order, and every mechanic that branch changes.

  - Both run in a **follow-up** `AskUserQuestion` call, still before any dispatch; a `no` loads nothing and changes nothing downstream.

- **Run the quality-gate batch-end tail?** (yes/no, default yes) — decides whether §8.2 runs `/quality-gate` at all, always `--report-only`.
  - The human applies its refactor and auto-review verdicts manually afterward, via `/address-verdicts` — never this run.

- **Run the repo-green gate at batch end?** (yes/no, default yes, independent of the quality-gate toggle, decided fresh each run).
  - On yes, runs BOTH §1.6's full-suite baseline capture and §8.3's batch-end gate; on no, runs NEITHER.
  - The gate can only classify pre-existing red by diffing against a baseline, so a gate without one can never terminate.

- **Base-branch confirmation** — show `~/.claude/scripts/resolve-base-ref.sh`'s output (origin/HEAD, falling back to local main, then local master) as the default; let the user confirm or override.

Record all answers before proceeding — §2.3 persists them to the state file.

### 1.3. Re-validate all three dependency checks — once, before any execution

Run all three checkers on the resolved plan, before §2 seeds anything and before the first dispatch:

```bash
~/.claude/skills/spec-driven-development/scripts/check-tasks-dag.sh <plan-file>
~/.claude/skills/spec-driven-development/scripts/check-pr-dag.sh <plan-file>
~/.claude/skills/spec-driven-development/scripts/check-pr-task-projection.py <plan-file>
```

The first two validate one graph each in isolation — the Task Breakdown's, and the PR Breakdown's.

A plan can pass both and still be wrong: a task in an early PR can depend on one in a later PR never listed as a dependency.

§2.3's "absent id counts as satisfied" rule then dispatches it before the real prerequisite runs — which is what the third check, `check-pr-task-projection.py`, exists to catch.

It validates the task graph's PROJECTION onto the PR partition, the composition the first two never cross-check.

**All three run once per invocation, PR-label or not** — never again per task, per PR, or on retry.

The last two pass trivially with no PR Breakdown, or with the literal "Single PR." escape, so there's no mode to branch on.

The plan stays hand-editable, so a later edit can reintroduce a cycle, dangling dependency, or duplicate id — and nothing downstream re-checks it.

A non-zero exit stops the run: surface the script's own stderr diagnostic verbatim and fix the plan before re-invoking.

### 1.4. Worktree setup (only when §1.2 answered yes)

Creation and file-symlink mechanics live in [`references/worktree-setup.md`](references/worktree-setup.md). Load when §1.2 answered yes. When §1.2 answered no, skip this step; the batch-end package omits the merge-back reminder.

### 1.5. Resolve the PR-labels (only when the arg is a PR-label)

Resolve every `PR-N` in the arg to its task-id list now, before §2 seeds anything, so §2 can see the whole run.

Resolution and per-PR branch creation live in [`references/pr-awareness.md`](references/pr-awareness.md). Load it here.

### 1.6. Capture the full-suite baseline (only when §1.2's repo-green gate toggle answered yes)

Commands, ordering, and result handling live in [`references/full-suite-baseline.md`](references/full-suite-baseline.md). Load it here.

## 2. Seed the whole TaskList upfront, in execution order

Before dispatching anything, create every TaskList entry the run will need, top-to-bottom in execution order — the list *is* the run's timeline.

Within each batch: **tasks first, then that batch's batch-end reminders**, since reminders fire after the last task lands.

On a PR-label list this covers **every** PR, in order: PR-1's tasks → PR-1's reminders → PR-2's tasks → PR-2's reminders, and so on.

The per-PR loop never repeats this step — showing the whole run upfront is the point.

### 2.1. One entry per task

Create one entry for **every** task-id the run resolved — never just the first. Mark the run's first task `in_progress` and every other one `pending`.

On a PR-label run, prefix each subject with its owning label: `PR-2 · 5. <task title>` — the PR stays visible in the list, not hidden in metadata.

The TaskList carries **status only** — attempt counts, gate outcomes, and fix SHAs live in the JSON state file (§2.3).

CLAUDE.md's `metadata` rule yields here: the verdict script and Stop hook are shell processes blind to it.

### 2.2. One reminder per batch-end step this run will perform (they survive compaction)

After a batch's task entries, seed a **separate** `[Reminder]` entry per CLAUDE.md's category for each batch-end step this run will actually perform.

Never one shared chain, since one `completed` flag per task would hide step-level skips and failures.

**A step the interview toggled off gets no entry at all** — not seeded, not seeded-then-skipped. Four steps exist; the first and last always run, the middle two are conditional:

```
push the branch; record it in the PR entry; open the draft PR via the pr-creator agent when pr.wanted (§8.1) — always seed
quality-gate tail, always report-only (§8.2) — seed only when quality_gate.wanted
repo-green gate — full suite + full lint, fix-loop until green (§8.3) — seed only when repo_green_gate.wanted
re-push and refresh the PR description when the gates landed commits; package print, closing review notification (§8.4, success path only) — always seed
```

Number the entries actually seeded as `Batch-end <i>/<N>` in the fixed order above.

`N` is however many of the four apply this run (2, 3, or 4); `i` is that step's position among the seeded ones.

A run with both gates off seeds exactly two: `Batch-end 1/2` (push and PR) and `Batch-end 2/2` (package) — the two that always run, now first and last.

Prefix each with the owning `PR-N ·` on a PR-label run.

Flip each to `in_progress` when its step starts and `completed` when it lands. The push step has no toggle, so that reminder never completes as skipped.

A toggled-off step's skip is recorded only in the batch-end package (§8.4), never as a TaskList entry.

Keep the subjects free of run-specific values like `BATCH_BASE_SHA` — a subject needing them could not be seeded upfront.

### 2.3. Write the state files and notes.md — now, then keep them current

Create the run's durable state **immediately after §2.2's reminders land**, never at the end. Two artifacts, created here:

- **One JSON state file per unit** — the machine-checkable record the scripts and hooks read.
  - `/tmp/implement_<session_id>.json` on a plain `<task-ids>` run.
  - `/tmp/implement_<session_id>_pr<n>.json` per PR on a PR-label run (`_pr1`, `_pr2`, …) — one per label in the arg, **all created now**, never lazily.

- **`<scratchpad>/notes.md`**, in the scratchpad directory this session's system prompt names, per CLAUDE.md's Note-taking discipline — never an invented `/tmp` path. Holds what the JSON cannot: blocked-task notes (§5.5).

Each state file has exactly this shape:

```json
{
  "version": 4,
  "session_id": "<session_id>",
  "slug": "<slug>",
  "pr_label": "",
  "phase": "tasks",
  "start_sha": "<HEAD before this run touched anything>",
  "batch_base_sha": "",
  "tasks": [{ "id": "1", "status": "pending", "depends_on": [], "branch": "", "worktree_path": "" }],
  "attempts": [],
  "gate_dispatches": 0,
  "baseline": { "log_path": "", "failures": [] },
  "repo_green_gate": { "wanted": true },
  "quality_gate": { "wanted": true, "reports": [] },
  "worktree": { "created": false, "path": "", "branch": "" },
  "pr": { "wanted": false },
  "stack": { "wanted": false, "order": [], "refused": "" }
}
```

- `start_sha` is `git rev-parse HEAD` taken **before any branch or dispatch**, identical in every unit's file — the run's anchor.
- `batch_base_sha` stays `""` until that unit starts (§3.2) — a dependent PR branches off its parent, so its base doesn't exist yet.
- One `tasks[]` entry per task-id that unit resolved, each `status: "pending"`, flipped to `"in_progress"` at dispatch.
  - `branch` / `worktree_path` are set only for a per-task worktree; `worktree`, `pr`, `repo_green_gate.wanted`, and `quality_gate.wanted` come from §1.2's answers.

- Populate `depends_on` from the plan's `**Depends on**:` clause that §1.3's `check-tasks-dag.sh` validated, as bare id strings (`["3", "5"]`; `none` → `[]`).
  - `implement-loop-state.py` reads it to pick a DAG-eligible next task; unset, it silently degrades to lowest-id-first, so seed it here, not later.

  - An id absent from this unit's `tasks[]` counts as satisfied: it belongs to an earlier PR that `references/pr-awareness.md`'s stop predicate already required to be `[Done]`.

- `stack.order` is this unit's confirmed layer order (§1.2) and what §3.4 advances through when `stack.wanted` is true, overriding the script's DAG-only ordering.
  - Both keep their seeded values on a default run — §1.2 fills them only after a `yes`.

- `stack.refused` names the gate that forced `wanted: false` against a `yes` answer (`""` when none did), so the batch-end package can say why the run wasn't stacked.

- `pr_label` is `""` on a plain run, else the `PR-N` that file belongs to.
- §5.2/§5.4 append `attempts[]` entries as `{ "task", "n", "result", "signature", "at" }`.
- `baseline.log_path` and `baseline.failures` come from §1.6, empty when `repo_green_gate.wanted` is `false`.

**Update both artifacts as they go** — every flip, attempt, verdict, report path, and block. The hooks and verdict script read them, and a compaction or kill keeps only what's on disk.

**There's no resume path.** A leftover state file is stale: delete it and start over — re-deriving half-finished state costs more than re-running it.

## 3. Start a unit (once per PR, or once for a `<task-ids>` run)

§3 is the per-unit entry: run it once before that unit's first dispatch, never again mid-loop.

### 3.1. Check out this unit's branch — once, here, by the orchestrator

**Only the orchestrator ever creates or switches a branch.**

Every task in the unit commits on the branch this step leaves checked out, keeping all unit commits on one branch without mid-loop checkouts.

On a plain `<task-ids>` run there's nothing to do: the run stays on the current branch.

On a PR-label run, ask once, then act:

```bash
~/.claude/skills/implement/scripts/need-git-checkout.sh <plan-file> <PR-N>
```

`no` → dispatch this PR's tasks on the current branch. `yes` → create this PR's branch now, per [`references/pr-branch-creation.md`](references/pr-branch-creation.md).

### 3.2. Capture `BATCH_BASE_SHA`, then recap what it sits on

Capture HEAD as `BATCH_BASE_SHA` **after** §3.1's checkout — the branch decides what this batch is measured against.

Write it into this unit's state file as `batch_base_sha`; §5 and §8 both read it back from there rather than recomputing it.

Recap the work this unit builds on, in 3–5 lines, from `git log <base-branch>..HEAD`.

**Read the commit messages, not the diff** — bodies carry the *why*; open it only when a message can't tell you what it did.

Don't dump the log into chat; each subagent re-derives its own context from `git log` at dispatch.

### 3.3. Match this unit's task-ids

Exact-match each task-id against the numeric prefixes of the plan's task headings.

A prefix matching more than one heading means the plan changed underneath the run — §1.3's `check-tasks-dag.sh` already rejected duplicate ids. Stop and say so; never guess which heading was meant.

### 3.4. Activate a task

Per task, as it becomes the active one — the only orchestrator work between two dispatches:

- `TaskUpdate` that task to `in_progress`. Task-level status only; sub-steps never become TaskList items.
- Give it a **breadcrumb** — a coarse outline of its sub-steps (e.g. the plan's acceptance-criteria titles), so the list conveys the task's gist without RED-GREEN detail.

**The checklist file is the subagent's, end to end.** The orchestrator supplies only the `<run-label>` key that names it — never the file, its contents, or a read-back.

That key becomes the path `/tmp/tdd-coder_substeps_<run-label>.md`, per §4.1.

Its path, contents, and re-dispatch resume live in `~/.claude/agents/tdd-coder.md`; edit that file and this section together.

### 3.5. Mid-flight sub-steps

When a helper or drift surfaces mid-task, the subagent inserts new RED-GREEN lines into its checklist after the current step, then reports the deviation (§4.4).

The orchestrator's TaskList never changes except the parent task's status.

## 4. Dispatch the task subagent

Spawn one fresh-context `agent(subAgent=tdd-coder, title=Implement task <N>: <task subject>)` per task, in the background — only a background dispatch can carry the Monitor cap below.

Model is omitted: the agent file pins sonnet and the subagent-model-guard hook enforces it.

Cap the dispatch with a 1-hour `Monitor` timeout (`timeout_ms: 3600000` — the tool's documented maximum).

On expiry, call `TaskStop` on the subagent — the dispatch resolves as a `timeout`, which §5.2 records and obeys exactly like a `fail`.

The subagent runs the full per-task lifecycle. Its invariant discipline — TDD rules, standards-loading triggers, checklist mechanics, routing channels, report shape — lives in `~/.claude/agents/tdd-coder.md`.

The prompt pushes only the per-task data below.

### 4.1. Context contract

**Push** — embed a `Context`/`Units`/`Verification`/`Optional` block verbatim in the prompt, using the exact field names `tdd-coder.md`'s Inputs section defines; the subagent pulls nothing from CWD to begin.

- **Context**: the task's heading and brief description — what the task does and why, in the plan's own words.
- **Units**: the task's acceptance criteria and planned-test titles, one unit per forcing case, in the plan slice's own order.
  - Cap one dispatch at **3 units**. A task carrying more splits into consecutive dispatches of ≤3 units each, in plan order, each with its own `<run-label>`.

  - A dispatch that auto-compacts ran ~3.7× longer than one that didn't (18.4m vs 5.0m median), and each compaction stalls ~176s and buys nothing.

  - The cap is a proxy, not the mechanism: a single-unit dispatch still auto-compacted, at 168,867 pre-compaction tokens, so a low unit count alone does not prevent it.

  - Dispatch prompt size is a second, independent factor: that single-unit dispatch burned 275s on its first turn before any tool call, then averaged 18.3s/call against 9.1s/call elsewhere.

  - `tdd-coder.md` forbids the subagent from self-splitting, precisely so batch size stays a caller decision; that means this cap does not exist unless you apply it here.

  - Chunks of one task run **sequentially**, never in parallel: they commit to the same branch and would collide on a single git index.
  - Cross-task parallelism stays with `parallel-worktrees` (§5.4), which gives each task its own tree.

  - Give a later chunk's **Context** a one-line summary of what the earlier chunks landed, plus `base:`, so it can `git log` the *why* instead of rediscovering it.

  - A test and the change it covers are **one unit, never two**.

    - `tdd-coder` commits one commit per unit, so splitting a test from its change lands a commit whose test fails standing alone, which commit-standards forbids.

- **Verification**: the task's **task-scoped verification commands only**, when the plan names any.
  - Strip any repo-wide/full-suite command (e.g. a full `test:agentic` run, a repo-wide `yarn lint`) before pushing. A subagent verifies only its own change, never the whole repo.

  - A stripped requirement isn't dropped silently: §8.3's gate re-covers it when on; when off, the batch-end package (§8.4) names what full-suite checks never ran.

  - When the plan names no command for the task, **omit the field** rather than inventing one.

    - `tdd-coder.md` derives it from a file that declares the repo's entry point, and reports both the command and the source file it read it from.

    - An invented command is the one case its derivation can't audit: a caller-supplied command is trusted outright, so a bad guess here reaches the evidence file unchallenged.

  - Read that derived command back off the subagent's report and check it actually covers the task.
    - A wrong one is a plan gap, not a subagent fault — push the correct command on the re-dispatch.

    - Write it into the plan's task slice too, so the next task doesn't re-derive the same wrong thing.

  - Never substitute a full-suite command for a missing task-scoped one.
    - The subagent budgets the full suite at two runs per dispatch, so a stand-in burns that whole budget proving nothing about this task.

- **Optional**:
  - `files:` — the task's **Files (logical order)** list as the **starting set** — not a cage; touch more when needed, routing the delta per §4.3.

  - `references:` — `plan_<slug>.md`, plus `spec_<slug>.md` when one exists.
  - `base:` — `BATCH_BASE_SHA` and the base branch, so the subagent can scope its own `git log`.
  - `worktree:` — named here for completeness, but this contract leaves it unset.
    - A single-worktree run already sits inside that worktree by §1.4, before any dispatch, so the subagent inherits it via CWD.
    - A per-task worktree instead routes through `parallel-worktrees`'s own separate four-input contract (§5.4), never through this one.

  - `<run-label>` — this task's number, so its checklist and evidence files key uniquely among any siblings dispatched concurrently.

Everything invariant is baked into `tdd-coder.md` — checklist mechanics, standards-loading triggers, commit rule, report shape.

Don't re-push any of it.

### 4.2. Mid-execution design forks — the subagent never spawns a reviewer

`tdd-coder.md` owns how it resolves a fork the plan didn't pre-decide; only the outcome reaches you (§4.4) — a **soft** fork as a Deviation, a rare **hard** one as `blocked`.

The second opinion isn't lost, just deferred to §8.2's quality-gate tail, which reads the whole batch diff against the plan and spec.

### 4.3. Routing mid-execution discoveries

Anything outside the task's core work routes through three channels defined in `tdd-coder.md`: **Drift** (fix in place), **abstract-in-place** (dissolve into the code), **Scout** (leave it, return it).

There's no separate carry-forward digest: a Drift fix travels in its commit body, which the next subagent reads via `git log`.

**Only Scouts need you.** `TaskCreate` one `[Scout]` task each, cite that id on the plan — only a task carries a status the human can triage.

### 4.4. Report back

`~/.claude/agents/tdd-coder.md` authors the report's full shape — `Status`, `Commits`, `Units`, `Deviations`, `Scouts`, `Blocked on`, `Evidence`, `Checklist`; restating it here would be a second copy to keep in sync.

Three of its fields drive this section:

- **Commits** — the SHAs §5.1 resolves.
- **Scouts** — the `[Scout]` items you file per §4.3.
- **Blocked on** — present only on a `blocked` `Status`; names what clears it for §5.2.

## 5. Accept, retry & advance (orchestrator)

The loop advances on the subagent's own report; §8.2 reviews the whole diff once, at the end.

### 5.1. Accept the result — the reported commits exist

**The orchestrator does not verify the work itself** — it re-runs nothing, reads no checklist, and dispatches no reviewer.

Its one check: every SHA the subagent reported under **Commits** (§4.4) resolves to a real commit in this repo.

```bash
git cat-file -e <sha>^{commit}
```

Run it once per reported SHA; exit 0 on all of them is the pass — existence only, never content, since content review is §8.2's job.

- **`done`, every reported SHA resolves** → §5.4, which records the attempt.
- **`done`, any SHA missing or none reported at all** → §5.2, like any other failure; a task that changed nothing had nothing to report done.

A `blocked` report (§4.4) or a §4 timeout skips the check and goes straight to §5.2.

Every path ends in one recorded attempt and one script verdict.

### 5.2. On failure or a block — record the attempt, obey the verdict

Entry: a reported commit that doesn't resolve (§5.1), a §4 timeout, or a self-reported `blocked` (§4.4) — all three take the same path.

Recording the attempt, running `implement-loop-state.py`, and obeying its `retry` / `stuck` / `halt-budget` verdict live in [`references/failure-and-halt.md`](references/failure-and-halt.md).

It also covers verdict semantics, attempt-recording fields, and the `debug-standards` load — read it only on a failure or a block.

### 5.3. On `stuck` — mark terminal, chain-abort dependents, advance

Entry: `implement-loop-state.py` verdicted `stuck` (§5.2).

Marking the task terminal, chain-aborting its dependents transitively, flipping the plan to `[Blocked]`, and picking (or failing to pick) next task all live in [`references/failure-and-halt.md`](references/failure-and-halt.md), read only on a `stuck` verdict.

### 5.4. On an accepted `done` — advance

Record the attempt with `result: "pass"`, `signature: "n/a"`.

Flip that task to `status: "done"` and `reason: "done"` in the state file — before calling the verdict script, not after.

The script picks by `status`, so a passed task left `pending` gets re-dispatched later.

Also flip the plan to `[Done]` (§6), file the subagent's `[Scout]` items per §4.3, and `TaskUpdate` its TaskList status to `completed`.

Run `~/.claude/skills/implement/scripts/implement-loop-state.py <state-file>` and obey the verdict:

- **`next-task`** → its `task` field names the next task-id; re-run §3.4 on it. §1, §2, and §3.1–§3.3 don't repeat.
  - **When `stack.wanted` is true, take the next id from `stack.order` instead**, and dispatch that one alone — parallel tasks leave no single tip to stack the next layer on.

  - When `--eligible-set` returns several ids, dispatch them all at once instead: load `parallel-worktrees`.
    - It names its own four inputs; bind its base to this unit branch's HEAD at wave time, never `batch_base_sha` — that one is §8's fixed review anchor.

    - Its ledger is this state file: it writes `in_progress`, `branch`, and `worktree_path` before each spawn — what `--eligible-set` reads to skip an in-flight task.

- **`wait`** → a dispatched sibling hasn't reported yet. Dispatch nothing, take no halt action, and re-run this verdict once its report lands.
- **`gates`** → **every** task in this unit is `done`. Set `phase: "gates"` and go to §8's batch end.
- **`halted`** → every task is terminal with at least one blocked or stuck, or a same-unit dependency deadlock leaves pending tasks with unsatisfied `depends_on`. Go to §5.5.

- **`halt-budget`** → the unit's dispatch budget is exhausted. Go to §5.5.

**Only this script decides `wait`, `halted`, or `gates`** — never infer any of them from "the queue looks empty."

### 5.5. Halt — stop where you stand and wait for the human

The single exit every dead end in the run routes to.

The full entry list, state-file phase, notes.md's blocked-task record, which remaining steps stay unrun, and the release condition all live in [`references/failure-and-halt.md`](references/failure-and-halt.md). Load it on any dead end.

## 6. Status markers (plan task title)

The orchestrator owns the plan's status edits (`[Doing]` / `[Done]` / `[Blocked]` / `[Deferred]` / `[Dropped]`); the subagent never touches them.

Status is a file edit only, never committed (the plan is session-scoped per `spec-driven-development`).

Status sits **right after the number, before any pre-existing tag** (e.g. Jira IDs): `### N. [Doing][JIRA-123] Title (...)`, omitted entirely in the initial state.

Single value, mutually exclusive — `[Blocked]` *replaces* `[Doing]`, never stacks with it.

### Semantics

- `[Doing]` — actively in progress this session (dispatched, not yet verified-done).
- `[Done]` — finished, verified by the orchestrator, committed by the subagent.
- `[Blocked]` — external dependency unresolvable in this session. Pair with a `**QUESTION:**` marker naming what's needed to unblock.
- `[Deferred]` — deliberately postponed to a later session, but still planned.
- `[Dropped]` — decided not to do at all (scope reduction). Pair with `**DECISION (Task N):**` capturing the reason.

In all non-`[Done]` terminal states, do NOT leave partial code committed under a misleading status — either the commits stand as coherent work, or get reverted first.

### PR-level status markers (PR Breakdown heading, PR-label runs only)

A PR-label run's own PR Breakdown heading gets the same `[<status>]` prefix at its own §8.1. Only `[Done]` in practice, inline, never scripted. Format/timing: `references/batch-end-pr-branch-record.md`'s "Branch record & PR-level status marker".

On a stacked run each task heading additionally carries its own layer `**Branch**:` field, written at that same §8.1 — see [`references/stacked-by-task-batch-end.md`](references/stacked-by-task-batch-end.md)'s "Where the branch gets recorded".

## 7. Commit model

The **subagent** produces the commits: a task lands **at least 1 commit**, never zero.

RED + GREEN share one commit (tests + impl together); a refactor lands as its own, per `commit-standards`.

Scouts are never committed by the subagent — they route to the orchestrator per §4.3.

Never auto-invoke `/refactor`, `/auto-review`, `/test-sdd`, or `/quality-gate` **mid-task** — those belong to the user, or to §8.2's batch-end quality-gate tail.

## 8. Batch end — push, PR, quality gate, repo-green gate & package

**Entry: `phase` is `gates`**, set only by §5.4's `gates` verdict, and only when every task in this unit is `done`.

Run the batch-end flow over `<BATCH_BASE_SHA>..HEAD`, then present the whole batch for your async review.

**Stage order: §8.1 → §8.2 → §8.3 → §8.4**, strictly serial, each waiting for the previous to land:

- **§8.1 — push the branch, record it, open the draft PR.** The push is unconditional; only the PR is opt-in.

- **§8.2 — the quality-gate tail.** One `/quality-gate` run scoped to this unit's task-ids, always carrying `--report-only`. Skipped entirely when §1.2's toggle said no.
  - The human applies its verdicts manually afterward, via `/address-verdicts` — never this run.

- **§8.3 — repo-green gate.** Full lint + full test suite, repo-wide, fixed in a loop until green. Skipped entirely when §1.2's gate toggle said no.

- **§8.4 — re-push, refresh the PR description, package & finalize.** Both refreshes are skipped when §8.2 and §8.3 landed no commits.

§8.1 runs first because the PR it opens is a **draft**, and §8.4 refreshes that draft's description against the final diff.

A draft PR that exists beats a description composed once: two audited batches proved the old order strands every commit locally when a gate never terminates.

Both stalled with the repo-green gate `in_progress` and no verdict, leaving 9 and 16 commits unpushed across ~40 hours of the human being away.

A gate that cannot terminate must not be able to strand delivered work, so nothing that can hang sits between a finished batch and its remote.

`/quality-gate`'s `test-sdd` leg carries this run's **only** planned-test check, read against the batch's final state.

A per-task check would verify each task at its own commit point and miss later edits to those tests.

That leg **writes** the tests it finds missing on every run of the tail.

Every dispatch contract, package content, the Finalize step order, and the §5.5 halts on a red repo, a failed push, or a failed PR dispatch live in [`references/batch-end-review.md`](references/batch-end-review.md).

**Load on entry, read late** — by batch end, compaction has usually dropped whatever you read earlier.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
