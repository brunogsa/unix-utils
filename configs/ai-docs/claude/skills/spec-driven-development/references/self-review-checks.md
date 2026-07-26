# Self-review checks — what each one means and what blocks

Read this when self-review starts, once a plan exists and before any human is asked to review it.
SKILL.md carries the check table; this file carries what each check means and what blocks.

**A missing section may be a declared choice, not a defect.** The caller can request the light section set, described under SKILL.md's Section set heading.

It omits the spec's Context Diagram, Goals/KPIs, User Stories and Non-Functional requirements, plus the plan's General Flow, Side-effect report and Failure Handling.

Never report one of those absences as a finding, and don't ask for it back. Every check below still runs unchanged — light trims prose, never a gate.

Why it matters here: those headings are the first thing a fresh reviewer misses.
Without this note, the judged passes spend a whole round asking for sections the user already declined.

## Contents

- [Qualitative pass](#qualitative-pass)
- [Artifact fixers](#artifact-fixers)
- [Every AC has a test](#every-ac-has-a-test)
- [Every test has a task](#every-test-has-a-task)
- [How would this break?](#how-would-this-break)
- [PR and Task dependency DAGs](#pr-and-task-dependency-dags)
- [Every line traces to an AC (toggle)](#every-line-traces-to-an-ac-toggle)
- [Right-sized plan (toggle)](#right-sized-plan-toggle)

## Qualitative pass

Dispatch `agent(subAgent=deep-reviewer, title=Qualitative review of spec and plan)` to read both docs with fresh eyes and report findings. Only the PR-size item below blocks.

**Skip this dispatch when the caller's qualitative-pass toggle is off** — read it back from `/tmp/sdd_<session_id>.json`, never re-ask.
State in the output that it was skipped by request; the artifact fixers below still run.

- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within one doc disagree, or does the plan contradict the spec (spec assumptions overturned by planning, architectural choices superseding spec requirements)?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition?
  - If decomposable, write/update `scopes.md` next to the spec — one line per sub-project, each giving its name, a one-sentence purpose, and which other sub-projects it depends on.
  - Then re-run the qualitative pass only; the formal checks follow next regardless.
  - Why the file: a stale session loses the decomposition map, so the next planning run re-derives the same split from scratch.
- **PR size**: does the work fit one reviewable PR, or is it large enough to stage into several?
  - If large, **PR Breakdown** must split the tasks into an ordered PR sequence — vertical splits, each shipping its own tests + code + docs — not one oversized PR.
  - Blocking gate: an oversized PR blocks approval until the plan is split, or the user explicitly waives it for this run.
  - Felt anchor: reviewer defect-detection drops past ~400 lines of diff and hard above ~600 (SmartBear/Cisco; Google small-CL) — no code exists yet, so estimate by feel, never invent a line count.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does the Testable Acceptance Criteria section cover every Goal, Success Metric/KPI, User Story, and Non-Functional/Technical Requirement the spec actually carries — and every corner case and failure mode?
  - On a light-set spec most of those sections are absent by design, so judge coverage against what Background states plus the two checklists, which are never trimmed.
- **Human-Reviewable**: could a complete novice succeed with only this plan and the repo — no other context? Is the format pleasant enough to read that the user can verify you?

## Artifact fixers

Two dispatches that repair rather than judge, run serially after the qualitative pass and before the seven formal checks.

- **Artifacts Valid**: if any mermaid diagram exists, is it valid, verified via `mmdc`? A failing check routes to `agent(subAgent=mermaid-fixer, title=Fix spec/plan diagram)` on the resolved doc path — never fixed inline.

- **Density**: spawn `agent(subAgent=density-fixer, title=Fix spec/plan density)` on the resolved spec and plan paths — never check or rewrite density violations inline.
  - Runs after mermaid validation, since repairing a diagram adds lines the density check must then measure.

**No toggle switches these two off**, including the one that skips the qualitative pass.

Why: they repair a mechanical defect rather than judge content, so a caller has no rigor to trade away.
Nothing else in the run catches an unrenderable diagram or an over-cap line.

## Every AC has a test

Every `### AC-N:` in the spec is proven by ≥1 test in the plan's AC-grouped coverage list.

- Mechanical half — `scripts/check-ac-coverage.sh <plan> <spec>` checks completeness (every AC in the spec's Acceptance-Criteria section has a coverage header).
  - Honesty: every cited breadcrumb must exist verbatim among Test Design breadcrumbs; a `…`-truncated or invented citation won't match.
  - Exit 1 blocks.
- Semantic half — runs only after the mechanical half passes, never in parallel with it. Dispatch `agent(subAgent=deep-reviewer, title=Judge AC-to-test coverage)`.
  - It judges whether each cited test actually *proves* its AC — the match no script can make.
- Output: orphan ACs + bogus citations (empty = pass). Block plan approval if non-empty.

## Every test has a task

`scripts/check-test-distribution.sh <plan>` asserts set-equality between the Test Design breadcrumbs (A) and the union of tasks' `**Tests (planned)**:` lists (B).

Output: `A \ B` (a designed test in no task) + `B \ A` (a task inventing a test); empty = pass. Block if non-empty.

Both AC/test checks share `scripts/extract-design-tests.sh` to reconstruct the Test Design breadcrumb (`<describe> [> class] > it`), so the format lives in one place.

Authors write the two lists with bare `it()` titles, then run `scripts/normalize-list-breadcrumbs.sh <plan>` (idempotent) to upgrade them to breadcrumbs before the checks run — never hand-typed.

## How would this break?

Dispatch `agent(subAgent=deep-reviewer, title=Judge failure-mode coverage)` on both docs — never sweep this one inline.

Why dispatched: whether a listed failure mode is real, and whether a missing one matters, is exactly the blind spot the plan's own author cannot see.

The boundary and failure-category checklists (per `spec-template.md`) must each be present, either:

- Instantiated with one row per coverage-taxonomy item marked `covered (<recap>)` / `N/A — <reason>`, or
- Replaced wholesale by the opt-out `**DECISION:** Skip ... checklist because <reason>`.

Skipping a section outright fails self-review exactly like an empty placeholder row would.
"Skipped outright" means corner cases or failure modes written as flat ACs, with neither checklist rows nor an opt-out line.

Then, for every AC, ask "how would this break in production?" If no failure mode surfaces, flag it as under-specified.

Fail-closed; runs regardless of either toggle.

## PR and Task dependency DAGs

- `scripts/check-pr-dag.sh <plan>` validates the PR Breakdown's `Depends on:` graph. Passes trivially when the section reads `Single PR.` Exit 1 blocks.
- `scripts/check-tasks-dag.sh <plan>` runs the same three checks (cycle, dangling reference, duplicate label) over the Task Breakdown's `Depends on:` graph. Exit 1 blocks.

## Every line traces to an AC (toggle)

Dispatch `agent(subAgent=deep-reviewer, title=Judge machinery-to-AC traceability)` with the spec and the plan.

Every piece of machinery (abstraction, dependency, knob, extra layer) must trace to a spec AC or requirement.

Output: untraceable items (empty = pass). Block if non-empty — cut it or earn it an AC.

## Right-sized plan (toggle)

Dispatch `agent(subAgent=deep-reviewer, title=Judge spec/plan simplicity)` with the user's request + spec + plan. Ask: does the spec match the request (no gold-plating), and is the plan the simplest design meeting every AC?

Advisory even when its toggle is "yes" — surface findings and let the user decide, never blocks.
