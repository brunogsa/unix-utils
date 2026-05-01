---
name: brainstorm
description: "Interactively refine an idea into spec.md via Socratic interview. USE when user explicitly says 'let's brainstorm'."
disable-model-invocation: false
---

# Brainstorm

Help the user explore and refine an idea into a structured spec.md.

Spec template and marker conventions live in the companion skill — load it alongside this one:

@~/.claude/skills/spec-driven-development/SKILL.md

## Usage

`/brainstorm [path/to/spec.md]`

Examples:
- `/brainstorm spec.md` -- refine an existing spec the user wrote
- `/brainstorm features/auth-spec.md` -- custom path
- `/brainstorm` -- no file: use session context, check for ./spec.md

## Process

### 1. Gather starting context

**If a file path is provided**: read it and use as the starting point.
**If no file path**: check if `./spec.md` exists and read it.
**If nothing exists**: use the current session context (conversation history, codebase understanding) to seed the brainstorm.

### 2. Probe scope before deep questions

Before drilling into requirements, check whether the request describes multiple independent subsystems (e.g., "platform with chat, file storage, billing, and analytics").
Signals: multiple unrelated nouns, distinct user roles, separate persistence concerns, or features that could each ship independently.

If it looks decomposable, surface it: name the candidate sub-projects, ask the user how they relate and which one ships first. Brainstorm only the first sub-project here — each remaining piece ideally gets its own spec→plan cycle.

**If the user agrees to decompose**: write a brief `scopes.md` next to where the spec will live. One line per sub-project — name, one-sentence purpose, dependency on other sub-projects (if any). Include the one being brainstormed now. Format:

```markdown
## Sub-projects

1. **<name>** — <one-sentence purpose>. Depends on: <none | #N>.

2. **<name>** — <one-sentence purpose>. Depends on: <none | #N>.
```

Why: a stale brainstorm session loses the decomposition map; `scopes.md` survives so the next `/brainstorm` run picks up the queue without re-deriving it. Refining a too-large idea wastes interview rounds on details that belong in separate specs.

### 3. Interview the user

Ask clarifying questions (Socratic style). Focus on:
- What problem are we solving? (Background)
- What is goal and success metrics/KPIs? (Goal)
- Who benefits and how? (User Stories)
- What does success look like? (Testable Acceptance Criteria — BDD scenarios)
- What constraints exist? (Non-Functional and Techincal Requirements)
- What's unclear? (Open Questions)

Ask 2-3 questions per round. Don't overwhelm.

**CRITICAL: For Testable Acceptance Criteria, actively probe for coverage gaps.** Happy-path scenarios are easy to elicit; corner cases and failure modes need pulling. Before generating spec.md, push the user to enumerate:
- **Corner cases**: empty inputs, max sizes/limits, boundary values, combined/composed filters, idempotency, concurrent access.
- **Failure modes**: validation errors (4xx), downstream timeouts, downstream 5xx, partial failures, auth failures, rate limits.

If the user only describes the happy path, ask explicitly: "what should happen when X is empty / oversized / invalid / unavailable?" The spec template requires happy + corner + failure coverage.

### 4. Propose 2-3 approaches with trade-offs

Once requirements feel solid, present 2-3 viable approaches conversationally. Lead with your recommendation and the reasoning. Cover the trade-off axes that matter for this idea (complexity, blast radius, reversibility, dependencies, time-to-first-value).

Get a directional pick from the user before writing the spec. Capture the outcome in the spec's Decisions section as one marker with discarded alternatives as sub-bullets.

Why include discarded options at all: the next session (or reviewer) will re-derive the same alternatives unless the rationale is preserved. Naming what lost — and why — prevents re-litigation and surfaces when a trade-off has shifted (e.g., the constraint that killed alt-2 no longer applies).

### 5. Generate/update spec.md

Write to the provided file path, or `./spec.md` by default, populating the spec template.

If the file already exists, update it in place (preserve user content, fill gaps, restructure into the template).

### 6. Present for review

Show the spec summary. Ask if anything is missing or wrong.
Iterate until the user is satisfied.
