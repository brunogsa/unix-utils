---
name: to-spec
description: "Turn an already-held interview into spec_<slug>.md by dispatching spec-writer, then self-review it. USE when the user says 'write the spec' or 'to-spec', or brainstorm-why offers it. Never interviews; never for plans or code."
---

# To Spec

Write `spec_<slug>.md` from context that already exists, self-review it, and offer `brainstorm-how`.

This skill consumes context and never builds it.

It runs no interview, writes no findings of its own, and appends nothing to any brief or to `notes.md`.

Why: the skill that produced a finding owns persisting it, so a `to-spec` that had to append would be repairing an upstream skill's omission.

The document conventions — naming, template, self-review gates — live in the `spec-driven-development` library.

Read it by path (`~/.claude/skills/spec-driven-development/SKILL.md`), never via the Skill tool; its `disable-model-invocation: true` keeps it out of the skill listing.

## Usage

`/to-spec` — no arguments. It is model-invoked too, so a session that just finished `brainstorm-why` can reach it without the user typing the command.

## Process

### 1. Ground from what already exists

Read, and nothing else:

- The live session context.
- `<scratchpad>/notes.md`, in the harness scratchpad directory named in this session's own system prompt.
- `<scratchpad>/brainstorm-why-brief.md`, which carries the verbatim original request, every finding with its `file:line` evidence, and every decision with the alternatives it discarded.

Why these three only: they are where `brainstorm-why` persisted its findings, including any `sdd:sdd-grill` output, so nothing else needs re-deriving.

**No brief at that path means stop.** Tell the user `brainstorm-why` has not run, and offer it. Never reconstruct the brief from the conversation, since that is building context.

**An absent or empty `sdd-grill` section is not a gap.** Dispatch anyway, never ask the user to supply it.

Why: `sdd-grill` is opt-in at `brainstorm-why`, so a scratchpad without its output is a normal run.

### 2. Settle the three rigor toggles

One `AskUserQuestion` call, recommended answer first, before anything is dispatched:

- **"Every line traces to an AC?"** — `traces_to_ac`.
- **"Right-sized plan?"** — `right_sized`.
- **"Qualitative pass?"** — `qualitative_pass`, default yes.

Persist the answers to `/tmp/sdd_<session_id>.json` as booleans under exactly those three field names, keeping any other field already in the file.

Answer them fresh each run, and never write them into the spec or any committed file.

A no on `qualitative_pass` drops the qualitative checklist and nothing else; the fail-closed judged checks run regardless.

Why ask here: the toggles gate the document, not the interview, so the interview skills never need to know about self-review mode.

### 3. Dispatch `spec-writer`

Derive a short kebab-case `<slug>` from the brief's original request yourself, without asking the user.

Dispatch `agent(subAgent=spec-writer, title=Write the spec)` in the background and wait for it. Pass it:

- The absolute path to `brainstorm-why-brief.md` in this session's scratchpad, since a dispatched subagent gets its own different scratchpad directory.
- The slug.

**This session never writes the spec itself.** Every later edit goes through `agent(subAgent=spec-editor, title=Apply spec edits)` carrying the exact changes.

**A failed dispatch ends the run.** When the dispatch errors, or returns and `spec_<slug>.md` does not exist on disk, report the failure with the agent's error and stop.

Offer nothing, not `brainstorm-how` and not a retry, and never present the failed write as a finished spec.

Check the file on disk, never the agent's "done" message alone.

### 4. Self-review the spec once, with fresh eyes

Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now, and run `check-sections.sh <spec> ~/.claude/skills/spec-driven-development/assets/spec-template.md` first, fixing each miss through `spec-editor`.

Then dispatch `agent(subAgent=spec-reviewer, effort=high, title=Fresh-eyes review of spec)` in the background, pointed at the spec file alone, with two jobs:

- **Always — "How would this break?"**: every boundary and failure-category row instantiated or opted out, and every AC carrying a surfaced failure mode.
- **Only when `qualitative_pass` is true**, read back from `/tmp/sdd_<session_id>.json`: placeholders, contradictions, ambiguity, completeness, human-reviewable. Exclude PR-size, plan-contradiction and Scope.

Decide each finding yourself and dispatch `spec-editor` with the ones you accept.

Report every finding to the user in one block, applied or skipped with the reason, naming any check skipped by toggle.

This runs once per spec, never twice over the same text.

Why fresh eyes: this session never wrote the spec, but it holds the interview and would read the spec as complete from memory.

### 5. Offer `brainstorm-how`

Give the user the spec's path and offer `brainstorm-how`. Do not run it in this session.
