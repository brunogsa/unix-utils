# Authoring a procedural skill's assets/flowchart.md

Read this before writing or regenerating one.

The file carries an H1 title, a preamble marking it human-facing and non-authoritative (SKILL.md's numbered steps win on conflict), then one mermaid flowchart of the control flow.

## What the flowchart covers

- The trigger/invocation that starts the skill, its steps/phases, and every loop with its exit condition.
- User-interaction points: the questions asked (interviews, toggles) and the manual gates where the human approves before flow continues.
- Durable-state writes: TaskList usage (tasks created, `[Reminder]` entries) and scratchpad/run-state updates, each with a short why.
- Delegation: other skills loaded, and every subagent dispatch labeled with agent type, model, effort, and parallel (∥) vs serial.
- Hooks/scripts that steer the flow (state machines, Stop hooks).

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

Regenerate it whenever the skill's flow changes, and validate the render with `mmdc` (dispatch the `mermaid-fixer` agent on failures); author it under the `mermaid-diagrams` skill.
