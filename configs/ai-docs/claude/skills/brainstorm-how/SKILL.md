---
name: brainstorm-how
description: "Interview the user on the technical how (architecture, approach, risk) from an approved spec, then offer to-plan. USE when user says 'brainstorm how' or asks how to build what a spec describes. Writes no docs. Never for why/what, code, bugs, review."
disable-model-invocation: false
---

# Brainstorm How

Interview the user on the solution space: architecture, approach, and risk. Hand the settled result to `to-plan`.

This skill interviews and writes no document: no `plan_<slug>.md`, and no writer, editor or reviewer agent is dispatched.

It plans and does not build: nothing in the working tree changes.

Why the why/what is out of scope: problem framing belongs to `brainstorm-why`, and this skill starts from its approved result, so re-asking it reopens what is already settled.

## Usage

`/brainstorm-how` — no arguments. A run starts from an approved `spec_<slug>.md` in CWD, never from a raw request.

Resolve it before step 1:

- **Exactly one `spec_*.md`** → use it, printing the resolved path.
- **Several** → list them numbered and ask which one via `AskUserQuestion`.
- **None** → hard-stop with nothing interviewed, naming `brainstorm-why` then `to-spec` as how to produce one.

## Process

Seed the TaskList per CLAUDE.md's `[Reminder]` category with one entry per step below. Seeding is scaffolding only, never a go-ahead to run a step early.

### 1. Run the interview

This skill wraps no module: it offers no choice at pre-flight, runs no `get-enabled-modules.py`, and nests no `Skill()` call.

It never offers `sdd-grill-tech`, even on a machine where the Arco plugin is present.

Why: `sdd-grill-tech` hard-requires an Arco-pipeline `domains/**/<initiative>/prd.md` with `status != draft`, which this design never produces, so a `spec_<slug>.md` in CWD can never satisfy it.

Read [`../brainstorm-why/references/interview-engine.md`](../brainstorm-why/references/interview-engine.md) and run it, never restating its discipline here. The engine lives under `brainstorm-why/` so that one directory owns it.

- Seed: the approved spec, which is the solution space, plus your own codebase read of where the change lands.
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
