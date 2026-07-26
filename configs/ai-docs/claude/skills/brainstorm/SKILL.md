---
name: brainstorm
description: "Refine an idea into an approved spec_<slug>.md + plan_<slug>.md via Socratic interview, then self-review and hand off to /implement. USE when the user says 'let's brainstorm', or when planning a non-trivial feature or breaking work into commits."
disable-model-invocation: false
---

# Brainstorm

Help the user explore and refine an idea into a structured `spec_<slug>.md`, then into a self-reviewed `plan_<slug>.md` ready to hand off.

This skill owns the whole procedure end to end.
The document conventions it writes against — naming, templates, guidelines, and the self-review gates — live in the `spec-driven-development` library, read at the two points that need it:

- **Step 5 (write the spec)**: read `~/.claude/skills/spec-driven-development/SKILL.md` for its Guidelines, plus its `assets/spec-template.md` for the section structure.
- **Step 8 (self-review)**: read `~/.claude/skills/spec-driven-development/references/self-review-checks.md`.

Read that library by path — never via the Skill tool. It sets `disable-model-invocation: true`, so it is absent from the skill listing and cannot be invoked.

Why not read it upfront: steps 1-4 are pure interview and need none of it, and that is the phase that burns the most context before any document exists.

## Usage

`/brainstorm [path/to/spec_<slug>.md]`

Examples:
- `/brainstorm spec_auth.md` -- refine an existing spec the user wrote
- `/brainstorm features/spec_auth.md` -- custom path
- `/brainstorm` -- no file: use session context; discover existing `spec_*.md` (see step 1)

## Process

### 1. Gather starting context

**If a file path is provided**: read it and use as the starting point.
**If no file path**: glob `spec_*.md` in CWD (top-level). One match → read it. Multiple → list them numbered and ask which to refine. Zero → treat as a fresh idea.
**If nothing exists**: use the current session context (conversation history, codebase understanding) to seed the brainstorm.

### 2. Probe scope before deep questions

Before drilling into requirements, check whether the request describes multiple independent subsystems (e.g., "platform with chat, file storage, billing, and analytics").
Signals: multiple unrelated nouns, distinct user roles, separate persistence concerns, or features that could each ship independently.

If it looks decomposable, surface it.

- Name the candidate sub-projects, ask the user how they relate and which one ships first.
- Brainstorm only the first sub-project here — each remaining piece ideally gets its own spec→plan cycle.
- If the user declines, brainstorm the whole original idea instead — no implicit narrowing to a first sub-project.

**If the user agrees to decompose**: write a brief `scopes.md` next to where the spec will live.

- One line per sub-project — name, one-sentence purpose, dependency on other sub-projects (if any).
- Include the one being brainstormed now. Format:

```markdown
## Sub-projects

1. **<name>** — <one-sentence purpose>. Depends on: <none | #N>.

2. **<name>** — <one-sentence purpose>. Depends on: <none | #N>.
```

Why:

- A stale brainstorm session loses the decomposition map.
- `scopes.md` survives so the next `/brainstorm` run picks up the queue without re-deriving it.
- Refining a too-large idea wastes interview rounds on details that belong in separate specs.

### 3. Interview the user

**Open with two yes/no rigor toggles**, in one message, before the first Socratic round:

- **"Every line traces to an AC?"** — should self-review block on machinery that maps to no acceptance criterion?
- **"Right-sized plan?"** — should a fresh reviewer judge the plan against the original request for gold-plating?

Persist both answers immediately to `/tmp/sdd_<session_id>.json` — one brainstorm run per session, so the session id alone keys the file.
Answer them fresh each run: never reuse a previous run's answers, and never write them into `plan_<slug>.md` or any committed file.

Why upfront: both toggles gate how strictly step 8 checks the plan, so deciding rigor before the plan exists closes off tuning it down after seeing what was produced.
Why persisted: a compaction between here and step 8 would otherwise lose them, and step 8 must read the file — never re-ask.

At interview start, create `/tmp/brainstorm_<session_id>.md` — one brainstorm per session, so the session id alone keys the file.
Persist each decision with its why, each discarded alternative with why it lost, and open questions — as they happen, not at the end.
Why: a compaction mid-interview drops session memory entirely; the file survives, so you re-read it instead of re-deriving what was lost.
On resume or after a compaction, re-read this file first and trust it over recalled context.

Ask clarifying questions (Socratic style). Focus on:
- What problem are we solving? (Background)
- What is goal and success metrics/KPIs? (Goal)
- Who benefits and how? (User Stories)
- What does success look like? (Testable Acceptance Criteria — BDD scenarios)
- What constraints exist? (Non-Functional and Technical Requirements)
- What's unclear? (Open Questions)

Ask 2-3 questions per round. Don't overwhelm.

**Prefer the AskUserQuestion tool for each round** — options with your recommended answer first — over free-text chat questions; fall back to chat only when a question can't be shaped into options.

Other procedural skills ask everything up front. This one is the deliberate exception: the interview IS the skill, and each round depends on the previous answer.

**Split facts from decisions before asking.** Anything discoverable from the codebase, session context, or a web search is legwork — look it up yourself, never ask it.
Questions to the user are reserved for genuine decisions: preferences, priorities, and context only they hold.

**Attach your recommended answer to every question**, with one line of reasoning.

