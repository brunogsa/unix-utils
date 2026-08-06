---
name: brainstorm
description: "Refine an idea into an approved plan_<slug>.md — plus a spec_<slug>.md at full mode — via Socratic interview, then self-review and /implement. USE when the user says 'let's brainstorm', or when planning a feature or breaking work into commits."
disable-model-invocation: false
# Trim hierarchy exhausted at 3066 words. Every step below fires on every run, so nothing earns
# a lazy load; the spec and plan phases co-fire at `full` by contract, so splitting them would
# make two files that always load together. The two modes share every step but four, so a
# per-mode split would duplicate ten steps. Override is the only honest option left.
words-budget: 4096
---

# Brainstorm

Help the user explore and refine an idea into a self-reviewed plan ready to hand off, preceded by a spec when the run is `full`.

This skill owns the whole procedure end to end.
The document conventions it writes against — naming, templates, guidelines, self-review gates — live in the `spec-driven-development` library.

Read that library by path — never via the Skill tool; its `disable-model-invocation: true` keeps it out of the skill listing entirely.

**Only step 13 reads it into this session's context.** Every other read happens inside a dispatched agent, and each step below names what its agent reads.

Why nothing loads upfront: steps 1-5 are pure interview and need none of it, and that is the phase that burns the most context before any document exists.

## Usage

`/brainstorm` — no arguments.

A run always starts from an idea, never from a document, so there is no path to resolve and no prior spec or plan to reconcile.

## Modes

Step 1 settles one of two. Every step below reads it back from `/tmp/sdd_<session_id>.json` and never re-asks:

- **`full`** (default) — writes `spec_<slug>.md` and `plan_<slug>.md`, and runs the AI self-reviews plus the deterministic gates.

- **`light`** — writes `plan_<slug>.md` alone, and runs the deterministic gates only.
  - `light` is `full` minus the spec, minus the AI gates. The plan uses the same template and the same sections either way.
  - Why it exists: a plan alone is enough for `/implement`, `/quality-gate` and `/create-pr` to run, so a small change can skip the second document without losing the machinery.

## Process

**Once step 1 settles the mode**, seed the TaskList with one `[Reminder]` per remaining step, in order, and update each as it completes.

Seed the step 7 and step 10 review reminders only at `full` with the self-review toggle on — a reminder no run can complete is one that stalls the list.

### 1. Pre-flight — settle the mode, then its toggles

**Phase 1, one `AskUserQuestion` call, before any other question**: "How much do you want written?" — `full` or `light`, per the Modes section above.

**Phase 2 runs only when the answer is `full`** — three toggles, all in one further `AskUserQuestion` call:

- **"Every line traces to an AC?"** — should self-review block on machinery that maps to no acceptance criterion?
- **"Right-sized plan?"** — should a fresh reviewer judge the plan against the original request for gold-plating?
- **"Fresh-eyes self-review?"** — should a `deep-reviewer` subagent read the spec (step 7) and the plan (step 10) before you do? Default yes; a no skips both.

At `light`, skip phase 2 entirely and treat all three as off.
Each one gates an AI review, and `light` runs none — so asking would spend a round-trip on three dead questions.

Persist the answers immediately to `/tmp/sdd_<session_id>.json` — one brainstorm run per session, so the session id alone keys the file.
The mode is the `mode` field, valued exactly `full` or `light`.
Answer them fresh each run: never reuse a previous run's answers, and never write any of them into the spec, the plan, or any committed file.

Why upfront: the mode decides whether a spec exists, and the toggles decide how strictly later steps check what gets written.
Settling both before anything is written closes off tuning either down after seeing the output.
Why persisted: a compaction between here and self-review would lose them.

Then create the run scratchpad `/tmp/brainstorm_<session_id>.md`, keyed the same way, per CLAUDE.md's scratchpad rules.
It stays alive for the whole run — through the spec, the plan, and self-review — so the plan phase can still see why the earlier steps decided what they did.
It is also the sole context channel to every dispatched writing agent — each one starts with none of this session's context.
Anything this file omits is invisible to the agent that writes the documents.

### 2. Gather starting context

Seed the brainstorm from session context — conversation history plus codebase understanding.

