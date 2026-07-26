---
name: brainstorm
description: "Refine an idea into an approved spec_<slug>.md + plan_<slug>.md via Socratic interview, then self-review and hand off to /implement. USE when the user says 'let's brainstorm', or when planning a non-trivial feature or breaking work into commits."
disable-model-invocation: false
---

# Brainstorm

Help the user explore and refine an idea into a structured `spec_<slug>.md`, then into a self-reviewed `plan_<slug>.md` ready to hand off.

This skill owns the whole procedure end to end.
The document conventions it writes against — naming, templates, guidelines, self-review gates — live in the `spec-driven-development` library, read at exactly two points:

- **Step 6 (write the spec)**: the dispatched `fork` reads that library's `SKILL.md` plus its `assets/spec-template.md`. This session reads neither.
- **Step 10 (self-review)**: this session reads its `references/self-review-checks.md`.

Read that library by path — never via the Skill tool; its `disable-model-invocation: true` keeps it out of the skill listing entirely.

Why not read it upfront: steps 1-5 are pure interview and need none of it, and that is the phase that burns the most context before any document exists.

## Usage

`/brainstorm [path/to/spec_<slug>.md]`

Examples:
- `/brainstorm spec_auth.md` -- refine an existing spec, at any path the user gives
- `/brainstorm` -- no file: use session context; discover existing `spec_*.md` (see step 2)

## Process

**Before step 1 runs**, seed the TaskList with one `[Reminder]` per step below, in order, and update each as it completes.

Why: the TaskList survives compaction, so one entry per step keeps a step that would otherwise vanish with the summary visible as pending.

### 1. Pre-flight — settle the run's toggles and open its state

**Ask all three yes/no toggles in one message, before any other question:**

- **"Every line traces to an AC?"** — should self-review block on machinery that maps to no acceptance criterion?
- **"Right-sized plan?"** — should a fresh reviewer judge the plan against the original request for gold-plating?
- **"Fresh-eyes self-review?"** — should a `deep-reviewer` subagent read the spec (step 7) and the plan (step 10) before you do? Default yes; a no skips both.

Persist all three answers immediately to `/tmp/sdd_<session_id>.json` — one brainstorm run per session, so the session id alone keys the file.
Answer them fresh each run: never reuse a previous run's answers, and never write them into `spec_<slug>.md`, `plan_<slug>.md`, or any committed file.

Why upfront: all three gate how strictly later steps check the documents, so settling rigor before any document exists closes off tuning it down after seeing what was produced.
Why persisted: a compaction between here and self-review would lose them, so those steps read the file instead of re-asking.

Then create the run scratchpad `/tmp/brainstorm_<session_id>.md`, keyed the same way.

- Persist each decision with its why, each discarded alternative with why it lost, and open questions.
- Write as things happen, never at the end.
- It stays alive for the whole run — through the spec, the plan, and self-review — so the plan phase can still see why the spec reads the way it does.
- On resume or after a compaction, re-read it first and trust it over recalled context — compaction drops session memory, the file survives.

### 2. Gather starting context

**If a file path is provided**: read it and use as the starting point.
**If no file path**: glob `spec_*.md` in CWD (top-level). One match → read it. Multiple → list them numbered and ask which to refine.
**Zero matches**: seed the brainstorm from session context — conversation history plus codebase understanding.

### 3. Probe scope before deep questions

Before drilling into requirements, check whether the request describes multiple independent subsystems.
Signals: multiple unrelated nouns, distinct user roles, separate persistence concerns, or features that could each ship independently.

If it looks decomposable, surface it:

- Name the candidate sub-projects, ask the user how they relate and which one ships first.
- Brainstorm only the first sub-project here — each remaining piece ideally gets its own spec→plan cycle.
- If the user declines, brainstorm the whole original idea instead — no implicit narrowing to a first sub-project.

**If the user agrees to decompose**: write a brief `scopes.md` next to where the spec will live.

