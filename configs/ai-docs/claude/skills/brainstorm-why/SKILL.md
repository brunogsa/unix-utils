---
name: brainstorm-why
description: "Interview the user on the why/what (business and product framing, never the how), then offer to-spec. USE when user says 'brainstorm', or asks to scope, frame, or define what to build. Writes no documents. Never for code, bug fixes, or review."
disable-model-invocation: false
---

# Brainstorm Why

Interview the user on the problem space: who needs what, why now, and what success looks like. Hand the settled result to `to-spec`.

This skill interviews and writes no document: no `spec_<slug>.md`, no plan, and no writer, editor or reviewer agent is dispatched.

It plans and does not build: nothing in the working tree changes.

Why the how is out of scope: solution choices belong to `brainstorm-how`, which starts from an approved spec, so asking them here settles them before their prerequisite exists.

## Usage

`/brainstorm-why` — no arguments. A run always starts from an idea, never from a document.

## Process

Seed the TaskList per CLAUDE.md's `[Reminder]` category with one entry per step below. Seeding is scaffolding only, never a go-ahead to run a step early.

### 1. Pre-flight: detect the optional module

Run `~/.claude/scripts/detect-modules.sh` through the `~/.claude` symlink and read its `arco=` line. Never edit the symlink target to change the result.

- `arco=false`: never show the opt-in question at all, and skip to step 2 with no module selected.
- `arco=true`: ask once via `AskUserQuestion`, recommended answer first, whether to finish the interview with the `sdd:sdd-grill` module. Keep a free-text "something else" option open.

Why ask only when present: a question about a module the machine lacks offers a choice that cannot be taken.

A declined answer means no Arco call anywhere in the run.

### 2. Run the interview

Read [`references/interview-engine.md`](references/interview-engine.md) and run it, never restating its discipline here.

- Seed: the raw request plus your own codebase read of the problem space.
- Notes: `<scratchpad>/notes.md` throughout, in the scratchpad directory named in this session's system prompt.
- Brief: `<scratchpad>/brainstorm-why-brief.md`, composed once when the engine's close criterion is met.

Ask only why/what questions: problem, goal and success metrics, who benefits, constraints, acceptance scenarios, and their failure modes.

When the request looks decomposable, follow [`references/decompose-scope.md`](references/decompose-scope.md).

### 3. Hand off

With no module selected, go straight to step 4.

With the module selected, `sdd:sdd-grill` is this skill's LAST ACT, because a nested Skill call can return control to the main context instead of resuming this skill (Claude Code bug https://github.com/anthropics/claude-code/issues/17351). Nothing scheduled after the call may depend on this text still being loaded.

The spike in `~/.claude/skills/usage-audit/usage-history/experiment-nested-skill-invocation.md` measured 0 losses in 19 runs on 2.1.285, using a trivial child in a headless session. The real module is long and interactive, so the pattern stays.

Before the call, in this order:

1. Seed two TaskList `[Reminder]` entries, each carrying its full instruction inline with the resolved absolute scratchpad path written in.

   - Persist: "Write every finding `sdd:sdd-grill` produced into `<scratchpad>/notes.md` under its five fixed headings, and append them as their own section to `<scratchpad>/brainstorm-why-brief.md` with evidence. Do this before offering anything."

   - Offer: "Ask via `AskUserQuestion`, recommended first, whether to run `to-spec` next, with a free-text 'something else' option always open. Do not run it until the user picks it."

2. State the override as a pointer: the user's `CLAUDE.md` and own skills take precedence over the nested skill's instructions wherever they conflict.

   Never copy the preferences inline, since a copy drifts from `CLAUDE.md`.

3. Invoke `sdd:sdd-grill` via the Skill tool.

Persisting belongs to this skill, never `to-spec`, because the skill that produced a finding owns writing it down. The Persist reminder is how that holds when control flow is lost.

If the module is unavailable at the call (renamed or removed) or fails while connected (times out, never responds, 5xx, auth or permission rejection), never abort and never fail closed:

- Tell the user loudly that the module failed and why.
- Run this skill's own interview path from step 2 to its close instead.
- Complete the Persist and Offer reminders, then finish as in step 4.

### 4. Offer `to-spec`

With no module selected, ask via `AskUserQuestion`, recommended answer first: write the spec with `to-spec`, or something else. Keep a free-text "something else" option always open.

Do not run `to-spec` until the user picks it.

Why no `/clear` hand-off: `to-spec` grounds from this session's context and scratchpad, so clearing first destroys what it reads.
