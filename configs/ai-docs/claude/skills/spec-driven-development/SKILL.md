---
description: "Spec-driven development methodology: spec.md (requirements/why) and plan.md (tasks/how) as living docs, marker conventions ([NEEDS CLARIFICATION] for gaps, [DECISION: ... because ...] for trade-offs), and the spec→plan→tasks lifecycle. Templates live in assets/. USE PROACTIVELY when planning a non-trivial feature, writing up requirements, breaking work into committable tasks, or starting significant multi-step work — the skill provides both templates and the methodology for keeping spec and plan live as work progresses."
user-invocable: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in the project root to guide development, code review, and PR description generation.

## Documents

Two living documents in the project root. Templates live in `assets/` and are populated (not copied verbatim) based on the user's input.

### spec.md (what / why)

Captures requirements, context, and acceptance criteria. Owned by the user, refined collaboratively.

Populate `assets/spec-template.md` — sections: Background, Goals, User Stories, Functional Requirements, Non-Functional Requirements, Acceptance Criteria, Open Questions (`[NEEDS CLARIFICATION]` markers), Decisions (`[DECISION: ... because ...]` markers).

### plan.md (how / tasks)

Technical approach and task breakdown. Generated from spec.md (or directly from prompt).

Populate `assets/plan-template.md` — sections: Approach; Tasks (each with Description, Files, Acceptance criteria, Verify); Decisions. Task 0 is always a symlink step so `./plan.md` resolves to the canonical plan file.

## Marker Conventions

### `[NEEDS CLARIFICATION: <specific question>]`

Surfaces ambiguity explicitly. Used in spec.md and plan.md.
When resolved, remove the marker entirely.

### `[DECISION: <what was decided> because <reasoning>]`

Captures trade-off decisions as they happen. Feeds into PR descriptions.
When a decision changes, update the existing marker in place.

## Lifecycle

0. User creates spec.md with initial prompt/notes (or `/brainstorm` refines it)
1. Plan mode or direct request generates plan.md from spec.md (or from prompt)
2. Each plan.md task becomes a TaskCreate item (with acceptance criteria + verify)
3. Both files are updated as development progresses (living docs)
4. `/create-pr` uses both files to generate a rich PR description
5. spec.md and plan.md are NOT committed -- session-scoped scaffolding (gitignored or deleted after PR)

## Guidelines

- **spec.md is optional** -- plan.md can be created directly from a prompt for smaller work
- **Tasks are baby steps** -- each task in plan.md should be the smallest testable, committable change
- **Acceptance criteria are testable** -- every task has a concrete verify method (command, test, or manual check)
- **Update docs at each task boundary** -- stale spec/plan degrades PR description quality. Specific triggers:
  - **After completing a task**: mark it done in plan.md, note any deviations from the original plan
  - **After making a decision**: add `[DECISION: ... because ...]` marker immediately in the relevant file
  - **After discovering scope changes**: add/remove/update tasks in plan.md, update acceptance criteria in spec.md
  - **After incidental changes**: if you fix or change something not in the plan, add it as a completed task in plan.md so `/create-pr` can distinguish planned vs incidental work
