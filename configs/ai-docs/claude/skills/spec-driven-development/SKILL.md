---
name: spec-driven-development
description: "Self-review gates and living-doc conventions for spec_<slug>.md/plan_<slug>.md, run before a human reviews the plan. Read by path from brainstorm, design-docs, plan-writer — never model-invoked; run /brainstorm to produce them."
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

Downstream skills (`/implement`, `/auto-review`, `/create-pr`, `/quality-gate`) discover the files by glob in CWD (top-level only):

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

Resolve with this shared baseline:

- **Exactly one spec and one plan** → use both; print the resolved paths, no prompt.
- **Multiple specs or multiple plans** → never guess; the matches get listed numbered for a human to pick from.

Everything else diverges per consumer: the bullets below name those divergences, and each consumer's own `SKILL.md` is canonical for anything they leave out.

- **When and how that pick is asked.** `/auto-review` and `/quality-gate` prompt inline; `/implement` and `/create-pr` fold it into their one up-front interview instead.
- **What happens with no human to ask** — `/quality-gate` under either `--auto-solve` or `--report-only` proceeds without that kind rather than stalling on a prompt.

- **Zero matches, or only one kind.** Only `/implement` stops without a plan; every other consumer degrades to the diff alone.

### Every template section always gets written

Both templates below are one fixed section set — there is no reduced variant, and a caller never picks which sections to write.

Trim inside a section with its own `N/A — <reason>` escape instead, per the Guidelines' lean rule.

Why no variant: a dropped section is invisible to the reader, where an `N/A` line states that the author considered it and ruled it out.

### A plan may exist without a spec

A caller may write the plan alone — `brainstorm`'s `light` mode does exactly that.

Such a plan writes `N/A — plan-only run` on its `Spec:` line, and carries each task's acceptance criteria in that task's own `**Testable Acceptance criteria**` field.
In place of the Test Design section's AC → test coverage list it writes `N/A — no spec`.

It cannot run `check-ac-coverage.sh`, which takes both documents — so with no spec there is nothing for that coverage list to cite and no gate left to read it.

Why the spec is the droppable one: every downstream consumer degrades gracefully to "no spec", while `/implement` — the one that writes code — refuses to run without a plan.

### spec_<slug>.md (why / what)

Captures background, goals, requirements, testable acceptance criteria and functional decisions.
Owned by the user, refined collaboratively.

Read `./assets/spec-template.md` when starting the spec phase, and populate it.

### plan_<slug>.md (how / tasks)

Technical approach and task breakdown. Generated from spec_<slug>.md (or directly from prompt).

Read `./assets/plan-template.md` when starting the plan phase, and populate it.

The Task Breakdown section is populated from the artifact the `task-breakdown` skill emits.
That skill owns task ordering (unblockers first, riskiest with a proof of concept next), thin contract-task extraction, and sub-step splitting.
The PR Breakdown mirrors the same priority order one level up.
The template instructs loading it where each section is authored, so any plan author picks it up without this library saying more.

Uses BDD/TDD by default: load the `test-driven-development` skill once per task, before implementing it.
Opt out per task with `**Tests (planned)**: N/A — <reason>` inside the task — the one opt-out with a runner, which `scripts/extract-planned-tests-for-task.sh` short-circuits on.

## Self-review gates

Every plan passes every gate below before a human is asked to review it.

The gates split into two buckets: **deterministic** — a script or a renderer returns the verdict — and **judged**, where a `deep-reviewer` decides.

Run the deterministic bucket first and as often as needed; the judged bucket runs as few times as the caller will accept.

**Read [`references/self-review-checks.md`](references/self-review-checks.md) when you run these.**
It carries the bucket membership and dispatch tiers, the qualitative-pass checklist, the two artifact fixers, and, per formal check, what it means and what blocks.

Three toggles the caller resolves *before* the plan exists and persists to `/tmp/sdd_<session_id>.json`.
Read the answers from that file when you reach the checks — never ask them here.

A caller may also resolve none of them and run the deterministic bucket alone — `brainstorm`'s `light` mode does.
Treat all three as off in that case, and skip `check-ac-coverage.sh` too, since it takes both a plan and a spec.

