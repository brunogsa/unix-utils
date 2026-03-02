---
description: "Spec-driven development workflow using spec.md (what/why) and plan.md (how/tasks) as living documents for features and significant changes"
user-invocable: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in the project root to guide development, code review, and PR description generation.

## Documents

### spec.md (what / why)

Captures requirements, context, and acceptance criteria. Owned by the user, refined collaboratively.

```markdown
# Spec: [Title]

## Background
Why this change is needed. Business context, pain point, or opportunity.

## Goals
What we want to achieve (outcomes, not implementation).

## User Stories
- As a [role], I want [capability] so that [benefit].

## Functional Requirements
1. System MUST ...
2. System MUST ...

## Non-Functional Requirements
1. Performance: ...
2. Security: ...

## Acceptance Criteria
1. [Testable criterion]
2. [Testable criterion]

## Open Questions
- [NEEDS CLARIFICATION: ...]

## Decisions
- [DECISION: ... because ...]
```

### plan.md (how / tasks)

Technical approach and task breakdown. Generated from spec.md (or directly from prompt).

```markdown
# Plan: [Title]

Spec: [link or reference to spec.md]

## Approach
High-level technical approach. Architecture decisions. Trade-offs considered.

## Tasks

### 0. Symlink plan to project directory
**What**: Create a symlink from this plan file to `./plan.md` in the current working directory. If spec.md exists in cwd, it was already used as input.
**Verify**: `readlink ./plan.md` points to this plan file.

### 1. [Task title]
**Description**: What needs to be done.
**Files**: `path/to/file1.ts`, `path/to/file2.ts`
**Acceptance criteria**: What "done" looks like for this task.
**Verify**: Command or test that proves it works.

### 2. [Task title]
...

## Decisions
- [DECISION: ... because ...]
```

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
- **Include diagrams** -- use Mermaid blocks (source + rendered ASCII) when architecture, data flow, or state would clarify the spec or plan. See `mermaid-ascii-diagrams` skill.
- **Tasks are baby steps** -- each task in plan.md should be the smallest testable, committable change
- **Acceptance criteria are testable** -- every task has a concrete verify method (command, test, or manual check)
- **Update docs at each task boundary** -- stale spec/plan degrades PR description quality. Specific triggers:
  - **After completing a task**: mark it done in plan.md, note any deviations from the original plan
  - **After making a decision**: add `[DECISION: ... because ...]` marker immediately in the relevant file
  - **After discovering scope changes**: add/remove/update tasks in plan.md, update acceptance criteria in spec.md
  - **After incidental changes**: if you fix or change something not in the plan, add it as a completed task in plan.md so `/create-pr` can distinguish planned vs incidental work
