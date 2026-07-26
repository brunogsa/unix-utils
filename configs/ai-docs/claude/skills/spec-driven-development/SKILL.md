---
name: spec-driven-development
description: "Conventions and self-review gates for spec_<slug>.md/plan_<slug>.md living docs — naming, discovery, templates, and the checks a plan must pass. Read by path from `brainstorm`, `design-docs`, and `plan-writer`; run `/brainstorm` to produce a spec/plan pair."
disable-model-invocation: true
---

# Spec-Driven Development

Conventions and gates for the two living documents in CWD that drive development, code review, and PR description generation.

This skill is a library, not a procedure.
It defines what the docs are called, how consumers find them, what shape they take, and which checks a plan must pass before a human sees it.
The procedure that produces them — interview, spec, plan, self-review, handoff — lives in the `brainstorm` skill.

Why the split: `/implement`, `/auto-review`, and `/create-pr` consume these docs without ever authoring one, so the authoring flow would be dead weight in their context.

**Callers reach this file by path, not by the Skill tool** — `Read ~/.claude/skills/spec-driven-development/SKILL.md`.
`disable-model-invocation: true` keeps a library nothing auto-triggers off the model's skill listing, which is also what takes its description out of every session's always-on budget.

## Documents

Two living documents in CWD. Templates live in `assets/` and are populated based on the user's input.

These throwaway docs feed from durable design docs (ADR / HLD / LLD).
Load the `design-docs` skill when authoring the spec, for the ownership + altitude rules that keep spec/plan from re-deriving them.

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

Uses BDD/TDD by default: load the `test-driven-development` skill once per task, before implementing it.
Opt-out per task with `**DECISION:** Skip TDD because <reason>` (inside the task itself).

## Self-review gates

Every plan passes a qualitative pass, then the artifact fixers, then the seven formal checks below, before a human is asked to review it.

**Read [`references/self-review-checks.md`](references/self-review-checks.md) when you run these** — it carries the qualitative-pass checklist, the two artifact fixers, and, per formal check, what it means and what blocks.

Three toggles the caller resolves *before* the plan exists and persists to `/tmp/sdd_<session_id>.json`.
Read the answers from that file when you reach the checks — never ask them here.

- Two of them switch off one formal check each — the last two rows of the table below.
- The third switches off the qualitative pass's `deep-reviewer` dispatch, and only that. The artifact fixers run regardless.

Why: asking after the plan is written lets a check get waived because it failed, rather than because it never applied.

Seven formal checks run in sequence (five always-on + the two toggles above):

| Check | Run by | Catches | Toggle? |
|---|---|---|---|
| Every AC has a test | `check-ac-coverage.sh`, then `deep-reviewer` | AC↔Test Design coverage | Always on |
| Every test has a task | `check-test-distribution.sh` | Test Design↔per-task assignment | Always on |
| How would this break? | manual sweep | checklist completeness + inversion sweep, merged | Always on |
| PR dependencies form a DAG | `check-pr-dag.sh` | cyclic, dangling, or duplicate PR-N label in the PR Breakdown | Always on |
| Task dependencies form a DAG | `check-tasks-dag.sh` | cyclic, dangling, or duplicate task id in the Task Breakdown | Always on |
| Every line traces to an AC | manual sweep | machinery↔AC traceability | Toggle |
| Right-sized plan | `deep-reviewer` | scope vs. request, simplest design | Toggle |

The five always-on checks, plus the Test Design authoring requirement itself, never become optional — they verify the plan is mechanically correct regardless of change size.

A toggled-off check or pass is omitted; self-review's output states explicitly what was skipped by request, so the reviewer never wonders why something is absent.

Why: catch them early; prevents "looks good, ship it" where ambiguity surfaces only in implementation.

### Iteration rounds and drift (conditional — load only when they fire)

- **Delta-scoped re-review** — later self-review rounds scope the gates to what `diff` shows changed, not the whole doc again.
  - Load [`references/delta-scoped-rereview.md`](references/delta-scoped-rereview.md) on the second and later rounds.
- **Formal-check recovery loop** — on a blocking failure, fix the issue, then re-run only that failed check plus the delta-scoped re-review above.
  - Never re-run the full seven-check block from the top — only the one check that failed, plus its delta re-review.
- **Snapshot hand-off loop** — before re-running the failed check, snapshot spec_<slug>.md + plan_<slug>.md to `/tmp/sdd-snapshots/` for the user's annotated-diff review.
  - Each round of AI fixes produces a fresh snapshot; the loop exits only when the user approves it.
- **Resolving spec/plan drift** — when plan_<slug>.md and spec_<slug>.md disagree, surface each conflict for the user before editing either doc.
  - Load [`references/resolving-drift.md`](references/resolving-drift.md) the moment a conflict first surfaces — any check, qualitative or formal; there is no fixed slot.

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

- **Cross-references inside the planning doc spell out the behavior — never cite `AC-N` IDs** (doc-standards' no-ID-references rule).
  - Anchors, not references — exempt from the ban: the spec's `### AC-N:` definition headings, and the plan's `- **AC-N**` coverage-list headers that `scripts/check-ac-coverage.sh` joins on.
  - Why: specs/plans are scanned non-linearly; an ID reference adds lookup cost on every scan, while the behavior recap alone carries the meaning.

- **CRITICAL: Keep spec and plan up to date** -- Stale docs degrade `/create-pr`.
  - Both files stay living through implementation; decisions are append-only past the divider that exists on both.

- **plan_<slug>.md tasks and their sub-steps become items on TaskList** — when running inline.
  - Under `/implement`, only parent tasks go on the orchestrator's TaskList; each task subagent tracks its own sub-steps in a private checklist file.

- **Tasks are commit-sized, never smaller**.

- **CRITICAL: Keep task status updated as you go, in both TaskList and plan_<slug>.md** — in plan_<slug>.md, status markers (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`, pending needs none) follow `/implement`'s status-markers section exactly.

- **After completing a task note deviations from the original plan**.

- **CRITICAL: When a doc warrants a diagram, follow the `mermaid-diagrams` skill**.

- **CRITICAL: Add a blank line between bullets (not sub-bullets)**:
  - This improve A LOT the readability
