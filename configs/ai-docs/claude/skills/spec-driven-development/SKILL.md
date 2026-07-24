---
name: spec-driven-development
description: "Spec-driven development with spec_<slug>.md/plan_<slug>.md as session-scoped, untracked living docs. USE PROACTIVELY when planning a non-trivial feature or breaking work into commits. For Socratic idea-refinement, use `brainstorm` instead."
disable-model-invocation: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in CWD to guide development, code review, and PR description generation.

## Documents

Two living documents in CWD. Templates live in `assets/` and are populated based on the user's input.

These throwaway docs feed from durable design docs (ADR / HLD / LLD). Load the `design-docs` skill for the ownership + altitude rules that keep spec/plan from re-deriving them.

### Naming convention

Each feature gets a descriptive slug, and its spec and plan **share** that slug:

- `spec_<slug>.md` — e.g. `spec_parallel-sessions.md`
- `plan_<slug>.md` — e.g. `plan_parallel-sessions.md`

`<slug>` is a short kebab-case descriptor of the feature. The shared slug pairs the spec with its plan by name.

Why: a directory may hold several in-flight features at once, so a descriptive slug keeps each pair self-identifying instead of colliding on one shared name.

### Discovery (how consumers find these files)

Downstream skills (`/implement`, `/auto-review`, `/create-pr`) discover the files by glob in CWD (top-level only):

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

Resolve with this shared baseline:

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Multiple specs or multiple plans** → list the matches numbered and ask the user which to use before proceeding.

The remaining shapes (zero matches, only one kind) diverge per consumer because their needs differ — each skill's own Discovery section is canonical.

### spec_<slug>.md (why / what)

Captures background, goals, requirements, testable acceptance criteria and functional decisions.
Owned by the user, refined collaboratively.

Read `./assets/spec-template.md` when starting the spec phase, and populate it.

### plan_<slug>.md (how / tasks)

Technical approach and task breakdown. Generated from spec_<slug>.md (or directly from prompt).

Read `./assets/plan-template.md` when starting the plan phase, and populate it.

Uses BDD/TDD by default: load the `test-driven-development` skill when starting the implementation phase.
Opt-out per task with `**DECISION:** Skip TDD because <reason>` (inside the task itself).

## Lifecycle

0. User creates spec_<slug>.md with initial prompt/notes (or `/brainstorm` refines it).
1. Dispatch the `plan-writer` subagent to write plan_<slug>.md from spec_<slug>.md alone — same mechanism regardless of whether the spec came from `/brainstorm`, plan mode, or a direct request.
   - Exception: a plan requested straight from a prompt with no spec_<slug>.md on disk skips plan-writer (spec-only input) — write it in-session instead.
2. AI Self-review — qualitative pass, then seven formal checks (five always-on, two toggled by one live question asked once).
3. User reviews and approves — then run `/clear` and invoke `/implement` in a fresh session; never continue in this one.
   - Why: `/implement` re-grounds from spec_<slug>.md and plan_<slug>.md on disk, so carrying this session forward only blurs planning-vs-execution cost.
4. Each plan_<slug>.md task becomes a TaskCreate item.
5. Both files updated as work progresses (living docs); decisions are append-only past the divider that exists on both spec_<slug>.md and plan_<slug>.md.
6. User runs `/refactor` then `/auto-review` when the entire feature is developed; fixes are addressed, if any.
7. User manually review the code. More fixes, if any.
8. `/create-pr` uses both spec_<slug>.md and plan_<slug>.md to generate a rich PR description.
9. Self-improving loop: user runs `/improve-from-user` then `english-coach` skills so both AI and human learn.

### Self-review both spec and plan before handing it back (step 2 detail)

First, a qualitative pass — spawn one sub-agent that reads both docs with fresh eyes and reports (findings only, no gate):
- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within the same doc disagree, or does plan_<slug>.md contradict spec_<slug>.md (e.g. spec assumptions overturned by planning, architectural choices superseding spec requirements)?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition? If yes, write/update `scopes.md` per the `brainstorm` skill's scope-probe step, then re-run this self-review.
- **PR size**: does the work fit one reviewable PR, or is it large enough to stage into several?
  - If large, **PR Breakdown** must split the tasks into an ordered PR sequence — vertical splits, each shipping its own tests + code + docs — not one oversized PR.
  - Felt anchor: reviewer defect-detection drops past ~400 lines of diff and hard above ~600 (SmartBear/Cisco; Google small-CL) — no code exists yet, so estimate by feel, never invent a line count.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does the Testable Acceptance Criteria section cover every Goal, Success Metric/KPI, User Story, and Non-Functional/Technical Requirement — and every corner case and failure mode?
