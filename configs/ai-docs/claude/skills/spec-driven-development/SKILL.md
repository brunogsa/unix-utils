---
name: spec-driven-development
description: "Spec-driven development with spec_<slug>.md/plan_<slug>.md as session-scoped, untracked living docs. USE PROACTIVELY when planning a non-trivial feature or breaking work into commits. For Socratic idea-refinement, use `brainstorm` instead."
disable-model-invocation: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in the project root to guide development, code review, and PR description generation.

## Documents

Two living documents in the project root. Templates live in `assets/` and are populated based on the user's input.

These throwaway docs feed from durable design docs (ADR / HLD / LLD). Load the `design-docs` skill for the ownership + altitude rules that keep spec/plan from re-deriving them.

### Naming convention

Each feature gets a descriptive slug, and its spec and plan **share** that slug:

- `spec_<slug>.md` — e.g. `spec_parallel-sessions.md`
- `plan_<slug>.md` — e.g. `plan_parallel-sessions.md`

`<slug>` is a short kebab-case descriptor of the feature. The shared slug pairs the spec with its plan by name.

Why descriptive over one generic filename: a directory may hold several in-flight features at once, and a slug makes each pair self-identifying instead of colliding on one shared name.

### Discovery (how consumers find these files)

Downstream skills (`/implement`, `/auto-review`, `/create-pr`) discover the files by glob in CWD (top-level only):

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

Resolve with this decision tree:

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Zero matches** → proceed without spec/plan context; tell the user explicitly.
- **Any other shape** (multiple specs, multiple plans, only one kind) → list the matches numbered and ask the user which to use before proceeding.

### spec_<slug>.md (why / what)

Captures background, goals, requirements, testable acceptance criteria and functional decisions.
Owned by the user, refined collaboratively.

Populate @./assets/spec-template.md

### plan_<slug>.md (how / tasks)

Technical approach and task breakdown. Generated from spec_<slug>.md (or directly from prompt).

Contains the high level architecture, general flow, reusage and side effect reports, test design, task breakdown and technical decisions.

Populate @./assets/plan-template.md

Uses BDD/TDD by default: @~/.claude/skills/test-driven-development/SKILL.md
Opt-out per task with `**DECISION:** Skip TDD because <reason>` (inside the task itself).

## Lifecycle

0. User creates spec_<slug>.md with initial prompt/notes (or `/brainstorm` refines it).
1. Plan mode or direct request generates plan_<slug>.md from spec_<slug>.md (or from prompt).
2. AI Self-review (two lenses) — a fresh-context subagent runs the unbiased structural gates; an advisor pass catches over-engineering and spec-vs-request drift. Validate every mermaid block with `mmdc` (caveats in plan-template.md).
3. User reviews and approves — when the user signals, execution start.
4. Each plan_<slug>.md task becomes a TaskCreate item.
5. Both files updated as work progresses (living docs); decisions are append-only past the divider that exists on both spec_<slug>.md and plan_<slug>.md.
6. User generally run `/refactor` then `/auto-review` skills when the entire features is developed; fixes are addressed, if any.
7. User manually review the code. More fixes, if any.
8. `/create-pr` uses both spec_<slug>.md and plan_<slug>.md to generate a rich PR description.
9. Self-improving loop: user runs `/improve-principles-and-skills-from-user-feedback` then `english-coach` skills so both AI and humand learn.

### Self-review both spec and plan before handing it back (step 2 detail)

Read them with fresh eyes by spawning a sub-agent that reports:
- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within the same doc disagree?
  - Does plan_<slug>.md contradict spec_<slug>.md? Examples: spec assumptions planning overturned, architectural choices superseding spec requirements, scope constraints discovered during planning.
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition? If yes, jump back to step 2 and write/update `scopes.md`.
- **PR size**: does the work fit one reviewable PR, or is it large enough to stage into several?
  - If large, **PR Breakdown** must split the tasks into an ordered PR sequence — vertical splits, each shipping its own tests + code + docs — not one oversized PR.
  - Felt anchor: reviewer defect-detection drops past ~400 lines of diff and hard above ~600 (SmartBear/Cisco; Google small-CL) — no code exists yet, so estimate by feel, never invent a line count.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does ALL Goals, Success Metrics and KPIs, User Stories and Non-Functional and Technical Requirements being covered on Testable Acceptance Criteria section? ALL corner cases and failure modes covered?
