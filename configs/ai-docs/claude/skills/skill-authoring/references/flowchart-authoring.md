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

## Every node carries an id — numbers down the main line, letters for branches

Prefix each node's label with its id and a `. ` — `5. Persist all 3 answers to /tmp/sdd_&lt;session_id&gt;.json`.

Ids are diagram-local and run in execution order, top to bottom: `1`, `2`, `3`, … one per node on the main line, trigger and decision nodes included.

A node hanging off a decision takes that decision's number plus a letter — `5a`, `5b`, `5c`.
The main line then resumes at `6`, where those branches rejoin.

Where one branch terminates (abort, stop, skip) and another carries the flow onward, the onward branch IS the main line — only the terminal branch takes a letter.

A branch running several nodes deep before it rejoins takes sequential letters — `5b`, `5c` — one per node down that path.

Assign the letters depth-first: a multi-node branch consumes its whole run of letters before the next branch off that same decision starts.

A loop body letters off its loop-check decision, and the loop's exit edge continues the main line.

A node three or more branches converge on takes a plain main-line number, since no single decision owns it.

A fork nested inside a lettered branch appends a digit instead: `5c1`, `5c2`.

Deeper nesting keeps alternating letter and digit — `5c1a`, `5c1a1` — so each character is one level and the id stays parseable.
Never append a digit to a digit: `5c11` is unreadable, and `5c1a` says the same thing.

An offshoot that never rejoins the main line letters the same way even when it hangs off a plain node rather than a decision.

Number a subgraph's members off the subgraph's own id when it holds a static set of siblings — a TaskList seed sitting at `2` holds `2a` … `2j`.

A subgraph that merely groups a long stretch of the flow (a per-task loop body, a phase) takes no id, and its nodes number as ordinary main-line and branch nodes.
Lettering fifty loop-body nodes off one id would need double letters and collide with the nested-fork digits — the opposite of what the ids are for.

Keep the sequence gapless on every regeneration, renumbering whatever a flow change displaced.

Name each mermaid node identifier after its id with an `n` prefix — `n5c1` — so the edge list reads in the same numbering as the labels.

A node that maps to a numbered SKILL.md step keeps its `Step N ·` marker after the id: `9. Step 4 · Interview (Socratic rounds)`.
The two numbers answer different questions — the id is where the node sits in this diagram, the marker is which step of the skill it implements.

Normalize any bare `N. ` step marker into that `Step N ·` form, so no label ever opens with two bare numbers.

Examples: `3. Step 1 · Glob the CWD`, never `3. 1. Glob the CWD`.

Why: the id is how the human names the node they want changed, and "drop 5c1" is unambiguous where a quoted label is not.
Numbering also makes the ordering readable outright, instead of something the eye reconstructs by following arrows.

An id is a position inside one revision of one diagram, so it is never a durable reference.
Never cite one from SKILL.md, another flowchart, a commit message, or a code comment — regeneration renumbers it silently.

## What the flowchart covers

- The trigger/invocation that starts the skill, its steps/phases, and every loop with its exit condition.
- User-interaction points: the questions asked (interviews, toggles) and the manual gates where the human approves before flow continues.
- Durable-state writes: scratchpad/run-state updates, plus **one node per TaskList entry**, each with a short why.
- Delegation: other skills loaded, and every subagent dispatch labeled with agent type and parallel (∥) vs serial — model and effort only per the rule below.
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

Good: `Dispatch tdd-coder (agent-pinned, background, serial)`, and `Hook: deep-reviewer-write-guard`.

## Model and effort come from the agent file, never the node label

Write `agent-pinned` whenever `agents/<name>.md` pins `model:`/`effort:` — never copy the values, and never copy `maxTurns` either.

Spell out an explicit tier only where the caller genuinely owns it: an unpinned agent like `general-purpose`, or a real per-call override.

Separate the parts with `·`, and always keep ∥/serial and background/foreground, which are the caller's own facts.

Why: a copied pin rots on the agent file's schedule rather than this diagram's, and nobody reopens six flowcharts when retuning one tier.

Every hand-copied effort in these files had already gone stale — two read "default effort" for agents since pinned to `low`, two more read "inherits".

## Node kinds and rendering

Mark node kinds with the shared classDef legend — `:::start` (trigger), `:::gate` (question/approval), `:::dispatch` (subagent), `:::state` (durable-state write), `:::skill` (skill load), `:::hook` (hook/script).

Copy the classDef color block verbatim from any existing flowchart.md so all six kinds render identically across skills.

Reference the flowchart from SKILL.md with a one-liner that tells the model NOT to load it.

Regenerate it whenever the skill's flow changes, and validate the render with `mmdc` (on failures, dispatch `agent(subAgent=mermaid-fixer, title=Fix skill flowchart)`); author it under the `mermaid-diagrams` skill.