- **Human-Reviewable**: could a complete novice succeed with only this plan and the repo — no other context? Is the format pleasant to read enough to let the user verify you?
- **Artifacts Valid**: If any mermaid diagram exists, are they valid, verified via `mmdc`?
  - A failing check routes to the `mermaid-fixer` subagent on the resolved doc path — never fixed inline.
- **Density**: spawn the `density-fixer` subagent on the resolved `spec_<slug>.md` / `plan_<slug>.md` paths — never check/rewrite density violations inline.
  - The subagent runs `check-density.sh` and applies the `density-rules.md` rewrite patterns until exit 0, without dropping information.

Immediately before dispatching `plan-writer` (or writing the plan in-session on the spec-less exception path), the orchestrating session asks one live question with two independent yes/no toggles.
It is answered fresh each time, never written to `plan_<slug>.md` or any state file:

- **"Every line traces to an AC?"**
- **"Right-sized plan?"**

Seven formal checks run in sequence (five always-on + the two toggles above):

| Check | Catches | Toggle? |
|---|---|---|
| Every AC has a test | AC↔Test Design coverage | Always on |
| Every test has a task | Test Design↔per-task assignment | Always on |
| How would this break? | checklist completeness + inversion sweep, merged | Always on |
| PR dependencies form a DAG | cyclic, dangling, or duplicate PR-N label in the PR Breakdown | Always on |
| Task dependencies form a DAG | cyclic, dangling, or duplicate task id in the Task Breakdown | Always on |
| Every line traces to an AC | machinery↔AC traceability | Toggle |
| Right-sized plan | scope vs. request, simplest design | Toggle |

The five always-on checks, plus the Test Design authoring requirement itself, never become optional — they verify the plan is mechanically correct regardless of change size.

A toggled-off check is simply omitted from that pass; self-review's output states explicitly which checks were skipped by request, so the reviewer never wonders why something is absent.

