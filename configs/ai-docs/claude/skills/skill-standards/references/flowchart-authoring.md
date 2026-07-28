---
# performance-check budget override, approved by the user 2026-07-27.
# This file governs both renderings a flowchart.md carries, and the two always
# load together on the same run — so splitting it would create the co-loading
# pair this skill's own rule forbids, and trimming to 1024 would delete the
# pseudo-code rules rather than tighten them.
words-budget: 2048
---

# Authoring a procedural skill's assets/flowchart.md

Read this before writing or regenerating one.

The file carries an H1 title and a human-facing non-authoritative preamble (SKILL.md's numbered steps win on conflict).

Then the control flow, rendered twice: a `## Pseudo-code` section, followed by a `## Flowchart` section holding one mermaid diagram.

Both renderings are mandatory and cover the same steps. Write the diagram first — the pseudo-code cross-references its node ids.

## The diagram stands alone

A human understands the entire skill from the diagram alone, never opening SKILL.md to decode a node.

Spell out every step this skill owns; never collapse a range into a prose pointer ("mirror steps 1-8 as TaskList entries"), and never label a node with a bare section number.

This doesn't contradict collapsing a callee (below): collapse what belongs to *another* file's flow, never this skill's own steps.

Why: the flowchart is read *instead of* the numbered steps — a pointer into SKILL.md reintroduces the cross-reference the diagram exists to spare, and rots the moment a step is renumbered.

## Every node carries an id

Prefix each label with its id and `. ` (`5. Persist all 3 answers to /tmp/sdd_&lt;session_id&gt;.json`).

Ids are diagram-local, ordered top to bottom (`1`, `2`, `3`, …), one per main-line node including triggers and decisions.

A node hanging off a decision takes that decision's number plus a letter (`5a`, `5b`, `5c`), and the main line resumes at `6` where branches rejoin.

Where one branch terminates (abort/stop/skip) and another continues, the onward branch IS the main line — only the terminal branch gets a letter.

A multi-node branch takes sequential letters (`5b`, `5c`), assigned depth-first: it consumes its whole run before the next sibling branch's letters start.

A loop body letters off its loop-check decision, and the exit edge continues the main line.

A node where 3+ branches converge takes a plain main-line number, since no single decision owns it.

A fork inside a lettered branch appends a digit (`5c1`, `5c2`).

Deeper nesting alternates letter/digit (`5c1a`, `5c1a1`), one level per character — never digit-on-digit (`5c11` is unreadable; `5c1a` says the same).

An offshoot that never rejoins still letters this way, even off a plain node.

Number a static sibling set off its subgraph's own id (a TaskList seed at `2` holds `2a`…`2j`).

A subgraph merely grouping a long stretch (a loop body, a phase) takes no id, numbering its nodes as ordinary main-line/branch nodes.

Lettering fifty loop-body nodes off one id would double-letter and collide with nested-fork digits.

Keep the sequence gapless on every regeneration, renumbering whatever a flow change displaced.

Name each mermaid node identifier after its id with an `n` prefix (`n5c1`), so the edge list matches the label numbering.

A node mapping to a SKILL.md step keeps its `Step N ·` marker after the id (`9. Step 4 · Interview (Socratic rounds)`) — id is diagram position, marker is skill step.

Normalize a bare `N. ` marker into that form, so no label opens with two bare numbers (`3. Step 1 · Glob the CWD`, never `3. 1. Glob the CWD`).

Why: the id lets the human name the node they want changed unambiguously ("drop 5c1", unlike a quoted label), and reads ordering instead of tracing arrows.

An id is a position in one diagram revision, never a durable reference — never cite one from SKILL.md, another flowchart, a commit, or a code comment, since regeneration renumbers it silently.

## The pseudo-code rendering

Write it in a ```python fence — near-Python, so it syntax-highlights and reads without a legend. Nothing in it is runnable.

Say so in one line under the `## Pseudo-code` heading: the function names stand for orchestrator actions, not real APIs. Otherwise a reader hunts for `implement_loop_state` in the repo.

Tag every step with its diagram node id as a comment — `# 19c ·` before the line, or trailing it.

Use the plain id, never the `n` prefix, which belongs to mermaid identifiers.

That tagging is the whole point of the second rendering: the two encodings cross-check each other, and a node id with no matching comment is drift a `grep` finds.

State that contract in the preamble, so a future editor knows the comments are load-bearing rather than decoration.

Keep the same `Step N ·`/`§N` skill-step markers the diagram's labels carry, so all three surfaces line up.

Model control flow with real Python control flow — `while` for a retry loop, `match` for a script verdict, early `return` for a halt.

Prefer a named helper (`def halt():`) over duplicating a terminal branch at each of its call sites.

Push what a node's label says into a comment rather than inventing a parameter for it.

An invariant like "ONLY this script sends a unit to the gates" is a comment, since no expression carries it honestly.

Where a diagram edge and a Python construct disagree, follow the diagram and note the seam.

A retry edge pointing back at the dispatch node, not at activation, is an inner `while True` — write that, and say why in a comment.

Why: prose and a diagram fail differently. A diagram hides sequencing inside arrow soup once branches nest, while pseudo-code cannot show convergence at a glance.

Each rendering is legible exactly where the other is weakest, and pairing them costs no context, since the file is parked in assets and never loaded.

## What the flowchart covers

- The trigger/invocation that starts the skill, its steps/phases, and every loop's exit condition.
- User-interaction points: questions asked (interviews, toggles) and manual gates where the human approves flow to continue.
- Durable-state writes: scratchpad/run-state updates, plus **one node per TaskList entry**, each with a short why.
- Delegation: skills loaded, and every subagent dispatch labeled with agent type, parallel (∥)/serial, and model/effort per the rule below.

- Hooks/scripts that steer the flow (state machines, Stop hooks).

## One node per TaskList entry

Word each node as the entry it creates: `Add to TaskList a [Reminder] for Step 3: interview the user`.

Wrap a statically-known set in a `subgraph` whose label carries the why (seeded upfront, before the first step runs, surviving compaction).

Keep a runtime-sized set (one entry per plan task, per review cluster) as a single node naming what it covers, since the count isn't knowable at authoring time.

Why: the diagram is the human's audit of the run's whole timeline — a collapsed range hides a step that could silently never be seeded.

## Scope it to this skill's own flow

Draw the edge in and the edge out; never redraw what happens inside.

Keep only what this skill's own flow branches on: a returned status the next decision node reads is its business, not how the callee produced it.

Why: those internals live in their own file and change on its schedule — a copy here rots unnoticed, and the reader can't tell stale from live.

Collapsing also holds the diagram at a single altitude — what makes it auditable at a glance.

Bad: a dispatch node listing the five skills an agent preloads, or a hook node spelling out its auto-approved write paths. Good: `Dispatch tdd-coder (agent-pinned, background, serial)`, `Hook: deep-reviewer-write-guard`.

## Model and effort come from the agent file

Write `agent-pinned` whenever `agents/<name>.md` pins `model:`/`effort:` — never copy the values or `maxTurns`.

Spell out an explicit tier only where the caller genuinely owns it (an unpinned agent like `general-purpose`, or a per-call override).

Separate the parts with `·`, and always keep ∥/serial and background/foreground, the caller's own facts.

Why: a copied pin rots on the agent file's schedule rather than this diagram's, and nobody reopens six flowcharts when retuning one tier.

Every hand-copied effort here had gone stale: two read "default effort" for agents now pinned `low`, two more read "inherits".

## Node kinds and rendering

Mark node kinds with the shared classDef legend (`:::start` trigger, `:::gate` question/approval, `:::dispatch` subagent, `:::state` durable-state write, `:::skill` skill load, `:::hook` hook/script).

Copied verbatim from any existing flowchart.md, so every skill's diagram renders identically.

Reference the flowchart from SKILL.md with a one-liner telling the model NOT to load it.

Regenerate it whenever the skill's flow changes, and validate the render with `mmdc` (on failures, dispatch `agent(subAgent=mermaid-fixer, title=Fix skill flowchart)`); author it under the `mermaid-diagrams` skill.

## Verify both renderings before you finish

Prove node coverage rather than eyeballing it: extract every declared mermaid node id, extract every id tagged in the pseudo-code, and diff the two sets.

Anything under 100% is an unwritten step, not a formatting nit.

Run `doc-standards/scripts/check-density.sh` on the file. Fenced blocks are skipped, so it only ever measures the preamble — a violation there is real and one sentence away from fixed.

Both renderings count toward the same bundled-resource budgets, so a first pseudo-code pass roughly doubles the file.

Raise `words-budget:`/`lines-budget:` to the next power of 2 only once the file exceeds the current one, per the sizing rules in `../SKILL.md`.