Name the three fields exactly `traces_to_ac`, `right_sized`, and `qualitative_pass`, so writer and reader never have to guess the same key.

- The first two switch off one formal check each — the last two rows of the table below.
- `qualitative_pass` switches off the qualitative pass's checklist, and only that. The artifact fixers run regardless, and so does every always-on check.

Why: asking after the plan is written lets a check get waived because it failed, rather than because it never applied.

Eight formal checks run in sequence (six always-on + the two toggles above):

| Check | Run by | Catches | Toggle? |
|---|---|---|---|
| Every template section is written | `check-sections.sh` | a dropped `## ` heading in either doc | Always on |
| Every AC has a test | `check-ac-coverage.sh`, then `deep-reviewer` | AC↔Test Design coverage | Always on |
| Every test has a task | `check-test-distribution.sh` | Test Design↔per-task assignment | Always on |
| How would this break? | `deep-reviewer` | checklist completeness + inversion sweep, merged | Always on |
| PR dependencies form a DAG | `check-pr-dag.sh` | cyclic, dangling, or duplicate PR-N label in the PR Breakdown | Always on |
| Task dependencies form a DAG | `check-tasks-dag.sh` | cyclic, dangling, or duplicate task id in the Task Breakdown | Always on |
| Every line traces to an AC | `deep-reviewer` | machinery↔AC traceability | Toggle |
| Right-sized plan | `deep-reviewer` | scope vs. request, simplest design | Toggle |

The six always-on checks, plus the Test Design authoring requirement itself, never become optional — they verify the plan is mechanically correct regardless of change size.

No toggle removes one, including the two judged ones — "How would this break?" and the semantic half of "Every AC has a test".
The single way those two go unrun is the deterministic-bucket-alone run above, which has no judged bucket to run them in.

A toggled-off check or pass is omitted; self-review's output states explicitly what was skipped by request, so the reviewer never wonders why something is absent.

Why: catch them early; prevents "looks good, ship it" where ambiguity surfaces only in implementation.

### Iteration rounds and drift (conditional — load only when they fire)

- **Formal-check recovery loop** — on a blocking failure, fix the issue, then re-run only the check that failed.
  - Never re-run the full eight-check block from the top; the other seven already passed over text the fix didn't touch.

- **Resolving spec/plan drift** — when the plan and the spec disagree, surface each conflict for the user before editing either doc.
  - Load [`references/resolving-drift.md`](references/resolving-drift.md) the moment a conflict first surfaces — any check, qualitative or formal; there is no fixed slot.

## Guidelines

- **CRITICAL: Write the spec and the plan in English** — even when the team, repo, or conversation is in another language:
  - Covers everything in both docs: headings, prose, Given/When/Then, task titles, and planned-test breadcrumbs.
  - Match the code they drive — comments, `describe`/`it` titles, and symbols are English, so a same-language plan stays greppable and copy-paste-ready.
  - Localize only the durable decision docs (ADR/HLD/LLD) and the final PR description — those target human reviewers, not the codebase.
  - Why: a plan in one language driving code in another forces the implementer to translate every task title and test name before writing the actual symbol.

- **CRITICAL: The spec and the plan are session-scoped and untracked**.
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

- **The plan's tasks and their sub-steps become items on TaskList** — when running inline.
  - Under `/implement`, only parent tasks go on the orchestrator's TaskList; each task subagent tracks its own sub-steps in a private checklist file.

- **Tasks are commit-sized, never smaller**.

- **CRITICAL: Keep task status updated as you go, in both TaskList and the plan** — in the plan, status markers (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`, pending needs none) follow `/implement`'s status-markers section exactly.

- **After completing a task note deviations from the original plan**.

- **When a doc warrants a diagram, follow the `mermaid-diagrams` skill** — the self-review's Artifacts Valid check validates every diagram via `mmdc`.

- **Bullet gaps follow `doc-standards`' rule** — gap any bullet that has a sub-bullet or exceeds 80% of the density cap.
  - The self-review's `markdown-standards-fixer` dispatch verifies and repairs both this and the density cap deterministically.