- Under a `## Sub-projects` heading, one numbered line each, including the one being brainstormed now.
- Format: `1. **<name>** — <one-sentence purpose>. Depends on: <none | #N>.`

Why: a stale session loses the decomposition map, but `scopes.md` survives — so the next `/brainstorm` run picks up the queue instead of re-deriving the split.

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

Get a directional pick from the user before writing the spec. Capture the outcome in the spec's Decisions section as one marker with discarded alternatives as sub-bullets.

Why keep the discarded ones: naming what lost, and why, stops the next session re-deriving the same alternatives and re-litigating them.
It also surfaces when the constraint that killed an alternative no longer applies.

### 6. Dispatch a `fork` to write the spec

For a fresh idea, derive a short kebab-case `<slug>` from the feature yourself — never ask the user to confirm it.
The plan later inherits that same slug — the shared slug is what pairs the two.

Why not confirm: the slug only names two files that always travel together, so a wrong one costs a rename, and the user is about to read the spec anyway.

Then dispatch `agent(subAgent=fork, title=Write spec_<slug>.md)`, in the foreground — the next step needs the spec to exist. Instruct it to:

- Read `~/.claude/skills/spec-driven-development/SKILL.md` and its `assets/spec-template.md`. That library's Guidelines govern what it writes — English regardless of the conversation's language, lean over exhaustive.
- Read the run scratchpad `/tmp/brainstorm_<session_id>.md` and fold its decisions and discarded alternatives into the spec's Decisions section.
- Write to the provided/discovered path, or for a fresh idea to `spec_<slug>.md` in CWD.
- If the file already exists, update it in place — preserve user content, fill gaps, restructure into the template.
- Report back the resolved spec path plus a short summary of what it wrote.

**This session never writes the spec itself** — every later edit goes through another `agent(subAgent=fork, title=Apply spec edits)` carrying the exact changes to make.

Why delegate: writing the spec costs whatever context loads the library and the template, and this session's is the one that must still survive both reviews and the plan hand-off.

Why a fork: it inherits this session's full context, so it already carries the interview and the approach pick.
A fresh agent would silently invent whatever a re-serialized prompt left out.

### 7. Self-review the spec with fresh eyes

**Skip this step when the pre-flight's self-review toggle is off** — read it back from `/tmp/sdd_<session_id>.json`, never re-ask.

Otherwise dispatch `agent(subAgent=deep-reviewer, title=Fresh-eyes review of spec)`, in the foreground, pointed at the spec file alone.

Tell it to read the Qualitative pass section of `~/.claude/skills/spec-driven-development/references/self-review-checks.md` and apply these items only: placeholders, contradictions, ambiguity, completeness, human-reviewable.

Exclude PR-size and plan-contradiction — no plan exists yet.
Exclude Scope too: step 3 already asked the user about decomposition, and step 10's qualitative pass judges it again over both documents.

Then dispatch `agent(subAgent=fork, title=Apply spec review findings)` to apply every blocking finding.

**Run this review exactly once — never a second round.**
The user reads the spec next and is the stronger judge of it.

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

Once the spec is approved, dispatch `agent(subAgent=plan-writer, title=Write implementation plan from spec)` in the foreground, to write `plan_<slug>.md` from the spec alone.

Pass it:
- The spec file's absolute path.
- The plan output path: `plan_<slug>.md` in CWD, same slug as the spec.
- Any planning-conventions file the user named (ADR/HLD/LLD), if one exists.

**A gap in the spec never withholds the plan.**
Where the spec doesn't carry a decision the plan needs, `plan-writer` writes the plan around it and records it as a `**QUESTION:**` entry under the plan's Open Questions.

Never close such a gap here, and never fill one yourself with an invented decision — that's exactly the author-bias this dispatch exists to catch.
Both documents may therefore reach step 10 with Open Questions still open; step 10.2 is where they all close, in one batch.

