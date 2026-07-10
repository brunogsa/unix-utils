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

Resolve with this shared baseline:

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Multiple specs or multiple plans** → list the matches numbered and ask the user which to use before proceeding.

The remaining shapes (zero matches, only one kind) diverge per consumer because their needs differ — each skill's own Discovery section is canonical. Recap:

- `/implement` — a plan is mandatory: plan without spec proceeds plan-only; no plan → ask for the path, else stop.
- `/auto-review` — only one kind found → prompt the user; zero matches → proceed without spec/plan context, telling the user explicitly.
- `/create-pr` — both files optional: use whichever exist (either, both, or neither); zero → proceed from commits + diff only.

### spec_<slug>.md (why / what)

Captures background, goals, requirements, testable acceptance criteria and functional decisions.
Owned by the user, refined collaboratively.

Populate @./assets/spec-template.md

### plan_<slug>.md (how / tasks)

Technical approach and task breakdown. Generated from spec_<slug>.md (or directly from prompt).

Contains the high level architecture, general flow, reuse and side-effect reports, failure handling, test design, task breakdown and technical decisions.

Populate @./assets/plan-template.md

Uses BDD/TDD by default: @~/.claude/skills/test-driven-development/SKILL.md
Opt-out per task with `**DECISION:** Skip TDD because <reason>` (inside the task itself).

## Lifecycle

0. User creates spec_<slug>.md with initial prompt/notes (or `/brainstorm` refines it).
1. Plan mode or direct request generates plan_<slug>.md from spec_<slug>.md (or from prompt).
2. AI Self-review — `deep-reviewer` subagents run structural gates; scope pass catches over-engineering and spec-vs-request drift. A failing mermaid `mmdc` check routes to `mermaid-fixer`, never fixed inline.
3. User reviews and approves — when the user signals, execution starts.
4. Each plan_<slug>.md task becomes a TaskCreate item.
5. Both files updated as work progresses (living docs); decisions are append-only past the divider that exists on both spec_<slug>.md and plan_<slug>.md.
6. User generally runs `/refactor` then `/auto-review` when the entire feature is developed; fixes are addressed, if any.
7. User manually review the code. More fixes, if any.
8. `/create-pr` uses both spec_<slug>.md and plan_<slug>.md to generate a rich PR description.
9. Self-improving loop: user runs `/improve-principles-and-skills-from-user-feedback` then `english-coach` skills so both AI and human learn.

### Self-review both spec and plan before handing it back (step 2 detail)

Read them with fresh eyes by spawning a sub-agent that reports:
- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within the same doc disagree?
  - Does plan_<slug>.md contradict spec_<slug>.md? Examples: spec assumptions planning overturned, architectural choices superseding spec requirements, scope constraints discovered during planning.
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition? If yes, write/update `scopes.md` per the `brainstorm` skill's scope-probe step, then re-run this self-review.
- **PR size**: does the work fit one reviewable PR, or is it large enough to stage into several?
  - If large, **PR Breakdown** must split the tasks into an ordered PR sequence — vertical splits, each shipping its own tests + code + docs — not one oversized PR.
  - Felt anchor: reviewer defect-detection drops past ~400 lines of diff and hard above ~600 (SmartBear/Cisco; Google small-CL) — no code exists yet, so estimate by feel, never invent a line count.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does ALL Goals, Success Metrics and KPIs, User Stories and Non-Functional and Technical Requirements being covered on Testable Acceptance Criteria section? ALL corner cases and failure modes covered?
- **Human-Reviewable**: Is it easy for the user to review? Is the format pleasant to read? Are you enabling user to verify you?
- **Artifacts Valid**: If any mermaid diagram exists, are they valid, verified via `mmdc`?
  - A failing check routes to the `mermaid-fixer` subagent on the resolved doc path — never fixed inline, mirroring the density-fixer rule below.
- **Density**: spawn the `density-fixer` subagent on the resolved `spec_<slug>.md` / `plan_<slug>.md` paths — never check or rewrite density violations inline.
  - The subagent runs `check-density.sh` and applies the `density-rules.md` rewrite patterns until exit 0, without dropping information.

Six checks (three `deep-reviewer` gates + two inline + one advisory scope lens) run in sequence:

- **Gates 1-3** (fail-closed): AC↔test coverage, test↔task assignment, machinery↔spec traceability — each a fresh-context `deep-reviewer` dispatch (Opus, max effort), so it sees only artifacts, no session bias.
- **Inline checks** (fail-closed): checklist completeness, inversion sweep — do the corner case and failure checklists have per-item disposition (covered / N/A)?
- **Scope lens** (advisory): does the spec match the user's request, or is plan_<slug>.md over-engineered relative to the ACs?

- **Gate 1 — AC ↔ Test Design coverage**: every `### AC-N:` in spec has ≥1 test in plan (semantic match, not grep).
  Output: orphan ACs (empty = pass). Block plan approval if non-empty.

- **Gate 2 — Test Design ↔ per-task assignment**: every Test Design title must be owned by a task's `**Tests (planned)**:`. Output: orphan titles (empty = pass). Block if non-empty.

- **Gate 3 — Machinery ↔ AC traceability**: every piece of machinery (abstraction, dependency, knob, extra layer) must trace to a spec AC or requirement.
  Output: untraceable items (empty = pass). Block if non-empty — cut or earn an AC.

- **Checklist completeness**: every corner case / failure mode item must be marked `covered (<recap>)`, `N/A — <reason>`, or opt-out: `**DECISION:** Skip because <reason>`. Empty placeholders fail self-review.

- **Inversion sweep**: for every AC, ask "how would this break in production?" If no failure mode surfaces, flag as under-specified.

- **Scope lens** (advisory): pass user's request + spec + plan to a subagent.
  Ask: does spec match request (no gold-plate), and is plan the simplest design meeting every AC?
  Advisory, not fail-closed — surface findings and let the user decide.

Why: catch them early; prevents "looks good, ship it" where ambiguity surfaces only in implementation.

#### Delta-scoped re-review on iteration rounds

The first self-review runs every gate over the whole doc.

Later rounds scope the gates to what actually changed — computed by `diff`, never from the in-doc summary (the human edits these docs directly, so a hand-maintained list misses their edits):

- **Snapshot at hand-off**: copy the docs into a stable dir when you hand them to the human; re-snapshot every hand-back.
  - `mkdir -p /tmp/sdd-snapshots && cp spec_<slug>.md plan_<slug>.md /tmp/sdd-snapshots/`

- **Diff on re-review**: next round, `diff /tmp/sdd-snapshots/spec_<slug>.md spec_<slug>.md` (same for plan) yields the changed hunks — including edits the human made directly.

- **Scope, don't blind**: hand each gate the changed hunks plus the full doc.
  - Gates stay fresh-context subagents, so the bias guarantee holds — scoping changes what they focus on, not where they run.

- **Re-check broken invariants**: each gate concentrates on the changed regions plus any invariant those changes break, even in UNCHANGED regions.
  - Deletions are the trap: removing an AC orphans the plan machinery tracing to it (Gate 3); removing a task orphans its owned test title (Gate 2).
  - Both orphans sit in unchanged regions the diff won't flag — this is what the full-doc backstop must catch.
  - The local case is easier: an edited AC or test re-runs that AC↔test coverage pair (Gate 1).

- **Backstop**: the full doc is present, so a gate that spots a problem outside the changed regions still reports it. The diff focuses the review, it doesn't blind it.

Why: convergence rounds shouldn't re-pay a full-doc review — it wastes subagent budget and makes the human re-read a whole report when only the delta moved.

The snapshot+diff is tools-first: it can't go stale or miss a human edit, unlike a hand-maintained marker.

The stable `/tmp` path is reconstructable after a `/clear`, so the re-review scope survives a phase handoff.

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

- **CRITICAL: Keep spec and plan as lean as the change allows — brief and didactic beats exhaustive**:
  - Fill only the sections the change needs; use each section's `N/A — <reason>` escape freely instead of padding.
  - Short titles, one thought per bullet, terse Given/When/Then — optimize for a fast human read, not formal completeness.
  - Why: these are throwaway living docs, so verbosity taxes every re-read and buries the decisions that matter.

- **Cross-references inside the planning doc spell out the behavior — never cite `AC-N` IDs** (doc-standards' no-ID-references rule; the `### AC-N:` headings defining ACs are anchors, not references).
  - Bad: "AC-12 / AC-13 / AC-15 / AC-16a behavior captured" — forces the reader to flip back.
  - Good: "one school's fetch fails / one agreement's SKU fetch fails — behavior captured".
  - Why: specs/plans are scanned non-linearly; an ID reference adds lookup cost on every scan, while the behavior recap alone already carries the meaning.

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
