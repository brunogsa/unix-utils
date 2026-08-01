---
name: task-breakdown
description: "Order and split work before executing it: unblockers and riskiest-with-PoC first, thin contract tasks that fan work out in parallel, feature slices split into commit-sized sub-steps. USE when breaking work into tasks/subtasks, prioritizing or sequencing a backlog, planning parallel work, or authoring a plan's Task Breakdown or PR Breakdown."
disable-model-invocation: false
---

# Task Breakdown

How to order and split a body of work into tasks, sub-steps, and PRs.

A breakdown is not bookkeeping — it is the main lever on three outcomes at once:

- **Quality** — a small, self-contained task runs in a small, fresh context, dodging the context rot that degrades long single-context runs.
- **Speed** — a wide dependency graph lets independent tasks run in parallel; a chain forces everything to wait.
- **Cost** — settling the parts that are cheap to write but expensive to be wrong (contracts, risky assumptions) first is what prevents rework, the most expensive waste.

Consumers inside `spec-driven-development` flows read this file by path — `Read ~/.claude/skills/task-breakdown/SKILL.md`; everywhere else it triggers off its description.

## Ordering — what runs first

Sequence tasks in this priority order, not in the order the feature narrates itself:

1. **Unblockers first** — the task whose completion unlocks the most other tasks runs earliest.
   Rank by how many tasks each one unblocks, directly and transitively.
   Why: every day an unblocker waits, everything behind it waits too — its delay is multiplied by its dependents.

2. **Extract thin contract tasks deliberately** — carve out a small task that pins the shared contract, even when no narrated feature step asks for it.
   Examples: an OpenAPI definition, an interface/type file, a DB schema or migration, an event payload shape, a stub endpoint returning fixtures.
   Why: a contract is cheap to write and expensive to be wrong; agreeing on it first lets N workers build against it in parallel instead of reworking each other.

3. **Riskiest next, proven by a proof of concept** — give the riskiest assumption its own early spike task that proves or kills it before dependent work stacks on top.
   Signals of risk: an unproven integration, an unfamiliar library, a performance bet, a design the team argued about.
   Why: rework cost grows with everything built on the assumption — fail while the pivot is cheap, not after five tasks embed it.

4. **Everything else in dependency order** — feature slices, polish, and docs follow, each behind whatever it builds on.

## Shape the graph wide, not deep

- **Minimize the critical path** — prefer many tasks depending on one thin unblocker over a chain where each task waits for the previous.

- **Keep independent tasks on disjoint files/modules** — two tasks editing the same file are sequential in disguise; re-cut the boundary so parallel workers never collide.

- **A task must stand alone** — executable by a fresh-context agent from its brief, acceptance criteria, and file list, without the session that wrote the plan.
  Why: the breakdown only buys its quality and speed wins if a task really can run in a fresh small context; a task needing tribal context drags the whole history back in.

## Sub-steps — splitting a feature slice

A feature slice too big for one commit splits into **sub-steps** (a.k.a. subtasks): the commit-sized moves a human would land one by one to keep feeling progress.

- **Each sub-step is one commit inside its parent task**, in natural build order — e.g. data model/migration; domain logic; component; client/adapter; consumer wire-up; E2E tests.

- **Past ~4 sub-steps, split the task** — a slice that long is two tasks in disguise, and each task must stay independently dispatchable.

- **In a `plan_<slug>.md`**, sub-steps surface as the task title's parenthetical breadcrumb and the task's `Commits (sketch, minimum)` list, per the plan template.
- **On the TaskList**, they are `[Sub-Step]` entries under their parent, per the global CLAUDE.md categories.

## PR ordering follows the same rule

When work splits into multiple PRs, partition and sequence them by the same priorities:

- **The earliest PRs ship the contract tasks and the riskiest proof of concept** — later PRs stack feature slices on an already de-risked, agreed base.

- Why: a wrong contract or dead assumption discovered while reviewing PR-1 costs one small PR; discovered in PR-5 it reworks four merged ones — and reviewer attention is freshest early, exactly where the load-bearing decisions should sit.

## Where this applies

- The Task Breakdown and PR Breakdown sections of a `plan_<slug>.md` — plan authors (`plan-writer`, `brainstorm` forks) apply it via the plan template's pointers.
- Any everyday breakdown at any scale: a TaskList for a multi-step request, a backlog ordering, a "what do we build first" call.
