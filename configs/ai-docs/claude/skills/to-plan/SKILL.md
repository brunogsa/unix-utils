---
name: to-plan
description: "Turn already-held context into plan_<slug>.md by dispatching plan-writer, then self-review it. USE when the user says 'write the plan' or 'to-plan', or brainstorm-how offers it. Never interviews; a spec is optional."
---

# To Plan

Write `plan_<slug>.md` from context that already exists, self-review it, and offer `sdd-to-linear`.

This skill consumes context and never builds it.

It runs no interview, writes no findings of its own, and appends nothing to any brief or to `notes.md`.

Why: the skill that produced a finding owns persisting it, so a `to-plan` that had to append would be repairing an upstream skill's omission.

The document conventions — naming, template, self-review gates — live in the `spec-driven-development` library.

Read it by path (`~/.claude/skills/spec-driven-development/SKILL.md`), never via the Skill tool; its `disable-model-invocation: true` keeps it out of the skill listing.

## Usage

`/to-plan` — no arguments. It is model-invoked too, so a session that just finished `brainstorm-how` can reach it without the user typing the command.

## Process

### 1. Ground from what already exists

Always ground `plan-writer` in both of these:

- The live session context.
- `<scratchpad>/notes.md`, in the harness scratchpad directory named in this session's own system prompt, which carries the technical findings.

Add each of these on top, only where it exists:

- `spec_<slug>.md`.
- `<scratchpad>/brainstorm-why-brief.md` and `<scratchpad>/brainstorm-how-brief.md`.

**A spec is a bonus, never a precondition.** `to-plan` runs and produces a plan with no `spec_<slug>.md` present at all.

Why: a compaction between `brainstorm-how` and `to-plan` must lose nothing, and the scratchpad notes plus the briefs survive it where the conversation does not.

**A section these sources cannot ground is flagged, never invented.** Put it in the plan's `## Open Questions`.

### 2. Settle the three rigor toggles

One `AskUserQuestion` call, recommended answer first, before anything is dispatched:

- **"Every line traces to an AC?"** — `traces_to_ac`.
- **"Right-sized plan?"** — `right_sized`.
- **"Qualitative pass?"** — `qualitative_pass`, default yes.

Persist the answers to `/tmp/sdd_<session_id>.json` as booleans under exactly those three field names, keeping any other field already in the file.

Answer them fresh each run, and never write them into the plan or any committed file.

A no on `qualitative_pass` drops the qualitative checklist and nothing else; the fail-closed judged checks run regardless.

Why ask here: the toggles gate the document, not the interview, so the interview skills never need to know about self-review mode.

### 3. Dispatch `plan-writer`

Derive a short kebab-case `<slug>` from the spec when one exists, else from the original request in the briefs or session context, without asking the user.

`plan-writer` loads `task-breakdown` over the work, per `~/.claude/skills/spec-driven-development/references/plan-writing.md`; this session does not load it.

Dispatch `agent(subAgent=plan-writer, title=Write the plan)` in the background and wait for it. Pass it:

- The absolute path to `notes.md` and to each existing brief, since a dispatched subagent gets its own different scratchpad directory.
- The slug.
- The spec's path, when one exists.
- An instruction to wrap the body of every machine-facing section the human will not read in a `<details>` block collapsed by default, with the `##` heading left outside the block.

Machine-facing means the derived `## Files to Create or Modify` union and any other section written for scripts or the executing agent.

Why the heading stays outside: a script grepping `## ` and a reader's outline both still find every section.

**This session never writes the plan itself.** Every later edit goes through `agent(subAgent=plan-editor, title=Apply plan edits)` carrying the exact changes.

**A failed dispatch ends the run.** When the dispatch errors, or returns and `plan_<slug>.md` does not exist on disk, report the failure with the agent's error and stop.

Offer nothing, not `sdd-to-linear` and not a retry, and never present the failed write as a finished plan.

Check the file on disk, never the agent's "done" message alone.

Then check the written plan: every machine-facing section body sits inside a collapsed `<details>` block with its `##` heading outside it, fixing each miss through `plan-editor`.

### 4. Self-review the plan once, with fresh eyes

Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now.

Run the deterministic gates first with `~/.claude/skills/spec-driven-development/scripts/check-deterministic-gates.sh <plan> [<spec>]`, passing the spec path when one exists, and fix each miss through `plan-editor`.

Then dispatch `agent(subAgent=plan-reviewer, effort=high, title=Fresh-eyes review of plan)` in the background, pointed at the plan file alone (plus the spec path when one exists).

Its qualitative leg runs only when `qualitative_pass` is true, read back from `/tmp/sdd_<session_id>.json`; its fail-closed judged checks run regardless.

Decide each finding yourself and dispatch `plan-editor` with the ones you accept.

Report every finding to the user in one block, applied or skipped with the reason, naming any check skipped by toggle.

This runs once per plan, never twice over the same text.

Why fresh eyes: this session never wrote the plan, but it holds the context and would read the plan as complete from memory.

### 5. Offer `sdd-to-linear`

Give the user the plan's path and offer `sdd-to-linear`, with a free-text "something else" option always open. Do not run it in this session.