- **Every AC has a test**: every `### AC-N:` in spec is proven by ≥1 test in the plan's AC-grouped coverage list.
  - Mechanical half — `scripts/check-ac-coverage.sh <plan> <spec>`: completeness (every AC in the spec's Acceptance-Criteria section has a coverage header).
    Honesty: every cited breadcrumb exists verbatim among Test Design breadcrumbs; a `…`-truncated or invented citation won't match.
    Exit 1 blocks.
  - Semantic half — a `deep-reviewer` dispatch judges whether each cited test actually *proves* its AC — the match no script can make.
  - Output: orphan ACs + bogus citations (empty = pass). Block plan approval if non-empty.

- **Every test has a task**: `scripts/check-test-distribution.sh <plan>` asserts set-equality between the Test Design breadcrumbs (A) and the union of tasks' `**Tests (planned)**:` lists (B).
  Deterministic, so a script, not a subagent.
  Output: `A \ B` (a designed test in no task) + `B \ A` (a task inventing a test); empty = pass.
  Block if non-empty.

- **Both checks share `scripts/extract-design-tests.sh`** to reconstruct the Test Design breadcrumb (`<describe> [> class] > it`), so the format lives in one place.

  Each scans only its relevant sections — never the whole file.
  Authors write the two lists with bare `it()` titles, then run `scripts/normalize-list-breadcrumbs.sh <plan>` (idempotent) to upgrade them to breadcrumbs before the checks run — never hand-typed.

- **How would this break?**: the boundary and failure-category checklists (per `spec-template.md`) must each be present.
  - Either instantiated with one row per coverage-taxonomy item marked `covered (<recap>)` / `N/A — <reason>`.
  - Or replaced wholesale by the opt-out `**DECISION:** Skip ... checklist because <reason>`.
  - A checklist section skipped outright — corner cases / failure modes written as flat ACs with neither checklist rows nor an opt-out line.
  - Fails self-review exactly like an empty placeholder row would.
  - Then, for every AC, ask "how would this break in production?" If no failure mode surfaces, flag as under-specified.
  - Fail-closed; runs regardless of either toggle.

- **PR dependencies form a DAG**: `scripts/check-pr-dag.sh <plan>` validates the PR Breakdown's `Depends on:` graph.
  Passes trivially when the section reads `Single PR.` (nothing to validate). Exit 1 blocks.

- **Task dependencies form a DAG**: `scripts/check-tasks-dag.sh <plan>` — the same three checks (cycle, dangling reference, duplicate label) over the Task Breakdown's `Depends on:` graph. Exit 1 blocks.

- **Both checks share `scripts/dag-check-helper.sh`** for the cycle/dangling/duplicate-label detection algorithm — only the markdown parsing (PR Breakdown's single-line entries vs. Task Breakdown's heading + block) differs between the two.

- **Every line traces to an AC** (toggle): every piece of machinery (abstraction, dependency, knob, extra layer) must trace to a spec AC or requirement.
  - Output: untraceable items (empty = pass). Block if non-empty — cut or earn an AC.

- **Right-sized plan** (toggle, advisory): pass user's request + spec + plan to a subagent.
  - Ask: does spec match request (no gold-plate), and is plan the simplest design meeting every AC?
  - Advisory even when its toggle is "yes" — surface findings and let the user decide, never blocks.

Why: catch them early; prevents "looks good, ship it" where ambiguity surfaces only in implementation.

#### Iteration rounds and drift (conditional — load only when they fire)

- **Delta-scoped re-review** — later self-review rounds scope the gates to what `diff` shows changed, not the whole doc again.
  - Load [`references/delta-scoped-rereview.md`](references/delta-scoped-rereview.md) on the second and later rounds.
- **Resolving spec/plan drift** — when plan_<slug>.md and spec_<slug>.md disagree, surface each conflict for the user before editing either doc.
  - Load [`references/resolving-drift.md`](references/resolving-drift.md) when a conflict surfaces.

## Guidelines

- **CRITICAL: Write spec_<slug>.md and plan_<slug>.md in English** — even when the team, repo, or conversation is in another language:
  - Covers everything in both docs: headings, prose, Given/When/Then, task titles, and planned-test breadcrumbs.
  - Match the code they drive — comments, `describe`/`it` titles, and symbols are English, so a same-language plan stays greppable and copy-paste-ready.
  - Localize only the durable decision docs (ADR/HLD/LLD) and the final PR description — those target human reviewers, not the codebase.
  - Why: a plan in one language driving code in another forces the implementer to translate every task title and test name before writing the actual symbol.

- **CRITICAL: spec_<slug>.md and plan_<slug>.md are session-scoped and untracked**.
  - Never reference them in committed artifacts (code comments, commit bodies, docs).
  - They stay local and get removed after the session; the next reader won't have them. Put the why in the code comment itself or other appropriated place.

- **CRITICAL: Keep spec and plan as lean as the change allows — brief and didactic beats exhaustive**:
  - Fill only the sections the change needs; use each section's `N/A — <reason>` escape freely instead of padding.
  - Short titles, one thought per bullet, terse Given/When/Then — optimize for a fast human read, not formal completeness.
  - Why: these are throwaway living docs, so verbosity taxes every re-read and buries the decisions that matter.

- **Cross-references inside the planning doc spell out the behavior — never cite `AC-N` IDs** (doc-standards' no-ID-references rule; the `### AC-N:` headings defining ACs are anchors, not references).
  - Why: specs/plans are scanned non-linearly; an ID reference adds lookup cost on every scan, while the behavior recap alone carries the meaning.

- **CRITICAL: Keep spec and plan up to date** -- Stale docs degrade `/create-pr`.

- **plan_<slug>.md tasks and their sub-steps become items on TaskList** — when running inline.
  - Under `/implement`, only parent tasks go on the orchestrator's TaskList; each task subagent tracks its own sub-steps in a private checklist file.

- **Tasks are commit-sized, never smaller**.

- **CRITICAL: Keep task status updated as you go, in both TaskList and plan_<slug>.md** — in plan_<slug>.md, status markers (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`, pending needs none) follow `/implement`'s status-markers section exactly.

- **After completing a task note deviations from the original plan**.

- **CRITICAL: When a doc warrants a diagram, follow the `mermaid-diagrams` skill**.

- **CRITICAL: Add a blank line between bullets (not sub-bullets)**:
  - This improve A LOT the readability
