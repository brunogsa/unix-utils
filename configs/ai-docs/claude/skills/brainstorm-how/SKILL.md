---
name: brainstorm-how
description: "Interview the user on the how (architecture, approach, alternatives, risks) for a settled problem, before a plan. USE on 'brainstorm how', 'brainstorm the HOW', 'how should we fix/build this'. Then offer to-plan. Not for why/what, code, review."
disable-model-invocation: false
---

# Brainstorm How

Interview the user on the solution space: architecture, approach, and risk. Hand the settled result to `to-plan`.

This skill interviews and writes no document: no `plan_<slug>.md`, and no writer, editor or reviewer agent is dispatched.

It plans and does not build: nothing in the working tree changes.

Why the why/what is out of scope: problem framing belongs to `brainstorm-why`, and this skill starts from a problem that is already settled, so re-asking it reopens what is already settled.

Why a spec is optional: a small change can have its why/what settled by an investigation doc, a ticket or a thread, and forcing the full `brainstorm-why` then `to-spec` pipeline on it is overkill.

A spec is useful when it exists, but never a precondition.

## Usage

`/brainstorm-how` — no arguments. A run starts from a settled problem, never from a raw request.

An approved `spec_<slug>.md` in CWD is the best seed but is optional.

Resolve it before step 1:

- **Exactly one `spec_*.md`** → use it, printing the resolved path.
- **Several** → list them numbered and ask which one via `AskUserQuestion`.
- **None** → proceed without one, seeding from the settled problem as found in the conversation and any artifacts the user points at (investigation docs, tickets, threads).
  - If the why/what is genuinely still open, say so and suggest `brainstorm-why` instead of interviewing on it.

## Process

Seed the TaskList per CLAUDE.md's `[Reminder]` category with one entry per step below. Seeding is scaffolding only, never a go-ahead to run a step early.

### 1. Run the interview

This skill wraps no module: it offers no choice at pre-flight, runs no `get-enabled-modules.py`, and nests no `Skill()` call.

It never offers `sdd-grill-tech`, even on a machine where the Arco plugin is present.

Why: `sdd-grill-tech` hard-requires an Arco-pipeline `domains/**/<initiative>/prd.md` with `status != draft`, which this design never produces, so a `spec_<slug>.md` in CWD can never satisfy it.

Read [`../brainstorm-why/references/interview-engine.md`](../brainstorm-why/references/interview-engine.md) and run it, never restating its discipline here. The engine lives under `brainstorm-why/` so that one directory owns it.

- Seed: the approved spec when one exists, otherwise the settled-problem sources (conversation and user-pointed investigation docs, tickets, threads), plus your own codebase read of where the change lands.
- Notes: `<scratchpad>/notes.md` throughout, in the scratchpad directory named in this session's system prompt.
- Brief: `<scratchpad>/brainstorm-how-brief.md`, composed once when the engine's close criterion is met.

Ask only how questions: architecture, approach and alternatives, risks and their mitigations, and failure modes. Ground every question in the user's own conventions, read from their `CLAUDE.md`, skills and code, and never import outside ones.

Why the brief matters: `to-plan` hands it to `plan-writer`, so it is a real downstream input and never a byproduct.

### 2. Offer `to-plan`

Ask via `AskUserQuestion`, recommended answer first: write the plan with `to-plan`, or something else. Keep a free-text "something else" option always open.

Do not run `to-plan` until the user picks it.

Why no `/clear` hand-off: `to-plan` grounds from this session's context, `notes.md` and the brief, so clearing first destroys what it reads.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
