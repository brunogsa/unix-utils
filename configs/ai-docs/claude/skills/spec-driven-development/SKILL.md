---
name: spec-driven-development
description: "Spec-driven development methodology with spec.md/plan.md as living docs. USE PROACTIVELY when planning a non-trivial feature or breaking work into committable tasks. For interactive idea-refinement (Socratic Q&A), use `brainstorm` instead."
user-invocable: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in the project root to guide development, code review, and PR description generation.

## Documents

Two living documents in the project root. Templates live in `assets/` and are populated (not copied verbatim) based on the user's input.

### spec.md (what / why)

Captures requirements, context, and acceptance criteria. Owned by the user, refined collaboratively.

Populate `assets/spec-template.md` — sections: Background, Goals, User Stories, Functional Requirements, Non-Functional Requirements, **Testable Acceptance Criteria** (BDD-style Given/When/Then scenarios — see template for format and the happy/corner/failure coverage rule), Open Questions (`**QUESTION:**` markers), Decisions (`**DECISION:** ..., because ...` markers).

### plan.md (how / tasks)

Technical approach and task breakdown. Generated from spec.md (or directly from prompt).

Populate `assets/plan-template.md` — sections: Approach; Test Design; Tasks (each with Description, Files, Acceptance criteria, Verify, **Commits**); Decisions. Each task names its planned commits (typically 1 base; optionally +1 if a refactor is anticipated upfront) (repo + `type(scope): subject`) as a local subsection — no separate global commit index. Task 0 is always a symlink step so `./plan.md` resolves to the canonical plan file.

## Marker Conventions

Bold-label prefix + colon. No brackets — they trip markdown link-parsing in some editors.

Separate adjacent markers with a blank line when listed in dedicated sections (Decisions, Open Questions) — readability.

### `**QUESTION:** <specific question>`

Surfaces ambiguity explicitly. Used in spec.md and plan.md.
When resolved, remove the marker entirely.

### `**DECISION:** <what was decided>, because <reasoning>`

Captures trade-off decisions as they happen. Feeds into PR descriptions.

- **Editable while planning** — modify in place freely.
- **Append-only after execution begins** — once the user approves the plan, the execution divider is inserted in spec.md and plan.md; from that point, append new entries prefixed `**DECISION (Task N):**`. To revise an earlier decision, append a new entry ending with `**Supersedes:** "<first ~60 chars of prior decision>"` rather than editing the prior entry in place.
- **Why:** preserves evolution for `/create-pr` and review; keeps prompt cache warm (immutable history); makes `git diff` of the plan unambiguous (only additions, no rewrites).

### `**LINTER GAP:** <what the linter should have caught>`

Surfaces lint coverage gaps so the config can be improved.

Grep all markers: `\*\*(DECISION|QUESTION|LINTER GAP):\*\*`

## Lifecycle

0. User creates spec.md with initial prompt/notes (or `/brainstorm` refines it).
1. Plan mode or direct request generates plan.md from spec.md (or from prompt).
2. **Self-review** — run the two checks in the next section; surface gaps, unresolved `**QUESTION:**` markers, and any incidental observations (per the scout rule).
3. **User approves the plan** — when the user signals execution start (e.g., "approved, let's go"), insert the execution divider line into the `## Decisions` section of both spec.md and plan.md as the first action, then begin Task 1.
4. Each plan.md task becomes a TaskCreate item (with acceptance criteria + verify).
5. Both files updated as work progresses (living docs); decisions are append-only past the divider.
6. `/create-pr` uses both files to generate a rich PR description.
7. spec.md and plan.md are NOT committed -- session-scoped scaffolding (gitignored or deleted after PR).

## Self-review

After writing or revising spec.md or plan.md, run two checks before handing off:

1. **Spec coverage** — for each spec acceptance criterion, name the task that implements it. Surface gaps to the user only when they might be intentional out-of-scope (so the user can confirm).
2. **Open questions** — collect every unresolved `**QUESTION:**` marker; surface them as a "before we proceed, can you answer these?" list.

Anything else you notice during the review (stray placeholders, name drift, inconsistent terminology, stale references) follows the scout rule from `CLAUDE.md` — flag it to the user, fix only if approved. The two checks above are mandatory; everything beyond is incidental observation worth surfacing but not blocking.

## Guidelines

- **spec.md is optional** -- plan.md can be created directly from a prompt for smaller work
- **Separate long list items with blank lines** -- if an item wraps to two or more visual lines, put a blank line between it and its neighbours. Short single-line items stay compact. Applies across the whole file (Goals, User Stories, Requirements, Acceptance Criteria, Decisions, Questions).
- **Tasks are commit-sized, never smaller** -- each task produces **at least one base commit** (tests + impl together; RED/GREEN cycles inside that commit). Optional breadcrumb in the task title: `### N. Title (tests; impl; refactor)`. At execution, any refactor, scout finding, side quest worked on, separable incidental, or `/auto-review` follow-up gets its own additional commit within the task. Substantial scope additions still warrant a new peer task. Why: smaller than a commit = noise on the task list; bundling unrelated changes = mixed-concern reviews.
- **Acceptance criteria are testable** -- every task has a concrete verify method (command, test, or manual check)
- **Update docs at each task boundary** -- stale spec/plan degrades PR description quality. Specific triggers:
  - **After completing a task**: mark it done in plan.md, note any deviations from the original plan
  - **After making or revising a decision**: append a `**DECISION (Task N):**` entry below the execution divider. To revise a prior decision, end the new entry with `**Supersedes:** "<first ~60 chars of prior>"` rather than editing the prior entry in place.
  - **After discovering scope changes**: add/remove/update tasks in plan.md, update acceptance criteria in spec.md
  - **After incidental changes**: if you fix or change something not in the plan, add it as a completed task in plan.md so `/create-pr` can distinguish planned vs incidental work
