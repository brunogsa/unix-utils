---
name: brainstorm
description: "Run a Socratic interview that turns an idea into settled decisions, then offer to-spec. USE when user says 'brainstorm', or asks to plan/design/scope work. Writes no documents. Never for writing code, bug fixes, or code review."
disable-model-invocation: false
---

# Brainstorm

Help the user explore and refine an idea through a Socratic interview, then hand the settled result to `to-spec`.

This skill interviews and writes no document: no `spec_<slug>.md`, no plan, and no writer, editor or reviewer agent is dispatched.

It plans and does not build: nothing in the working tree changes — no scaffolded files, no stubs, no config edited to unblock a later step.

Why documents live elsewhere: one skill doing both the interview and the document generation lost the interview when a compaction hit mid-run, so `to-spec` now writes the documents from context this session already holds.

There is no `full`/`light` mode. Whether the user invokes `to-spec` afterwards is the choice that mode used to encode.

## Usage

`/brainstorm` — no arguments.

A run always starts from an idea, never from a document, so there is no path to resolve and no prior spec or plan to reconcile.

## Process

Seed the TaskList per CLAUDE.md's `[Reminder]` category with one entry per step below.

Seeding is scaffolding only — creating a `[Reminder]` entry is never a go-ahead to run its step early.

### 1. Gather starting context

Create `<scratchpad>/notes.md` in the harness scratchpad directory named in this session's own system prompt, per CLAUDE.md's Note-taking discipline.
Never an invented ad-hoc per-skill `/tmp` path.
It stays alive for the whole interview under the five fixed headings that discipline defines, so `to-spec` can still see why each step decided what it did.

Then seed the brainstorm from session context — conversation history plus codebase understanding.

Read what the request touches in the codebase before asking anything: the files it changes, the modules it neighbours, the conventions it must match.

Why read first: everything discoverable there is legwork, and step 3 spends its rounds only on what the codebase can't answer.

### 2. Probe scope before deep questions

Before drilling into requirements, check whether the request describes multiple independent subsystems.
Signals: multiple unrelated nouns, distinct user roles, separate persistence concerns, or features that could each ship independently.

If it looks decomposable, follow [`references/decompose-scope.md`](references/decompose-scope.md) to surface it and handle the user's answer.

### 3. Interview the user

**Read the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`) before the first round.**

Why up front: its categories then shape every question you ask, instead of becoming a checklist swept at the end.
By then the requirements are settled, so a boundary raised that late reopens answered questions rather than refining them.

Write every answer that shapes the spec into `notes.md` as the round closes, per step 1 — decisions under `## Decisions` with their why, alternatives under `## Rejected` with why they lost.

Ask clarifying questions (Socratic style). Focus on:
- What problem are we solving? (Background)
- What is goal and success metrics/KPIs? (Goal)
- Who benefits and how? (User Stories)
- What does success look like? (Testable Acceptance Criteria — BDD scenarios)
- What constraints exist? (Non-Functional and Technical Requirements)
- What's unclear? (Open Questions)

**Ask 2-3 questions per round, via the AskUserQuestion tool** — options with your recommended answer first, plus one line of reasoning.
Fall back to free-text chat only when a question can't be shaped into options.

**Split facts from decisions before asking.** Anything discoverable from the codebase, session context, or a web search is legwork — look it up yourself, never ask it.
Questions to the user are reserved for genuine decisions: preferences, priorities, and context only they hold.

Why: a look-up-able fact wastes an interview round on work the agent can do; a recommendation turns each remaining question from an essay prompt into a confirm-or-override.

**CRITICAL: For Testable Acceptance Criteria, actively probe for coverage gaps.** Happy-path scenarios are easy to elicit; corner cases and failure modes need pulling.

Push the user through every category of the taxonomy read at the top of this step — all of them, before the interview closes. Illustrative probes:

- **Corner cases** (e.g.): empty inputs, max sizes/limits, boundary values.
- **Failure modes** (e.g.): downstream timeouts, partial failures, rate limits.

If the user only describes the happy path, ask explicitly: "what should happen when X is empty / oversized / invalid / unavailable?"

**Close every question this step raises, here** — a question carried forward reaches the spec as an Open Question and costs the user a whole extra round later.

**Exit criterion**: end interview rounds once the latest round adds no new requirement or constraint changes, every coverage-taxonomy category is covered or explicitly ruled out, and nothing raised is still open.

### 4. Propose 2-3 approaches with trade-offs

Present 2-3 viable approaches conversationally.
Lead with your recommendation and the reasoning. Cover the trade-off axes that matter for this idea (complexity, blast radius, reversibility, dependencies, time-to-first-value).

Get a directional pick from the user before composing the brief.
Capture the outcome under `notes.md`'s `## Decisions` heading; the spec writer folds it into the document's Decisions section as one marker, with the discarded alternatives as sub-bullets.

Why keep the discarded ones: naming what lost, and why, stops the next session re-deriving the same alternatives and re-litigating them.
It also surfaces when the constraint that killed an alternative no longer applies.

**The interview closes here.** Compose `<scratchpad>/brainstorm-why-brief.md`, which `to-spec` reads and stops without.
It carries the verbatim original request, every finding with its `file:line` evidence, and every decision with the alternatives it discarded.
It is elaborated past what `notes.md`'s density guide allows, since the brief's zero-context reader needs detail that guide deliberately omits.

Why compose it only now: any earlier would hand off unfinished results.

### 5. Offer `to-spec`

Ask via `AskUserQuestion`, recommended answer first: write the spec with `to-spec`, or something else.
Keep a free-text "something else" option always open, since the user may want to stop, keep interviewing, or go elsewhere.

Do not run `to-spec` in this session until the user picks it.

Why no `/clear` hand-off: the old one existed because `/implement` re-grounds from approved documents on disk, but `to-spec` grounds from this session's context and scratchpad, so clearing first would destroy exactly what it reads.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
