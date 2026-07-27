---
name: brainstorm
description: "Refine an idea into an approved spec_<slug>.md + plan_<slug>.md via Socratic interview, then self-review and hand off to /implement. USE when the user says 'let's brainstorm', or when planning a non-trivial feature or breaking work into commits."
disable-model-invocation: false
# Trim hierarchy exhausted at 2856 words: two passes cut 337 words of genuine cross-file
# redundancy (CLAUDE.md, light-section-set.md, spec-driven-development). Every remaining step
# fires on every run, so nothing earns a lazy load; spec and plan phases co-fire by contract,
# so splitting would be two files that always load together. Override is the only honest step left.
words-budget: 4096
---

# Brainstorm

Help the user explore and refine an idea into a structured spec, then into a self-reviewed plan ready to hand off.

This skill owns the whole procedure end to end.
The document conventions it writes against — naming, templates, guidelines, self-review gates — live in the `spec-driven-development` library.

Read that library by path — never via the Skill tool; its `disable-model-invocation: true` keeps it out of the skill listing entirely.

**Only step 10 reads it into this session's context.** Every other read happens inside a dispatched agent, and each step below names what its agent reads.

Why nothing loads upfront: steps 1-5 are pure interview and need none of it, and that is the phase that burns the most context before any document exists.

## Usage

`/brainstorm [path/to/spec]`

Examples:
- `/brainstorm spec_auth.md` -- refine an existing spec, at any path the user gives
- `/brainstorm` -- no file: use session context; discover existing `spec_*.md` (see step 2)

## Process

**Before step 1 runs**, seed the TaskList with one `[Reminder]` per step 1-5, in order, and update each as it completes.

Step 6 seeds the rest, once the run's depth is settled — seeding a step the depth later cancels would leave a reminder nobody can complete.

### 1. Pre-flight — settle the run's depth and toggles, and open its state

**Ask all four questions in one message, in one `AskUserQuestion` call, before any other question.**

Ask the full set even when depth will make the toggles moot.
One round-trip beats splitting into two, just to spare a rare run three dead questions.

- **"How much spec/plan writing do you want?"** — the run's depth, one of three:
  - **`full`** (default) — both documents with every section of the `spec-driven-development` templates, and every gate.
  - **`light`** — the same two documents with the briefing sections dropped. Every gate still runs; only prose a human reads is trimmed.
  - **`none`** — no spec and no plan. The interview's output lands on the TaskList, and every document gate is skipped.

- **"Every line traces to an AC?"** — should self-review block on machinery that maps to no acceptance criterion?
- **"Right-sized plan?"** — should a fresh reviewer judge the plan against the original request for gold-plating?
- **"Fresh-eyes self-review?"** — should a `deep-reviewer` subagent read the spec (step 7) and the plan (step 10) before you do? Default yes; a no skips both.

Persist all four answers immediately to `/tmp/sdd_<session_id>.json` — one brainstorm run per session, so the session id alone keys the file.
The depth is the `mode` field, valued exactly `full`, `light`, or `none`; every step below reads it back from there and never re-asks.
Answer them fresh each run: never reuse a previous run's answers, and never write any of them into the spec, the plan, or any committed file.

Why upfront: depth decides whether documents exist; toggles decide how strictly later steps check them.
Settling both early closes off tuning either down after seeing the output.
Why persisted: a compaction between here and self-review would lose them.

Then create the run scratchpad `/tmp/brainstorm_<session_id>.md`, keyed the same way, per CLAUDE.md's scratchpad rules.
It stays alive for the whole run — through the spec, the plan, and self-review — so the plan phase can still see why the spec reads the way it does.

### 2. Gather starting context

**If a file path is provided**: read it and use as the starting point.
**If no file path**: glob `spec_*.md` in CWD (top-level). One match → read it. Multiple → list them numbered and ask which to refine.
**Zero matches**: seed the brainstorm from session context — conversation history plus codebase understanding.

Then check whether a plan already sits beside the resolved spec — the paired file the library's naming convention gives.
Record the answer in the run scratchpad: step 9 needs it to update that plan rather than overwrite it.

### 3. Probe scope before deep questions

Before drilling into requirements, check whether the request describes multiple independent subsystems.
Signals: multiple unrelated nouns, distinct user roles, separate persistence concerns, or features that could each ship independently.

If it looks decomposable, follow [`references/decompose-scope.md`](references/decompose-scope.md) to surface it and handle the user's answer.

### 4. Interview the user