Why batch them there: a gap-by-gap walkthrough stops the run once per item.
One pass at step 10.2 lets the user answer every question against a finished plan, where what each one actually decides is visible.

Should it return a numbered gap list anyway instead of a plan, dispatch a `fork` to record those gaps as Open Questions in `spec_<slug>.md`.
Then re-dispatch `plan-writer` once — not once per gap.

Why fresh context: this session already talked itself into the spec's choices during the interview.
A planner that sees only the spec file tests whether the spec carries what a plan needs, rather than drawing on session memory the next reader won't have.

### 10. Run self-review, then hand off with `/clear`

`plan-writer` never reviews its own output, so nothing upstream has checked the plan yet — this session runs every gate.

**Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now** — it defines every gate below.

Sort those gates into two buckets first, because every rule in this step turns on which bucket a gate is in:

- **Deterministic** — a script or renderer returns the verdict, and re-running one costs nothing: the mermaid and density artifact fixers, `check-ac-coverage.sh`, `check-test-distribution.sh`, `check-pr-dag.sh`, `check-tasks-dag.sh`.
- **Non-deterministic** — a `deep-reviewer` judges: the qualitative pass, the semantic half of AC-to-test coverage, "how would this break?", and the two toggled checks.

Why the split governs everything here: a deterministic gate is free to re-run and catches structural breakage, while each non-deterministic round costs a dispatch over both documents whole.
So the deterministic ones run first and as often as needed, and the non-deterministic ones run as few times as the user will accept.

#### 10.1 Run the deterministic gates

Run them serially in this order: `mermaid-fixer`, then `density-fixer`, then the four scripts.
Fix each failure, then re-run that gate alone until it passes.

The fixers lead because repairing a diagram adds lines the density cap must then measure.
This step runs them before the qualitative pass, which is the reverse of the order that reference states.
The reference sequences one pass over both buckets, while this step runs the cheap bucket to exhaustion first.

#### 10.2 Close every Open Question before anything expensive runs

Read the Open Questions section of both `spec_<slug>.md` and `plan_<slug>.md`.

While either still holds a `**QUESTION:**` entry, interview the user to settle them — `AskUserQuestion`, 2-3 at a time, recommended answer first, exactly as in step 4.
Then dispatch `agent(subAgent=fork, title=Close open questions)` to fold the answers into both documents and leave each Open Questions section reading `None`.

Re-read both sections after each round. **Nothing below runs while a question is open.**

Why gate here: every non-deterministic gate reads both documents whole, so running one over an unanswered question spends a dispatch reviewing a document that is about to change.

#### 10.3 Run the non-deterministic gates once

Dispatch them serially, per that reference — the qualitative pass first, then the remaining judged checks, including the two toggles read from `/tmp/sdd_<session_id>.json`. Never re-ask a toggle here.
Skip only the qualitative-pass dispatch when the pre-flight's self-review toggle is off, and say so in the output.

#### 10.4 Loop on any blocking finding

1. **Interview the user to resolve it** — never invent the resolution, and never resolve it silently.
2. **Dispatch `agent(subAgent=fork, title=Apply self-review findings)`** to apply what the user decided to the spec, the plan, or both.
3. **Re-run the deterministic gates only** — the fork's edits can break a DAG or an AC-coverage citation, and those are free to re-check.
4. **Ask the user whether to re-run the non-deterministic gates.** A yes returns to 10.3; a no ends the loop and accepts the documents as they stand.

Repeat until nothing blocks or the user declines another round.

Then tell the user to run `/clear`, then invoke `/implement`. Don't run `/implement` in this session.

Why: `/implement` re-grounds entirely from `spec_<slug>.md` and `plan_<slug>.md` on disk; carrying this session's conversation forward buys nothing and blurs cost attribution between planning and execution.

Everything downstream — `/implement`, `/refactor`, `/auto-review`, `/create-pr` — is the user's to drive.
Both documents stay living through all of it; this skill produces their starting state, never their final one.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