Why: a look-up-able fact wastes an interview round on work the agent can do; a recommendation turns each remaining question from an essay prompt into a confirm-or-override.

**CRITICAL: For Testable Acceptance Criteria, actively probe for coverage gaps.** Happy-path scenarios are easy to elicit; corner cases and failure modes need pulling.

Before generating the spec, always push the user through every category in the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`). Illustrative probes:

- **Corner cases** (e.g.): empty inputs, max sizes/limits, boundary values.
- **Failure modes** (e.g.): downstream timeouts, partial failures, rate limits.

If the user only describes the happy path, ask explicitly: "what should happen when X is empty / oversized / invalid / unavailable?"

The spec template requires happy + corner + failure coverage.

**Exit criterion**: end interview rounds once the latest round adds no new requirement or constraint changes, and every coverage-taxonomy category is covered or explicitly ruled out.

### 4. Propose 2-3 approaches with trade-offs

Once the step 3 exit criterion is met, present 2-3 viable approaches conversationally.
Lead with your recommendation and the reasoning. Cover the trade-off axes that matter for this idea (complexity, blast radius, reversibility, dependencies, time-to-first-value).

Get a directional pick from the user before writing the spec. Capture the outcome in the spec's Decisions section as one marker with discarded alternatives as sub-bullets.

Why include discarded options at all:

- The next session (or reviewer) will re-derive the same alternatives unless the rationale is preserved.
- Naming what lost — and why — prevents re-litigation.
- It surfaces when a trade-off has shifted (e.g., the constraint that killed alt-2 no longer applies).

### 5. Generate/update the spec

**Read `~/.claude/skills/spec-driven-development/SKILL.md` now**, plus its `assets/spec-template.md`.
That library's Guidelines govern what you write: English regardless of the conversation's language, lean over exhaustive, and no `AC-N` cross-references.

Write to the provided/discovered file path. For a fresh idea, name a new spec file:

- Derive a short kebab-case `<slug>` from the feature and confirm it with the user.
- Write `spec_<slug>.md` in CWD. The plan later inherits that same slug — the shared slug is what pairs the two, so several in-flight features can coexist in one directory.

If the file already exists, update it in place (preserve user content, fill gaps, restructure into the template).

Fold the scratchpad's decisions and discarded alternatives into the spec's Decisions section, then discard the scratchpad — the spec is now the durable artifact.

### 6. Present for review

Show the spec summary. Ask if anything is missing or wrong.
Route rework to the earliest step the feedback invalidates:

- Wording/detail issues → re-present this spec.
- Missing or wrong requirements → back to the step 3 interview.
- Approach concerns → back to the step 4 trade-off discussion.

Iterate until the user is satisfied.

### 7. Dispatch `plan-writer` to generate the plan

Once the spec is approved, dispatch `agent(subAgent=plan-writer, title=Write implementation plan from spec)` to write `plan_<slug>.md` from the spec alone.

Run it in the foreground (not backgrounded) — the next step depends on its result.

Pass it:
- The spec file's absolute path.
- The plan output path: `plan_<slug>.md` in CWD, same slug as the spec.
- Any planning-conventions file the user named (ADR/HLD/LLD), if one exists.

**If it returns a numbered list of gaps** instead of a plan: the spec is missing information the plan needs.
Walk and close every reported gap with the user first, updating `spec_<slug>.md`, then re-dispatch `plan-writer` once — not once per gap.
Never fill a gap yourself with an invented decision — that's exactly the author-bias this dispatch exists to catch.

Why fresh context: this session already talked itself into the spec's choices during the interview.
A planner that sees only the spec file — never the interview — tests whether the spec actually carries what a plan needs.
It does this instead of quietly drawing on session memory the next reader won't have.

### 8. Run self-review, then hand off with `/clear`

`plan-writer` never reviews its own output, so nothing upstream has checked the plan yet — this session runs every gate.

**Read `~/.claude/skills/spec-driven-development/references/self-review-checks.md` now.**
The library SKILL.md read at step 5 carries the seven-check table this reference expands on.

Run the gates in this order:

1. **Qualitative pass** — dispatch `deep-reviewer`, then `mermaid-fixer`, then `density-fixer`, serially, per that reference's detail.
2. **The seven formal checks, in sequence** — the five always-on ones, plus the two toggles read from `/tmp/sdd_<session_id>.json`. Never re-ask a toggle here.

On a blocking failure, follow that library's iteration-and-drift loops: fix the issue, then snapshot both docs to `/tmp/sdd-snapshots/` for the user's annotated-diff review.
Once the user approves that snapshot, re-run only the failed check plus a delta-scoped re-review of what changed — never the whole seven-check block from the top.

Once every blocking check passes, tell the user to run `/clear`, then invoke `/implement`. Don't run `/implement` in this session.

Why: `/implement` re-grounds entirely from `spec_<slug>.md` and `plan_<slug>.md` on disk; carrying this session's conversation forward buys nothing and blurs cost attribution between planning and execution.

What follows is the user's to drive, not this skill's: `/implement`, then `/refactor` and `/auto-review` once the feature is whole.
Then a manual code read, then `/create-pr` (which reads both docs for a rich description), then `/improve-from-user` and `english-coach`.
Both documents stay living through all of it — this skill produces their starting state, never their final one.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
