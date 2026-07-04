---
name: brainstorm
description: "Interactively refine an idea into a spec_<slug>.md via Socratic interview. USE when user explicitly says 'let's brainstorm'."
disable-model-invocation: false
---

# Brainstorm

Help the user explore and refine an idea into a structured `spec_<slug>.md`.

Spec template and marker conventions live in the companion skill — load it alongside this one:

@~/.claude/skills/spec-driven-development/SKILL.md

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

Ask clarifying questions (Socratic style). Focus on:
- What problem are we solving? (Background)
- What is goal and success metrics/KPIs? (Goal)
- Who benefits and how? (User Stories)
- What does success look like? (Testable Acceptance Criteria — BDD scenarios)
- What constraints exist? (Non-Functional and Technical Requirements)
- What's unclear? (Open Questions)

Ask 2-3 questions per round. Don't overwhelm.

**CRITICAL: For Testable Acceptance Criteria, actively probe for coverage gaps.** Happy-path scenarios are easy to elicit; corner cases and failure modes need pulling.

Before generating the spec, push the user through every category in the canonical coverage taxonomy (`~/.claude/skills/test-standards/references/coverage-taxonomy.md`). Illustrative probes:

- **Corner cases** (e.g.): empty inputs, max sizes/limits, boundary values.
- **Failure modes** (e.g.): downstream timeouts, partial failures, rate limits.

If the user only describes the happy path, ask explicitly: "what should happen when X is empty / oversized / invalid / unavailable?"

The spec template requires happy + corner + failure coverage.

### 4. Propose 2-3 approaches with trade-offs

Once requirements feel solid, present 2-3 viable approaches conversationally. Lead with your recommendation and the reasoning. Cover the trade-off axes that matter for this idea (complexity, blast radius, reversibility, dependencies, time-to-first-value).

Get a directional pick from the user before writing the spec. Capture the outcome in the spec's Decisions section as one marker with discarded alternatives as sub-bullets.

Why include discarded options at all:

- The next session (or reviewer) will re-derive the same alternatives unless the rationale is preserved.
- Naming what lost — and why — prevents re-litigation.
- It surfaces when a trade-off has shifted (e.g., the constraint that killed alt-2 no longer applies).

### 5. Generate/update the spec

Write to the provided/discovered file path. For a fresh idea, name a new spec file:

- Derive a short kebab-case `<slug>` from the feature and confirm it with the user.
- Write `spec_<slug>.md` in CWD. The plan later inherits the same slug.
- The companion `spec-driven-development` skill defines this naming convention.

If the file already exists, update it in place (preserve user content, fill gaps, restructure into the template).

### 6. Present for review

Show the spec summary. Ask if anything is missing or wrong.
Iterate until the user is satisfied.