- **Human-Reviewable**: Is it easy for the user to review? Is the format pleasant to read? Are you enabling user to verify you?
- **Artifacts Valid**: If any mermaid diagram exists, are they valid, verified via `mmdc`?
- **Density**: Run `~/.claude/skills/doc-standards/scripts/check-density.sh <resolved-spec> <resolved-plan>` (the actual `spec_<slug>.md` / `plan_<slug>.md` paths).
  - Exit 0 = clean; exit 1 = rewrite each `<line>:<chars>:<words>` violation.
  - Follow `~/.claude/skills/doc-standards/references/density-rules.md` (paragraph → bullets+sub-bullets, long bullet → bullet + sub-bullets) without dropping information.

Three of the five checks below are **dedicated fresh-context subagent gates** (Gate 1, Gate 2, Gate 3) — they see only the artifacts, so no writing-session bias leaks in.

The other two (checklist completeness, inversion sweep) are inline checks.

All five are **fail-closed**: any miss, parse error, or subagent error blocks self-review until reconciled.

A sixth check — the **advisor lens** — runs on the full session instead of a fresh context, and is advisory rather than fail-closed.

It is the one judgment the artifact-only gates structurally can't make: whether the spec is over-scoped versus what the user actually asked.

- **Gate 1 — AC ↔ Test Design coverage**: spawn a fresh-context subagent with `spec_<slug>.md` + `plan_<slug>.md`.
  - Task: for every `### AC-N:` in spec_<slug>.md, identify at least one test in plan_<slug>.md (Test Design section or per-task `**Tests (planned)**:`) that semantically covers it.
  - Output: list of ACs with no covering test (empty = pass).
  - Semantic match, not literal grep — AC wording and test title may diverge ("reject empty input" ↔ "return 400 when payload missing"); the subagent judges equivalence.
  - Block plan approval on any non-empty missing list.

- **Gate 2 — Test Design ↔ per-task assignment**: spawn a separate fresh-context subagent with `plan_<slug>.md`.
  - Task: for every title in the global Test Design section, locate the task whose `**Tests (planned)**:` bullet owns it.
  - Output: list of orphan titles (designed but unassigned).
  - Same fail-closed semantics as Gate 1.

- **Gate 3 — Machinery ↔ AC traceability (over-engineering)**: spawn a fresh-context subagent with `spec_<slug>.md` + `plan_<slug>.md`.
  - Task: for every piece of machinery in plan_<slug>.md — each abstraction, dependency, config knob, extra layer, or point of generality — name the spec AC or documented requirement (goal/NFR) it serves.
  - Output: list of machinery with no traceable justification (empty = pass).
  - Untraceable machinery is speculative scope; block plan approval until each item is either cut or earns an AC that justifies it.
  - "Necessary" means it traces to a requirement — this is the artifact-internal half of the over-engineering check; the request-context half is the advisor lens below.

- **Checklist completeness**: verify spec_<slug>.md's **boundary checklist** (Corner cases) and **failure category checklist** (Failure modes) are evaluated.
  - Each item marked `covered (AC-N)` or `N/A — <reason>`. Empty template placeholders fail self-review.
  - Honor opt-out: a checklist replaced with `**DECISION:** Skip <name> checklist because <reason>` counts as evaluated.

- **Inversion sweep**: for every AC in spec_<slug>.md, ask "how would this break in production?".
  - If no failure mode surfaces, the AC is under-specified — flag it for the user to tighten the AC or document N/A in the failure-category checklist.

