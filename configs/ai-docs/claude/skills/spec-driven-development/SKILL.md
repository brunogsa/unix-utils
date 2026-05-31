---
name: spec-driven-development
description: "Spec-driven development with spec.md/plan.md as session-scoped, untracked living docs. USE PROACTIVELY when planning a non-trivial feature or breaking work into commits. For Socratic idea-refinement, use `brainstorm` instead."
disable-model-invocation: false
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
9. Self-improving loop: user runs `/improve-principles-and-skills-from-user-feedback` then `english-coach` skills so both AI and humand learn.

### Self-review both spec and plan before handing it back (step 2 detail)

Read them with fresh eyes by spawning a sub-agent that reports:
- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within the same doc disagree? Does plan.md contradict spec.md — assumptions the spec made that planning overturned, architectural choices that supersede spec requirements, or constraints discovered during planning that change scope?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition? If yes, jump back to step 2 and write/update `scopes.md`.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does ALL Goals, Success Metrics and KPIs, User Stories and Non-Functional and Technical Requirements being covered on Testable Acceptance Criteria section? ALL corner cases and failure modes covered?
- **Human-Reviewable**: Is it easy for the user to review? Is the format pleasant to read? Are you enabling user to verify you?
- **Artifacts Valid**: If any mermaid diagram exists, are they valid, verified via `mmdc`?
- **Density**: Run `~/.claude/skills/doc-standards/scripts/check-density.sh spec.md plan.md`.
  - Exit 0 = clean; exit 1 = rewrite each `<line>:<chars>:<words>` violation.
  - Follow `~/.claude/skills/doc-standards/references/density-rules.md` (paragraph → bullets+sub-bullets, long bullet → bullet + sub-bullets) without dropping information.

The next four checks are **dedicated fresh-context gates** — each runs in its own subagent invocation so prior session bias does not leak into the verdict. All four are **fail-closed**: any miss, parse error, or subagent error blocks self-review until reconciled.

- **Gate 1 — AC ↔ Test Design coverage**: spawn a fresh-context subagent with `spec.md` + `plan.md`. Task: for every `### AC-N:` heading in spec.md, identify at least one test in plan.md (either in the global Test Design section or under a task's `**Tests (planned)**:`) that semantically covers it. Output: list of ACs with no covering test (empty list = pass).
  - Semantic match, not literal grep — AC wording and test title may diverge ("reject empty input" ↔ "return 400 when payload missing"); the subagent judges equivalence.
  - Block plan approval on any non-empty missing list.

- **Gate 2 — Test Design ↔ per-task assignment**: spawn a separate fresh-context subagent with `plan.md`. Task: for every test title in the global Test Design section, locate the task whose `**Tests (planned)**:` bullet owns it. Output: list of orphan titles (tests designed but unassigned).
  - Same fail-closed semantics as Gate 1.

- **Checklist completeness**: verify spec.md's **boundary checklist** (under Corner cases) and **failure category checklist** (under Failure modes) are evaluated — each item marked `covered (AC-N)` or `N/A — <reason>`. Empty template placeholders fail self-review.
  - Honor opt-out: a checklist replaced with `**DECISION:** Skip <name> checklist because <reason>` counts as evaluated.

- **Inversion sweep**: for every AC in spec.md, ask "how would this break in production?". If no failure mode surfaces, the AC is under-specified — flag it for the user to either tighten the AC or document the N/A reason in the failure-category checklist.

Why: cheaper for you to catch these than for the user to find them in review — and it prevents the "looks good, ship it" loop where ambiguity surfaces only during implementation.

#### Resolving spec/plan drift

When plan.md and spec.md disagree, surface each conflict before updating anything:

1. **List each drift item** — what spec.md states, what plan.md says, and why they conflict.

2. **Present to the user and wait** — don't update either doc yet. The user picks the direction:
   - Update spec.md (planning uncovered a better reality).
   - Correct plan.md (it misread the spec).
   - Add a `**QUESTION:**` marker (the trade-off is genuinely open).

3. **Apply only the agreed change** — targeted edit to whichever doc the user chose; don't refactor surrounding content.

Why: spec.md drives PR description and auto-review — a stale spec ships wrong context downstream. But plan.md can also be the one that's wrong; surfacing the choice preserves intent rather than assuming the spec was outdated.

## Guidelines

- **CRITICAL: spec.md and plan.md are session-scoped and untracked**.
  - Never reference them in committed artifacts (code comments, commit bodies, docs).
  - They stay local and get removed after the session; the next reader won't have them. Put the why in the code comment itself or other appropriated place.

- **Cross-references inside the planning doc expand inline, not by ID alone**.
  - Bad: "AC-12 / AC-13 / AC-15 / AC-16a behavior captured" — forces the reader to flip back.
  - Good: "AC-12 (one school's fetch fails) / AC-13 (one agreement's SKU fetch fails)".
  - Why: specs/plans are scanned non-linearly; ID-only references add lookup cost on every scan.

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
