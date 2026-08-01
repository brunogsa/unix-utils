---
name: task-breakdown
description: "Break a body of work into a prioritized, dependency-aware task breakdown — unblockers and riskiest-with-PoC first, thin contract tasks that fan work out in parallel, feature slices split into commit-sized sub-steps — emitted as a .md artifact in /tmp for the caller to consume. USE when breaking work into tasks/subtasks, prioritizing or sequencing a backlog, or planning parallel work."
disable-model-invocation: false
---

# Task Breakdown

Break a body of work into ordered, dependency-aware tasks, and emit the result as one standalone `.md` artifact.

This skill is pure: it takes the work to break down — from the conversation, a document, or whatever the caller supplies — applies the rules below, and writes the artifact.
It knows nothing about who consumes that artifact or what surface it feeds; the caller decides.

Why an artifact instead of in-context advice: a file survives compaction, hands to any consumer unchanged, and keeps this skill reusable from any flow without coupling to any.

A breakdown is not bookkeeping — it is the main lever on three outcomes at once:

- **Quality** — a small, self-contained task runs in a small, fresh context, dodging the context rot that degrades long single-context runs.
- **Speed** — a wide dependency graph lets independent tasks run in parallel; a chain forces everything to wait.
- **Cost** — settling the parts that are cheap to write but expensive to be wrong (contracts, risky assumptions) first is what prevents rework, the most expensive waste.

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

- **A task must stand alone** — executable by a fresh-context agent from its brief, acceptance criteria, and file list, without the session that produced the breakdown.
  Why: the breakdown only buys its quality and speed wins if a task really can run in a fresh small context; a task needing tribal context drags the whole history back in.

## Sub-steps — splitting a feature slice

A feature slice too big for one commit splits into **sub-steps** (a.k.a. subtasks): the commit-sized moves a human would land one by one to keep feeling progress.

- **Each sub-step is one commit inside its parent task**, in natural build order — e.g. data model/migration; domain logic; component; client/adapter; consumer wire-up; E2E tests.

- **Past ~4 sub-steps, split the task** — a slice that long is two tasks in disguise, and each task must stay independently dispatchable.

## Output artifact

Write the breakdown to `/tmp/task-breakdown_<slug>.md` — derive a short kebab-case `<slug>` from the work — unless the caller names an output path. Report the resolved path back.

ALWAYS use this exact template, one `###` entry per task, numbered in execution order (position 1 runs first):

```markdown
# Task Breakdown: <title>

### 1. <task title>

- **Depends on**: none | task <N>, ...
- **Unlocks**: none | task <N>, ...
- **Priority rationale**: <unblocker | thin contract | risk PoC | dependency order> — <one line of why>
- **Sub-steps (one commit each)**: none — single-commit task | <sub-step>; <sub-step>; ...
- **Parallelizable with**: none | task <N>, ... (disjoint files, no shared dependency pending)
```