- **Advisor lens (full-context, advisory — not a gate)**: the gates above see only the artifacts, so they can't tell whether the spec itself is over-scoped versus what you were actually asked.
  - The advisor sees the whole session, so it can.
  - First state the concern in your reasoning — name plan_<slug>.md's heaviest machinery and the simplest design you believe meets every AC — then call `advisor()`.
    - It forwards the transcript with no question attached, so a bare call with nothing staged wastes it.
  - Aim it at two judgments: is the spec scoped to the request (no gold-plated ACs the user never asked for), and is plan_<slug>.md the simplest design that still meets every AC?
  - Advisory, not fail-closed: surface its findings to the user alongside the gate results and let them decide what to cut.
    - Over-engineering is a judgment call, not a parse error — don't block on it.

Why: cheaper for you to catch these than for the user to find them in review — and it prevents the "looks good, ship it" loop where ambiguity surfaces only during implementation.

#### Resolving spec/plan drift

When plan_<slug>.md and spec_<slug>.md disagree, surface each conflict before updating anything:

1. **List each drift item** — what spec_<slug>.md states, what plan_<slug>.md says, and why they conflict.

2. **Present to the user and wait** — don't update either doc yet. The user picks the direction:
   - Update spec_<slug>.md (planning uncovered a better reality).
   - Correct plan_<slug>.md (it misread the spec).
   - Add a `**QUESTION:**` marker (the trade-off is genuinely open).

3. **Apply only the agreed change** — targeted edit to whichever doc the user chose; don't refactor surrounding content.

Why: spec_<slug>.md drives PR description and auto-review — a stale spec ships wrong context downstream.

But plan_<slug>.md can also be wrong; surfacing the choice preserves intent rather than assuming the spec was outdated.

## Guidelines

- **CRITICAL: spec_<slug>.md and plan_<slug>.md are session-scoped and untracked**.
  - Never reference them in committed artifacts (code comments, commit bodies, docs).
  - They stay local and get removed after the session; the next reader won't have them. Put the why in the code comment itself or other appropriated place.

- **Cross-references inside the planning doc expand inline, not by ID alone**.
  - Bad: "AC-12 / AC-13 / AC-15 / AC-16a behavior captured" — forces the reader to flip back.
  - Good: "AC-12 (one school's fetch fails) / AC-13 (one agreement's SKU fetch fails)".
  - Why: specs/plans are scanned non-linearly; ID-only references add lookup cost on every scan.

- **CRITICAL: Keep spec and plan up to date** -- Stale docs degrade `/create-pr`.

- **Maintain the "Bottom line" and "Since your last review" header on every edit** -- they serve the human reviewer, your bottleneck.
  - The Bottom line is the reviewer's BLUF: the proposal, the one decision to weigh, the scope boundary — so an early-scanning reader gets the conclusion before the detail.
  - The "Since your last review" delta lists one bullet per section changed since the human last looked, so they re-read only the delta.
  - Update it in the same edit that changes the body; a stale summary misleads the reviewer.
  - This delta is human-facing prose only — the gates compute their re-review scope by diff, not from this list.

- **plan_<slug>.md tasks and their sub-steps become items on TaskList**.

- **Tasks are commit-sized, never smaller**.

- **CRITICAL: Keep task status updated as you go, in both TaskList and plan_<slug>.md**:
  - For plan_<slug>.md use this pattern:
    - The "ToDo" / "Pending" state do not required a marker
    - Suggested status: `[Doing]`, `[Done]`, `[Blocked]`, `[Deferred]`, `[Dropped]`
    - Shape: `## <status> Task <N>: <title>`

- **After completing a task note deviations from the original plan**.

- **CRITICAL: When a doc warrants a diagram, follow the `mermaid-diagrams` skill**.

- **CRITICAL: Add a blank line between bullets (not sub-bullets)**:
  - This improve A LOT the readability
