---
name: to-spec
description: "Turn an already-held interview into spec_<slug>.md by dispatching spec-writer, then self-review it. USE when the user says 'write the spec' or 'to-spec', or brainstorm-why offers it. Interviews only to settle open questions; never for plans or code."
---

# To Spec

Write `spec_<slug>.md` from context that already exists, self-review it, and offer `brainstorm-how`.

This skill consumes context and never builds it.

It builds no context through an interview - it asks only to settle the written spec's open questions - writes no findings of its own, and appends nothing to any brief or to `notes.md`.

Why: the skill that produced a finding owns persisting it, so a `to-spec` that had to append would be repairing an upstream skill's omission.

The document conventions - naming, template, self-review gates - live in the `spec-driven-development` library.

Read it by path (`~/.claude/skills/spec-driven-development/SKILL.md`), never via the Skill tool; its `disable-model-invocation: true` keeps it out of the skill listing.

## Usage

`/to-spec` - no arguments. It is model-invoked too, so a session that just finished `brainstorm-why` can reach it without the user typing the command.

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

### 2. Settle the rigor toggle

One `AskUserQuestion` call, recommended answer first, before anything is dispatched:

- **"Qualitative pass?"** - `qualitative_pass`, default yes.

Persist the answer to `/tmp/sdd_<session_id>.json` as a boolean under exactly that field name, keeping any other field already in the file.

Answer it fresh each run, and never write them into the spec or any committed file.

A no on `qualitative_pass` drops the qualitative checklist and nothing else; the fail-closed judged checks run regardless.

Why ask here: the toggles gate the document, not the interview, so the interview skills never need to know about self-review mode.

### 3. Dispatch `spec-writer`

Derive a short kebab-case `<slug>` from the brief's original request yourself, without asking the user.

Dispatch `agent(subAgent=spec-writer, title=Write the spec)` in the background and wait for it. Pass it:

- The absolute path to `brainstorm-why-brief.md` in this session's scratchpad, since a dispatched subagent gets its own different scratchpad directory.
- The slug.
- The absolute path to this session's `notes.md`, when one exists, since the subagent cannot find it in its own scratchpad directory.

**This session never writes the spec itself.** Every later edit goes through `agent(subAgent=spec-editor, title=Apply spec edits)` carrying the exact changes.

**A failed dispatch ends the run.** When the dispatch errors, or returns and `spec_<slug>.md` does not exist on disk, report the failure with the agent's error and stop.

Offer nothing, not `brainstorm-how` and not a retry, and never present the failed write as a finished spec.

Check the file on disk, never the agent's "done" message alone.

### 4. Interview the user on every open question

Read the spec's `## Open Questions` section. When it is empty, skip this step.

Interview the user on every entry before any review runs, with `AskUserQuestion`: recommended answer first, each question self-contained - why it exists, what changes per option, and the thing decided quoted rather than named by id or line.

Cluster every question open at the same moment into one call, at most 4 per call, and use more calls when there are more.

Settle each question in the interview by default. Apply each answer through `agent(subAgent=spec-editor, title=Apply spec edits)`: remove the answered entry from `## Open Questions` and write the decision where it belongs in the spec.

Keep an entry in `## Open Questions` only when the user explicitly says to keep it open, typically because they don't know either and it needs discovery. Never keep one on your own judgment.

Why before the review: the reviewer judges the settled spec, so reviewing a spec with open questions reviews text the answers will change, and the review would run twice.

Why settle by default: the common path is a spec with no open question left, and an entry the user never chose to keep is a decision this session skipped asking about.

### 5. Self-review the spec once, with fresh eyes

Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now.

Run the deterministic gates first with `~/.claude/skills/spec-driven-development/scripts/check-deterministic-gates.sh --spec-only <spec>`, and fix each miss through `spec-editor`.

A runner exit of 1 is a finding to fix. **Exit 2, or a `FAIL exit=2` line, means a gate could not run** - report it to the user, never route it to `spec-editor`, and never count the spec as gated.

Then dispatch `agent(subAgent=spec-reviewer, effort=xhigh, title=Fresh-eyes review of spec)` in the background, pointed at the spec file alone, with two jobs:

- **Always - "How would this break?"**: every boundary and failure-category row instantiated or opted out, and every AC carrying a surfaced failure mode.
- **Only when `qualitative_pass` is true**, read back from `/tmp/sdd_<session_id>.json`: placeholders, contradictions, ambiguity, completeness, human-reviewable. Exclude PR-size, plan-contradiction and Scope.

Decide each finding yourself and dispatch `spec-editor` with the ones you accept.

Report every finding to the user in one block, applied or skipped with the reason, naming any check skipped by toggle.

This runs once per spec, never twice over the same text.

Why fresh eyes: this session never wrote the spec, but it holds the interview and would read the spec as complete from memory.

### 6. Offer `brainstorm-how`

Give the user the spec's path and offer `brainstorm-how`. Do not run it in this session.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it - non-authoritative, the steps above win; regenerate it whenever the flow changes.