Read what the request touches in the codebase before asking anything: the files it changes, the modules it neighbours, the conventions it must match.

Why read first: everything discoverable there is legwork, and step 4 spends its rounds only on what the codebase can't answer.

### 3. Probe scope before deep questions

Before drilling into requirements, check whether the request describes multiple independent subsystems.
Signals: multiple unrelated nouns, distinct user roles, separate persistence concerns, or features that could each ship independently.

If it looks decomposable, follow [`references/decompose-scope.md`](references/decompose-scope.md) to surface it and handle the user's answer.

### 4. Interview the user

**Read the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`) before the first round.**

Why up front: its categories then shape every question you ask, instead of becoming a checklist swept at the end.
By then the requirements are settled, so a boundary raised that late reopens answered questions rather than refining them.

Write every answer that shapes the documents into the run scratchpad as the round closes, per step 1 — decisions with their why, alternatives with why they lost.

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

Push the user through every category of the taxonomy read at the top of this step — all of them, before any document is written. Illustrative probes:

- **Corner cases** (e.g.): empty inputs, max sizes/limits, boundary values.
- **Failure modes** (e.g.): downstream timeouts, partial failures, rate limits.

If the user only describes the happy path, ask explicitly: "what should happen when X is empty / oversized / invalid / unavailable?"

**Close every question this step raises, here.** Carry none forward as an Open Question — a question the interview could have settled costs a whole extra round at step 12.

Questions that surface later, while writing the documents, are expected and fine; step 12 exists for exactly those.

**Exit criterion**: end interview rounds once the latest round adds no new requirement or constraint changes, every coverage-taxonomy category is covered or explicitly ruled out, and nothing raised is still open.

### 5. Propose 2-3 approaches with trade-offs

Present 2-3 viable approaches conversationally.
Lead with your recommendation and the reasoning. Cover the trade-off axes that matter for this idea (complexity, blast radius, reversibility, dependencies, time-to-first-value).

Get a directional pick from the user before writing anything.
Capture the outcome in the run scratchpad; the writing agent folds it into the document's Decisions section as one marker, with the discarded alternatives as sub-bullets.

Why keep the discarded ones: naming what lost, and why, stops the next session re-deriving the same alternatives and re-litigating them.
It also surfaces when the constraint that killed an alternative no longer applies.

### 6. Derive the slug, then dispatch a `general-purpose` agent to write the spec

**Full only.** At `light` skip to step 9, which derives its own slug.

Derive a short kebab-case `<slug>` from the feature yourself — never ask the user to confirm it.
The plan inherits that same slug at step 9 — the shared slug is what pairs the two files.

Why not confirm: the slug just names two paired files — a wrong one costs only a rename, and the user is about to read the spec anyway.

Then dispatch `agent(subAgent=general-purpose, model=sonnet, title=Write the spec)`, in the foreground — the next step needs the spec to exist. Instruct it to:

- Read `~/.claude/skills/spec-driven-development/SKILL.md` and its `assets/spec-template.md` — that library's Guidelines govern what it writes, and every section of the template gets written.

- It has no inherited context — read the run scratchpad `/tmp/brainstorm_<session_id>.md` first.
- Fold the scratchpad's decisions and discarded alternatives into the spec's Functional Decisions section.
- Write `spec_<slug>.md` in CWD, and report back its resolved path plus a short summary of what it wrote.

**This session never writes the spec itself** — every later edit goes through another `agent(subAgent=general-purpose, model=sonnet, title=Apply spec edits)` carrying the exact changes to make.

Why delegate: writing the spec costs the context to load the library and template — context this session still needs for both reviews and the hand-off.

Why `general-purpose`: this agent inherits none of this session's context, unlike a fork, so it cannot lean on the interview or the approach pick.
It must ground entirely from the run scratchpad `/tmp/brainstorm_<session_id>.md` instead.
That is why the scratchpad has to be self-contained: the verbatim original request, every finding with its file:line evidence, and every decision with the alternatives it discarded.
Leaving any of that out of the scratchpad makes it invisible to the agent that writes the spec, which would otherwise silently invent whatever is missing.

### 7. Self-review the spec once, with fresh eyes

**Full only, and only when the pre-flight's self-review toggle is on** — read it back from `/tmp/sdd_<session_id>.json`, never re-ask.

Dispatch `agent(subAgent=deep-reviewer, title=Fresh-eyes review of spec)`, in the foreground, pointed at the spec file alone.

Tell it to read the Qualitative pass section of `~/.claude/skills/spec-driven-development/references/self-review-checks.md` and apply these items only: placeholders, contradictions, ambiguity, completeness, human-reviewable.

**Make acceptance-criteria gaps its first job** — an AC whose `Then` isn't independently checkable, a happy path with no matching corner case or failure mode, an uninstantiated boundary or failure-category checklist row.

Why that emphasis: the Testable Acceptance Criteria section is the only part of the spec a downstream script parses.
A gap there passes every later gate untouched, and reaches implementation as a test nobody wrote.

Exclude PR-size and plan-contradiction — no plan exists yet.
Exclude Scope too: step 3 already asked the user about decomposition.

Then decide each finding yourself and dispatch `agent(subAgent=general-purpose, model=sonnet, title=Apply spec review findings)` with the ones you accept.

**Report the outcome to the user in one block before step 8** — each finding, and whether it was applied or skipped with the reason.

Why report it: this summary is the only way to judge whether the gate earns its cost.
In the finished spec, a silently-applied fix and a gate that found nothing read identically.

**Runs once per spec, never twice over the same text.** The step 8 loop re-runs no review; from there the user reading the spec is the stronger judge.

Why fresh eyes before the user: this session argued itself into every choice, so it reads its own spec as complete because it remembers what the spec never says.

Why not `general-purpose` for the review: it composes under conventions the way the spec-writing dispatch does, not the fresh-eyes judgment a review needs — that judgment is `deep-reviewer`'s job.

### 8. User review/approve spec

**Full only.**

Give the user the spec's path, then ask via `AskUserQuestion` whether it is approved or what to change.

**This is a loop, not a stop.** Each round applies the feedback and asks again; the moment they approve, continue to step 9 automatically without a further confirmation.

Route each round's rework to the earliest step the feedback invalidates:

- Wording/detail issues → re-dispatch the `general-purpose` agent with the edits, then re-ask.
- Missing or wrong requirements → back to the step 4 interview.
- Approach concerns → back to the step 5 trade-off discussion.

Why a loop: approval is rarely one round, and a step that ends the run on "not yet" makes the user re-invoke the skill to say what they meant.

### 9. Write the plan

**At `full`** — dispatch `agent(subAgent=plan-writer, title=Write implementation plan from spec)` in the foreground, to write the plan from the spec alone. Pass it:

- The spec file's absolute path, plus the slug derived in step 6.
- Any planning-conventions file the user named (ADR/HLD/LLD), if one exists.

`plan-writer` resolves the output path itself from the slug — it reads the library that defines how a plan is named, so this session never spells that name out.

Why fresh context: this session already talked itself into the spec's choices.
A planner seeing only the spec file tests whether it carries what a plan needs, rather than leaning on session memory the next reader won't have.

**A gap in the spec never withholds the plan.**
Where the spec doesn't carry a decision the plan needs, `plan-writer` writes the plan around it and records it as a `**QUESTION:**` entry under the plan's Open Questions.

Never close a gap here, or fill one with an invented decision — that's the author-bias this dispatch exists to catch. Step 12 closes them all, in one batch.

Should it return a numbered gap list instead of a plan, dispatch `agent(subAgent=general-purpose, model=sonnet, title=Record plan gaps as spec Open Questions)` to record those gaps as Open Questions in the spec.
Then re-dispatch `plan-writer` once — not once per gap.

**At `light`** — dispatch `agent(subAgent=general-purpose, model=sonnet, title=Write the plan)` in the foreground instead. Instruct it to:

- Read `~/.claude/skills/spec-driven-development/SKILL.md` and its `assets/plan-template.md`, and write every section of that template.

- Derive a short kebab-case `<slug>` from the feature itself, and write `plan_<slug>.md` in CWD.

- Write `N/A — plan-only run` on the `Spec:` line, and carry each task's acceptance criteria in that task's own `**Testable Acceptance criteria**` field.

- Write `N/A — no spec` in place of the Test Design section's AC → test coverage list.
  - Why: `check-ac-coverage.sh` takes a plan and a spec, so with no spec there is nothing for that list to cite and no gate to read it.

- It has no inherited context — read the run scratchpad `/tmp/brainstorm_<session_id>.md` first, then fold its decisions and discarded alternatives into the plan's Technical Decisions section.

Why `general-purpose` rather than `plan-writer` here: `plan-writer` reads a spec and nothing else, by contract, so with no spec it returns a plan of nothing but open questions.
Its fresh-eyes value is testing whether the spec carries what a plan needs — a test with no subject at `light`, where the interview is the only place the requirements live.

### 10. Self-review the plan once, with fresh eyes

**Full only, and only when the pre-flight's self-review toggle is on** — read it back from `/tmp/sdd_<session_id>.json`, never re-ask.

Dispatch `agent(subAgent=deep-reviewer, title=Fresh-eyes review of plan)`, in the foreground, pointed at the plan and the spec.

**Make test-design gaps its first job** — a planned test title asserting nothing checkable, a thin scenario class, or an AC with no covering test.
A task whose `**Tests (planned)**` list is empty without saying why counts too.

Why that emphasis: `tdd-coder` builds each RED cycle straight from these titles, so a title that never got designed is a behavior that never gets a test.

Also apply the qualitative pass from that same reference, plus the two rigor toggles read back from `/tmp/sdd_<session_id>.json` — never re-asked here.

Then decide each finding yourself, dispatch `agent(subAgent=general-purpose, model=sonnet, title=Apply plan review findings)` with the ones you accept, and report applied-or-skipped to the user exactly as step 7 does.

**Runs once per plan, never twice over the same text.**

### 11. User review/approve plan

Give the user the plan's path, then ask via `AskUserQuestion` whether it is approved or what to change.

Same loop shape as step 8: apply, re-ask, and continue to step 12 automatically the moment they approve.
Route rework the same way — plan-level edits go through a `general-purpose` agent (`model=sonnet`), requirement gaps back to step 4, approach concerns back to step 5.

**No self-review re-runs during this loop, in either mode.**

Why: step 10 already read the plan with fresh eyes, and from here the user is the judge.
A second AI pass over text they are actively editing spends a dispatch on a moving target.

### 12. Close every Open Question

Read the Open Questions section of the plan, and of the spec when one exists.

While either still holds a `**QUESTION:**` entry, interview the user to settle them — `AskUserQuestion`, 2-3 at a time, recommended answer first, exactly as in step 4.
Then dispatch `agent(subAgent=general-purpose, model=sonnet, title=Close open questions)` to fold the answers in and leave each Open Questions section reading `None`.

Re-read after each round. **Step 13 does not run while a question is open.**

Why after approval rather than during: one pass here lets the user decide every question against a finished plan, where a gap-by-gap walkthrough would stop the run once per item.

### 13. Run the deterministic gates

**Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now** — it defines every gate, sorts them into a deterministic and a judged bucket, and gives each bucket's dispatch tier.

Run the whole deterministic bucket to exhaustion, in the order the reference gives — fix each failure, then re-run that gate alone until it passes.

**Skip `check-ac-coverage.sh` at `light`**: it takes a plan and a spec, and no spec exists.

**Run no judged gate here, in either mode.** Steps 7 and 10 already ran them once each, and the user has approved every document since.

Why the deterministic bucket still runs: step 12 rewrote text, which can break a task DAG or an AC-coverage citation — and re-checking that costs nothing but a script run.

### 14. Hand off with `/clear`

Tell the user to run `/clear`, then invoke `/implement`. Don't run `/implement` in this session.

Why: `/implement` re-grounds entirely from the documents on disk; carrying this session's conversation forward buys nothing and blurs cost attribution between planning and execution.

Everything downstream — `/implement`, `/refactor`, `/auto-review`, `/create-pr` — is the user's to drive.
Every document written here stays living through all of it; this skill produces their starting state, never their final one.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
