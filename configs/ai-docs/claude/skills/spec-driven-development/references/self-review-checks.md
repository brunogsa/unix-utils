# Self-review checks — what each one means and what blocks

Read once a plan exists, before human review.

A run may write the plan alone (SKILL.md) — never report the absent spec as a finding.

## The two buckets

**Deterministic** — a script or renderer returns the verdict, so re-running costs nothing.

- Members: the mermaid fixer, the density checks, `check-sections.sh`, `check-test-distribution.sh`, `check-pr-dag.sh`, `check-tasks-dag.sh`, `check-ac-task-consistency.py`, plus, with a spec, `check-ac-coverage.sh` and `check-coverage-checklists.sh`.

- Dispatch the mermaid fixer at its agent file's pinned model — never name one here.
  - Why: `subagent-model-guard.py` hard-denies an override, so naming one is an instruction no caller can follow.

**Judged** — the *routed judge* decides; each round costs one dispatch over the whole documents.

Routing: `spec-reviewer` over a spec, `plan-reviewer` over a plan, and for a check over both, the judge of the doc it blocks, with the other as context.

Why never `spec-reviewer` over a plan: separate report rows, and a plan raises questions a spec never does — planned-test design, task decomposition, AC tracing.

- Members: the qualitative pass, the semantic half of "every AC has a test", "how would this break?", and the two toggled checks.
- Dispatch each at `effort=high`, overriding its `max` pin — both docs are lean, so `max` buys latency, not accuracy.

Run the deterministic bucket first, to exhaustion under SKILL.md's recovery loop, then the judged one.

Why: a deterministic gate catches structural breakage a judged dispatch would otherwise cost.

## Qualitative pass

Dispatch the routed judge (`title=Qualitative review of spec and plan`) over both docs; only the PR-size item blocks.

**Skip this checklist when `qualitative_pass` is false** (SKILL.md's toggles) — state it was skipped.
The dispatch still runs, carrying this file's always-on checks.

- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within one doc disagree, or does the plan contradict the spec?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition?
  - If decomposable, hand it back to the caller, who owns how sub-projects are recorded.
  - A caller that probed decomposition before the spec was written skips this item.

- **PR size**: does the work fit one reviewable PR, or stage into several per `plan-template.md`'s splitting rules?
  - An oversized PR blocks approval unless the user waives it.

- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker.
- **Completeness**: does the Testable Acceptance Criteria section cover every Goal, Success Metric/KPI, User Story and Non-Functional/Technical Requirement in the spec — plus every corner case and failure mode?

- **Human-Reviewable**: judge the body above `# Appendix`, against the 1–6 page guideline — could a novice succeed with just this plan and repo?

## Mechanical defects — one repaired, one reported

Both measure rather than judge — never inline.

- **Artifacts Valid**: is every mermaid diagram valid per `mmdc`? A failure routes to `agent(subAgent=mermaid-fixer, title=Fix spec/plan diagram)` on that doc path.

- **Density**: run `doc-standards`' `check-density.sh` and `check-bullet-gap.py` on the resolved doc paths.
  - Runs after mermaid validation: repairing a diagram adds lines density must measure.

  - On any violation, file ONE `[Scout]` entry naming the file and what is off standard.
  - No fixer — the user alone triages it.

**No toggle switches either off, but only the mermaid failure repairs itself.**

Why: an unrenderable diagram is broken outright, needing no judgment to fix. Reflowing prose is a judgment call that has split bullets mid-sentence.

## Every AC has a test

Every `### AC-N:` in the spec is proven by ≥1 test in the plan's AC-grouped coverage list (mechanics: `plan-template.md`).

- No spec — skip the mechanical half; the semantic half reads each task's `## Task Details` acceptance criteria and planned-test fields.

- Mechanical half — `scripts/check-ac-coverage.sh <plan> <spec>` checks coverage completeness and citation honesty (no truncated/invented breadcrumb); exit 1 blocks.

- Semantic half — runs after any mechanical half passes, never in parallel.
  - Dispatch `agent(subAgent=plan-reviewer, title=Judge AC-to-test coverage)` to judge whether each cited test *proves* its AC — the match no script can make.

- Output: orphan ACs + bogus citations (empty = pass); block approval if non-empty.

## Every template section is written

`check-sections.sh <doc> <template>` asserts every `## ` heading the template defines is present; exit 1 blocks, listing each absent one.

Never judge a missing section by eye.

Run it on the plan against `assets/plan-template.md`, and on any spec against `assets/spec-template.md`.

Heading presence only — an `N/A — <reason>` body satisfies it, a dropped heading does not, an author-added section never fails.

## Every test has a task

`check-test-distribution.sh <plan>` asserts set-equality between the Test Design breadcrumbs and tasks' planned-test lists (mechanics in `plan-template.md`).

Output: `A \ B` (designed, no task) + `B \ A` (invented test); empty = pass, block otherwise.

Both checks share `extract-design-tests.sh`; breadcrumbs are copied verbatim from its output, never hand-typed.

## How would this break?

Dispatch the routed judge (`title=Judge failure-mode coverage`) on the docs — never sweep inline; a listed failure mode's realness is a blind spot its author can't see.

With a spec, `scripts/check-coverage-checklists.sh <spec>` settles whether the spec appendix's `## Coverage Checklists` are instantiated; exit 1 blocks.

Then ask, for every AC, "how would this break in production?" — flag any with no surfaced failure mode. Fail-closed; no toggle removes it.

With no spec, skip that script; each task's `## Task Details` acceptance criteria is the AC set.

## PR and Task dependency DAGs

- `check-pr-dag.sh <plan>` validates the PR Breakdown's `Depends on:` graph (trivial on `Single PR.`); exit 1 blocks.
- `check-tasks-dag.sh <plan>` runs the same on the Task Breakdown's graph; exit 1 blocks.

## Every line traces to an AC (toggle)

Dispatch `agent(subAgent=plan-reviewer, title=Judge machinery-to-AC traceability)` with plan and spec: every piece of machinery must trace to a spec AC or requirement.

Output: untraceable items (empty = pass); block if non-empty — cut it, or earn an AC.

## Right-sized plan (toggle)

Dispatch `agent(subAgent=plan-reviewer, title=Judge spec/plan simplicity)` with the user's request + spec + plan — no gold-plating, simplest design meeting every AC.

Advisory even at toggle "yes" — surface findings, never block.
