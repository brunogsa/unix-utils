# Self-review checks — what each one means and what blocks

Read once a plan exists, before a human reviews it.

**A missing section may be a declared choice, not a defect** — the caller may request the light section set (SKILL.md's Section set heading; `light-section-set.md` lists exactly what it drops).

Never report an absence as a finding or ask for it back — every check still runs unchanged; light trims prose, not gates.

## Contents

- [The two buckets](#the-two-buckets)
- [Qualitative pass](#qualitative-pass)
- [Artifact fixers](#artifact-fixers)
- [Every AC has a test](#every-ac-has-a-test)
- [Every test has a task](#every-test-has-a-task)
- [How would this break?](#how-would-this-break)
- [PR and Task dependency DAGs](#pr-and-task-dependency-dags)
- [Every line traces to an AC (toggle)](#every-line-traces-to-an-ac-toggle)
- [Right-sized plan (toggle)](#right-sized-plan-toggle)

## The two buckets

Every check sits in exactly one bucket; its run order, re-run policy and dispatch tier all follow from which.

**Deterministic** — a script or renderer returns the verdict, so re-running costs nothing.

- Members: the two artifact fixers, plus `check-ac-coverage.sh`, `check-test-distribution.sh`, `check-pr-dag.sh`, `check-tasks-dag.sh`.
- Dispatch each fixer at `model=sonnet, effort=high`, overriding its agent file's cheaper pin.
  - Why: a fixer edits prose a human reads next, so a mangled sentence costs more than the cheaper tier saves.

**Judged** — a `deep-reviewer` decides; each round costs one dispatch over both documents whole.

- Members: the qualitative pass, the semantic half of "every AC has a test", "how would this break?", and the two toggled checks.
- Dispatch each at `effort=high` (its agent's own pin, overriding `max`) — both documents are lean, so `max` buys latency on a short read, not accuracy.

Run the deterministic bucket first, to exhaustion — fix and re-run each failure alone until it passes — then dispatch the judged bucket.

Why that order: a deterministic gate is free to re-run, and catches structural breakage a judged pass would otherwise spend a dispatch rediscovering.

## Qualitative pass

Dispatch `agent(subAgent=deep-reviewer, title=Qualitative review of spec and plan)` to read both docs fresh and report findings; only the PR-size item blocks.

**Skip when the caller's qualitative-pass toggle is off** (SKILL.md's toggles) — state it was skipped.

- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within one doc disagree, or does the plan contradict the spec?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition?
  - If decomposable, record it per `decompose-scope.md`'s TaskList format, then re-run the qualitative pass only — the formal checks follow next regardless.

- **PR size**: does the work fit one reviewable PR, or is it large enough to stage into several per `plan-template.md`'s splitting rules?
  - An oversized PR (that file's felt-size anchor) blocks approval unless the user waives it.

- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker.
- **Completeness**: does the Testable Acceptance Criteria section cover every Goal, Success Metric/KPI, User Story, and Non-Functional/Technical Requirement the spec carries — and every corner case and failure mode?
  - On a light-set spec, judge coverage against Background plus the two never-trimmed checklists.

- **Human-Reviewable**: could a complete novice succeed with only this plan and the repo?

## Artifact fixers

Two dispatches that repair rather than judge; both sit in the deterministic bucket.

- **Artifacts Valid**: if any mermaid diagram exists, is it valid per `mmdc`? A failing check routes to `agent(subAgent=mermaid-fixer, title=Fix spec/plan diagram)` on the resolved doc path — never fixed inline.

- **Density**: spawn `agent(subAgent=markdown-standards-fixer, title=Fix spec/plan markdown)` on the resolved spec and plan paths — never check or rewrite density violations inline.
  - Runs after mermaid validation, since repairing a diagram adds lines density must then measure.

**No toggle switches these two off.**

Why: they repair a mechanical defect rather than judge content, so nothing else in the run catches an unrenderable diagram or an over-cap line.

## Every AC has a test

Every `### AC-N:` in the spec is proven by ≥1 test in the plan's AC-grouped coverage list (format and authoring mechanics: `plan-template.md`).

- Mechanical half — `scripts/check-ac-coverage.sh <plan> <spec>` checks coverage completeness and citation honesty (no truncated or invented breadcrumb); exit 1 blocks.

- Semantic half — runs only after the mechanical half passes, never in parallel.
  - Dispatch `agent(subAgent=deep-reviewer, title=Judge AC-to-test coverage)` to judge whether each cited test actually *proves* its AC — the match no script can make.

- Output: orphan ACs + bogus citations (empty = pass); block plan approval if non-empty.

## Every test has a task

`scripts/check-test-distribution.sh <plan>` asserts set-equality between the Test Design breadcrumbs and the union of tasks' planned-test lists (mechanics in `plan-template.md`).

Output: `A \ B` (designed, no task) + `B \ A` (task invents a test); empty = pass, block otherwise.

Both checks share `scripts/extract-design-tests.sh`; breadcrumbs come from `scripts/normalize-list-breadcrumbs.sh <plan>`, never hand-typed.

## How would this break?

Dispatch `agent(subAgent=deep-reviewer, title=Judge failure-mode coverage)` on both docs — never sweep inline; a listed failure mode's realness is a blind spot its own author can't see.

The boundary and failure-category checklists must each be instantiated or opted out exactly as `spec-template.md` defines.

Flat ACs with neither checklist rows nor an opt-out line fail self-review like an empty placeholder row would.

Then, for every AC, ask "how would this break in production?" — flag any AC with no surfaced failure mode as under-specified. Fail-closed; runs regardless of either toggle.

## PR and Task dependency DAGs

- `scripts/check-pr-dag.sh <plan>` validates the PR Breakdown's `Depends on:` graph (trivially passes when it reads `Single PR.`); exit 1 blocks.
- `scripts/check-tasks-dag.sh <plan>` runs the same checks on the Task Breakdown's graph; exit 1 blocks.

## Every line traces to an AC (toggle)

Dispatch `agent(subAgent=deep-reviewer, title=Judge machinery-to-AC traceability)` with spec and plan: every piece of machinery must trace to a spec AC or requirement.

Output: untraceable items (empty = pass); block if non-empty — cut it or earn it an AC.

## Right-sized plan (toggle)

Dispatch `agent(subAgent=deep-reviewer, title=Judge spec/plan simplicity)` with the user's request + spec + plan — no gold-plating in the spec, simplest design meeting every AC in the plan.

Advisory even when its toggle is "yes" — surface findings, let the user decide; never blocks.
