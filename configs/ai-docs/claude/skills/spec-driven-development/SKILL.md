---
name: spec-driven-development
description: "Spec-driven development with spec_<slug>.md/plan_<slug>.md as session-scoped, untracked living docs. USE PROACTIVELY when planning a non-trivial feature or breaking work into commits. For Socratic idea-refinement, use `brainstorm` instead."
disable-model-invocation: false
---

# Spec-Driven Development

Lightweight workflow using two living documents in CWD to guide development, code review, and PR description generation.

## Pre-flight interview (the first thing, every run)

The moment this skill starts — before any spec or plan work — ask one message with two independent yes/no toggles:

- **"Every line traces to an AC?"**
- **"Right-sized plan?"**

UNLESS `brainstorm` drives the run — it `@`-imports this skill at load time, so "starts" would otherwise mean brainstorm's first step.
There the toggles fire at the top of brainstorm's "Interview the user" step instead, before its first question round.
Why: brainstorm reads any existing spec and probes scope before that, and firing the toggles ahead of its scope probe splits one interview into two disjoint question moments.

They govern the two toggleable self-review checks (see "Self-review both spec and plan" below).
Answered fresh each run — never reused from a previous run, never written to `plan_<slug>.md` or any committed state file.

The moment the answers arrive, persist them to `/tmp/sdd_<session_id>.json` — one SDD run per session, so the session id alone keys the file.
The self-review checks consume them only after `plan-writer` returns, and a compaction in that window must not lose them.
Writing them to `/tmp` for this run only is not the cross-run persistence banned above.

## Documents

Two living documents in CWD. Templates live in `assets/` and are populated based on the user's input.

These throwaway docs feed from durable design docs (ADR / HLD / LLD).
Load the `design-docs` skill at step 0 (spec authoring) for the ownership + altitude rules that keep spec/plan from re-deriving them.

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

Uses BDD/TDD by default: load the `test-driven-development` skill at step 4 (per TaskCreate item, before implementing it).
Opt-out per task with `**DECISION:** Skip TDD because <reason>` (inside the task itself).

## Lifecycle

0. User creates spec_<slug>.md with initial prompt/notes (or `/brainstorm` refines it).
1. Dispatch the `plan-writer` subagent to write plan_<slug>.md from spec_<slug>.md alone — same mechanism regardless of whether the spec came from `/brainstorm`, plan mode, or a direct request.
   - Exception: a plan requested straight from a prompt with no spec_<slug>.md on disk skips plan-writer (spec-only input) — write it in-session instead.
2. AI Self-review — qualitative pass, then seven formal checks (five always-on, two toggled by the pre-flight interview at skill start).
3. User reviews and approves — then run `/clear` and invoke `/implement` in a fresh session; never continue in this one.
   - Why: `/implement` re-grounds from spec_<slug>.md and plan_<slug>.md on disk, so carrying this session forward only blurs planning-vs-execution cost.
4. Each plan_<slug>.md task becomes a TaskCreate item — owned by `/implement` in the fresh post-`/clear` session; listed here for lifecycle continuity only.
5. Both files updated as work progresses (living docs); decisions are append-only past the divider that exists on both spec_<slug>.md and plan_<slug>.md.
6. User runs `/refactor` then `/auto-review` when the entire feature is developed; fixes are addressed, if any.
7. User manually review the code. More fixes, if any.
8. `/create-pr` uses both spec_<slug>.md and plan_<slug>.md to generate a rich PR description.
9. Self-improving loop: user runs `/improve-from-user` then `english-coach` skills so both AI and human learn.

### Self-review both spec and plan before handing it back (step 2 detail)

Step 2 runs a qualitative pass first, then the seven formal checks below.

**Read [`references/self-review-checks.md`](references/self-review-checks.md) when you reach this step** — it carries the qualitative-pass checklist and, per formal check, what it means and what blocks.

The two toggles were already asked at skill start — the "Pre-flight interview" section at the top of this SKILL.md — and persisted to `/tmp/sdd_<session_id>.json`.
Read them from that file here; never re-ask them at this point.

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

A toggled-off check is omitted from that pass; self-review's output states explicitly which checks were skipped by request, so the reviewer never wonders why something is absent.

Why: catch them early; prevents "looks good, ship it" where ambiguity surfaces only in implementation.

#### Iteration rounds and drift (conditional — load only when they fire)

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

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the lifecycle above wins; regenerate it whenever the flow changes.
