# Authoring a procedural skill's assets/flowchart.md

Read this before writing or regenerating one.

The file carries an H1 title, a preamble marking it human-facing and non-authoritative (SKILL.md's numbered steps win on conflict), then one mermaid flowchart of the control flow.

## The diagram stands alone

A human understands the entire skill from the diagram alone, never opening SKILL.md to decode a node.

Spell out every step this skill owns.
Never collapse a range into a pointer at the prose — "mirror steps 1-8 as TaskList entries".
Never label a node with a bare section number the reader has to go look up.

This does not contradict collapsing a callee (below). Collapse what belongs to *another* file's flow; never what belongs to this skill's own steps.

Why: the flowchart is read *instead of* the numbered steps, not alongside them.
A pointer back into SKILL.md hands the reader the very cross-reference the diagram existed to spare them, and it rots the moment a step is renumbered.

## What the flowchart covers

- The trigger/invocation that starts the skill, its steps/phases, and every loop with its exit condition.
- User-interaction points: the questions asked (interviews, toggles) and the manual gates where the human approves before flow continues.
- Durable-state writes: scratchpad/run-state updates, plus **one node per TaskList entry**, each with a short why.
- Delegation: other skills loaded, and every subagent dispatch labeled with agent type, model, effort, and parallel (∥) vs serial.
- Hooks/scripts that steer the flow (state machines, Stop hooks).

## One node per TaskList entry

Word each node as the entry it creates: `Add to TaskList a [Reminder] for Step 3: interview the user`.

Wrap a statically-known set in a `subgraph` whose label carries the why — seeded upfront, before the first step runs, and surviving compaction.

Keep a runtime-sized set — one entry per plan task, per review cluster — as a single node naming what one entry covers, since the count isn't knowable at authoring time.

Why: the diagram is the human's audit of the run's whole timeline, so a collapsed range hides a step that could silently never be seeded.

## Scope it to this skill's own flow

A skill it loads, an agent it dispatches, or a hook that fires is **one collapsed node** — name it and stop there.

Draw the edge in and the edge out; never redraw what happens inside.

Keep only what this skill's own flow branches on.
A returned status the next decision node reads is this skill's business; how the callee produced it is not.

Why: those internals live in their own file and change on that file's schedule.
A copy here rots with nobody having touched this diagram, and the reader can't tell the stale copy from the live one.

Collapsing also holds the diagram at a single altitude, which is what makes it auditable at a glance.

Bad: a dispatch node listing the five skills the agent preloads, or a hook node spelling out which write paths it auto-approves.

Good: `Dispatch tdd-coder (sonnet, maxTurns 128, serial)`, and `Hook: deep-reviewer-write-guard`.

## Node kinds and rendering

Mark node kinds with the shared classDef legend — `:::start` (trigger), `:::gate` (question/approval), `:::dispatch` (subagent), `:::state` (durable-state write), `:::skill` (skill load), `:::hook` (hook/script).

Copy the classDef color block verbatim from any existing flowchart.md so all six kinds render identically across skills.

Reference the flowchart from SKILL.md with a one-liner that tells the model NOT to load it.

Regenerate it whenever the skill's flow changes, and validate the render with `mmdc` (on failures, dispatch `agent(subAgent=mermaid-fixer, title=Fix skill flowchart)`); author it under the `mermaid-diagrams` skill.