**Read the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`) before the first round.**

Why up front: its categories then shape every question you ask, instead of becoming a checklist swept at the end.
By then the requirements are settled, so a boundary raised that late reopens answered questions rather than refining them.

Write every answer that shapes the spec into the run scratchpad as the round closes, per step 1 — decisions with their why, alternatives with why they lost.

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

Push the user through every category of the taxonomy read at the top of this step — all of them, before the spec is generated. Illustrative probes:

- **Corner cases** (e.g.): empty inputs, max sizes/limits, boundary values.
- **Failure modes** (e.g.): downstream timeouts, partial failures, rate limits.

If the user only describes the happy path, ask explicitly: "what should happen when X is empty / oversized / invalid / unavailable?"

**Exit criterion**: end interview rounds once the latest round adds no new requirement or constraint changes, and every coverage-taxonomy category is covered or explicitly ruled out.

### 5. Propose 2-3 approaches with trade-offs

Present 2-3 viable approaches conversationally.
Lead with your recommendation and the reasoning. Cover the trade-off axes that matter for this idea (complexity, blast radius, reversibility, dependencies, time-to-first-value).

Get a directional pick from the user before writing the spec.
Capture the outcome in the run scratchpad; step 6's fork folds it into the spec's Decisions section as one marker, with the discarded alternatives as sub-bullets.

Why keep the discarded ones: naming what lost, and why, stops the next session re-deriving the same alternatives and re-litigating them.
It also surfaces when the constraint that killed an alternative no longer applies.

### 6. Seed the tail, then dispatch a `fork` to write the spec

**This is the run's only branch on depth.** Read it back from `/tmp/sdd_<session_id>.json`, never re-ask.

- **Depth `none`** → seed one `[Reminder]` per named section of [`references/tasklist-only-mode.md`](references/tasklist-only-mode.md).
  - Then read that file and follow it in place of steps 6-10. Nothing below runs.

- **Depth `full` or `light`** → seed one `[Reminder]` per step 6-10 below, then continue here.

Why here: steps 1-5 interview the same regardless of depth; step 6 is the first step needing a document.

Why `none` reads only that file: every step-10 gate parses a spec or plan, and a `none` run writes neither.

For a fresh idea, derive a short kebab-case `<slug>` from the feature yourself — never ask the user to confirm it.
The plan later inherits that same slug — the shared slug is what pairs the two.

Why not confirm: the slug just names two paired files — a wrong one costs only a rename, and the user is about to read the spec anyway.

Then dispatch `agent(subAgent=fork, title=Write the spec)`, in the foreground — the next step needs the spec to exist. Instruct it to:

- Read `~/.claude/skills/spec-driven-development/SKILL.md` and its `assets/spec-template.md` — that library's Guidelines govern what it writes.

- **At depth `light` only**: also read that library's `references/light-section-set.md`, and write only the spec sections it keeps.

- Read the run scratchpad `/tmp/brainstorm_<session_id>.md` and fold its decisions and discarded alternatives into the spec's Decisions section.
- Write to the provided/discovered path, or for a fresh idea to the spec file in CWD.
- If the file already exists, update it in place — preserve user content, fill gaps, restructure into the template.
- Report back the resolved spec path plus a short summary of what it wrote.

**This session never writes the spec itself** — every later edit goes through another `agent(subAgent=fork, title=Apply spec edits)` carrying the exact changes to make.

Why delegate: writing the spec costs the context to load the library and template — context this session still needs for both reviews and the hand-off.

Why a fork: it inherits this session's full context, already carrying the interview and the approach pick.
A fresh agent would silently invent whatever a re-serialized prompt left out.

### 7. Self-review the spec with fresh eyes

**Skip this step when the pre-flight's self-review toggle is off** — read it back from `/tmp/sdd_<session_id>.json`, never re-ask.

Otherwise dispatch `agent(subAgent=deep-reviewer, title=Fresh-eyes review of spec)`, in the foreground, pointed at the spec file alone.

Tell it to read the Qualitative pass section of `~/.claude/skills/spec-driven-development/references/self-review-checks.md` and apply these items only: placeholders, contradictions, ambiguity, completeness, human-reviewable.

Exclude PR-size and plan-contradiction — no plan exists yet.
Exclude Scope too: step 3 already asked the user about decomposition, and step 10's qualitative pass judges it again over both documents.

Then dispatch `agent(subAgent=fork, title=Apply spec review findings)` to apply every blocking finding.

**Run this review once per spec-writing pass — never twice over the same text.**
A step-8 loop-back through step 6 rewrites the spec, so that new version earns a fresh pass; unchanged text does not, since the user reading it next is the stronger judge.

Why fresh eyes before the user: this session argued itself into every choice, so it reads its own spec as complete because it remembers what the spec never says.
Catching that at step 10 instead would mean the plan was already built on the gap.

Why not a fork for the review: a fork inherits exactly the session bias the review exists to catch.

### 8. Present for review

Give the user the spec's path and ask whether anything is missing or wrong. Nothing else — no summary of the spec, and no report of what step 7 flagged or fixed.

Why nothing else: the user reads the spec itself, so a summary is a second version of the document that can contradict it.
A fixed finding is already invisible in the text they're about to read.

Route rework to the earliest step the feedback invalidates:

- Wording/detail issues → re-dispatch the fork with the edits, then re-present.
- Missing or wrong requirements → back to the step 4 interview.
- Approach concerns → back to the step 5 trade-off discussion.

### 9. Dispatch `plan-writer` to generate the plan

Once the spec is approved, dispatch `agent(subAgent=plan-writer, title=Write implementation plan from spec)` in the foreground, to write the plan from the spec alone.

Pass it:

- The spec file's absolute path, plus the slug you derived in step 6.

- Any planning-conventions file the user named (ADR/HLD/LLD), if one exists.

- **At depth `light`, the instruction to read `~/.claude/skills/spec-driven-development/references/light-section-set.md`** and write only the plan sections it keeps.

- **Whether a plan already sits at the paired path** — per step 2, instruct `plan-writer` to update it in place if it does.
  - Preserve every task status marker and everything below the decisions divider.
  - Fill gaps, restructure into the template.

`plan-writer` resolves the output path itself from the slug — it reads the library that defines how a plan is named, so this session never spells that name out.

Why that last one: `/brainstorm <spec path>` refines a spec mid-implementation, where the paired plan already carries `[Done]` markers and an append-only decisions log.
A regenerated plan destroys both, unrecoverably, since the two documents are untracked by design.

**A gap in the spec never withholds the plan.**
Where the spec doesn't carry a decision the plan needs, `plan-writer` writes the plan around it and records it as a `**QUESTION:**` entry under the plan's Open Questions.

Never close a gap here, or fill one with an invented decision — that's the author-bias this dispatch exists to catch.
Both documents may reach step 10 with Open Questions still open; step 10.2 closes them all, in one batch.

Why batch them there: a gap-by-gap walkthrough stops the run once per item, where one pass at step 10.2 lets the user decide every question against a finished plan.

Should it return a numbered gap list anyway instead of a plan, dispatch a `fork` to record those gaps as Open Questions in the spec.
Then re-dispatch `plan-writer` once — not once per gap.

Why fresh context: this session already talked itself into the spec's choices.
A planner seeing only the spec file tests whether it carries what a plan needs, rather than leaning on session memory the next reader won't have.

### 10. Run self-review, then hand off with `/clear`

`plan-writer` never reviews its own output, so nothing upstream has checked the plan yet — this session runs every gate.

**Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now** — it defines every gate, sorts them into a deterministic and a judged bucket, and gives each bucket's dispatch tier.

**From the second round on, also read that library's `references/delta-scoped-rereview.md`** — it scopes each re-review to what `diff` shows changed, instead of both documents whole.

#### 10.1 Run the deterministic gates

Run that whole bucket to exhaustion, in the order the reference gives — fix each failure, then re-run that gate alone until it passes.

#### 10.2 Close every Open Question before anything expensive runs

Read the Open Questions section of both the spec and the plan.

While either still holds a `**QUESTION:**` entry, interview the user to settle them — `AskUserQuestion`, 2-3 at a time, recommended answer first, exactly as in step 4.
Then dispatch `agent(subAgent=fork, title=Close open questions)` to fold the answers into both documents and leave each Open Questions section reading `None`.

Re-read both sections after each round. **Nothing below runs while a question is open.**

Why gate here: judged gates read both documents whole, so running one over an open question wastes a dispatch reviewing a document about to change.

#### 10.3 Run the judged gates once

Dispatch each judged gate serially, per that reference, titling it after the gate it judges.

Order: qualitative pass first, then the remaining judged checks, including the two toggles read from `/tmp/sdd_<session_id>.json` — never re-asked here.

Skip only the qualitative-pass dispatch when the pre-flight's self-review toggle is off, and say so in the output.

#### 10.4 Loop on any blocking finding

1. **Snapshot both documents into `/tmp/sdd-snapshots/` first**, per that library's `references/delta-scoped-rereview.md`, before any fix lands.

2. **Interview the user to resolve the finding** — never invent the resolution, and never resolve it silently.

3. **Dispatch `agent(subAgent=fork, title=Apply self-review findings)`** to apply what the user decided to the spec, the plan, or both.

4. **Re-run the deterministic gates only** — the fork's edits can break a DAG or an AC-coverage citation, and those are free to re-check.

5. **Hand the user a `diff` of each document against its snapshot** — that annotated diff is what they approve, and it also surfaces edits they made directly.

6. **Ask the user whether to re-run the judged gates.** A yes returns to 10.3, scoped to that diff; a no accepts the documents as they stand.

Repeat until nothing blocks and the user approves the latest diff, or until they decline another round.

Why snapshot before fixing: the diff against it is the only view that shows the user what the fork actually changed.

Why scope the return to that diff: a round that re-reads both documents whole re-pays a full dispatch for text nobody touched.

Then tell the user to run `/clear`, then invoke `/implement`. Don't run `/implement` in this session.

Why: `/implement` re-grounds entirely from the spec and the plan on disk; carrying this session's conversation forward buys nothing and blurs cost attribution between planning and execution.

Everything downstream — `/implement`, `/refactor`, `/auto-review`, `/create-pr` — is the user's to drive.
Both documents stay living through all of it; this skill produces their starting state, never their final one.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
