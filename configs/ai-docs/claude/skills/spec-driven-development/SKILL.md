---
name: spec-driven-development
description: "Spec-driven development with spec.md/plan.md as session-scoped, untracked living docs. USE PROACTIVELY when planning a non-trivial feature or breaking work into commits. For Socratic idea-refinement, use `brainstorm` instead."
user-invocable: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in the project root to guide development, code review, and PR description generation.

## Documents

Two living documents in the project root. Templates live in `assets/` and are populated based on the user's input.

### spec.md (why / what)

Captures background, goals, requirements, testable acceptance criteria and functional decisions.
Owned by the user, refined collaboratively.

Populate @./assets/spec-template.md

### plan.md (how / tasks)

Technical approach and task breakdown. Generated from spec.md (or directly from prompt).

Contains the high level architecture, general flow, reusage and side effect reports, test design, task breakdown and technical decisions.

Populate @./assets/plan-template.md

Uses BDD/TDD by default: @~/.claude/skills/test-driven-development/SKILL.md
Opt-out per task with `**DECISION:** Skip TDD because <reason>` (inside the task itself).

## Lifecycle

0. User creates spec.md with initial prompt/notes (or `/brainstorm` refines it).
1. Plan mode or direct request generates plan.md from spec.md (or from prompt).
2. AI Self-review — surface gaps, contradictions, unresolved ambiguity. Validate every mermaid block with `mmdc` (caveats in plan-template.md).
3. User reviews and approves — when the user signals, execution start.
4. Each plan.md task becomes a TaskCreate item.
5. Both files updated as work progresses (living docs); decisions are append-only past the divider that exists on both spec.md and plan.md.
6. User generally run `/refactor` then `/auto-review` skills when the entire features is developed; fixes are addressed, if any.
7. User manually review the code. More fixes, if any.
8. `/create-pr` uses both spec.md and plan.md to generate a rich PR description.
9. Self-improving loop: user runs `/improve-principles-and-skills-from-session-learnings` then `english-coach` skills so both AI and humand learn.

Both spec.md and plan.md enable or enrich multiple of these steps.


### Self-review both spec and plan before handing it back

Read them with fresh eyes by spawning a sub-agent that reports:
- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections disagree?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition? If yes, jump back to step 2 and write/update `scopes.md`.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does ALL Goals, Success Metrics and KPIs, User Stories and Non-Functional and Technical Requirements being covered on Testable Acceptance Criteria section? ALL corner cases and failure modes covered?
- **Human-Reviewable**: Is it easy for the user to review? Is the format pleasant to read? Are you enabling user to verify you?
- **Artifacts Valid**: If any mermaid diagram exists, are they valid, verified via `mmdc`?

Why: cheaper for you to catch these than for the user to find them in review — and it prevents the "looks good, ship it" loop where ambiguity surfaces only during implementation.

## Guidelines

- **CRITICAL: spec.md and plan.md are session-scoped and untracked**.
  - Never reference them in committed artifacts (code comments, commit bodies, docs).
  - They stay local and get removed after the session; the next reader won't have them. Put the why in the code comment itself or other appropriated place.

- **CRITICAL: Keep spec and plan up to date** -- Stale docs degrade `/create-pr`.

- **plan.md tasks and their sub-steps become items on TaskList**.

- **Tasks are commit-sized, never smaller**.

- **CRITICAL: Keep task status updated as you go, in both TaskList and plan.md**:
  - For plan.md use this pattern:
    - The "ToDo" / "Pending" state do not required a marker
    - Suggested status: `[Doing]`, `[Done]`, `[Blocked]`, `[Deferred]`, `[Dropped]`
    - Shape: `## <status> Task <N>: <title>`

- **After completing a task note deviations from the original plan**.

- **CRITICAL: When a doc warrants a diagram, follow the `mermaid-diagrams` skill**.

- **CRITICAL: Add a blank line between bullets (not sub-bullets)**:
  - This improve A LOT the readability
