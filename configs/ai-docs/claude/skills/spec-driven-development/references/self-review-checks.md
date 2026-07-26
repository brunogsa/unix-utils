# Self-review checks — what each one means and what blocks

Read this when self-review starts, once a plan exists and before any human is asked to review it.
SKILL.md carries the check table; this file carries what each check means and what blocks.

## Contents

- [Qualitative pass](#qualitative-pass)
- [Every AC has a test](#every-ac-has-a-test)
- [Every test has a task](#every-test-has-a-task)
- [How would this break?](#how-would-this-break)
- [PR and Task dependency DAGs](#pr-and-task-dependency-dags)
- [Every line traces to an AC (toggle)](#every-line-traces-to-an-ac-toggle)
- [Right-sized plan (toggle)](#right-sized-plan-toggle)

## Qualitative pass

Dispatch the `deep-reviewer` agent to read both docs with fresh eyes and report findings. Only the PR-size item below blocks.

- **Placeholders**: any TBD, TODO, XXX or vague requirements lingering?
- **Contradictions**: do sections within one doc disagree, or does plan_<slug>.md contradict spec_<slug>.md (spec assumptions overturned by planning, architectural choices superseding spec requirements)?
- **Scope**: is this still single-spec-sized, or did the interview reveal hidden decomposition?
  - If decomposable, write/update `scopes.md` next to the spec — one line per sub-project, each giving its name, a one-sentence purpose, and which other sub-projects it depends on.
  - Then re-run the qualitative pass only; the formal checks follow next regardless.
  - Why the file: a stale session loses the decomposition map, so the next planning run re-derives the same split from scratch.
- **PR size**: does the work fit one reviewable PR, or is it large enough to stage into several?
  - If large, **PR Breakdown** must split the tasks into an ordered PR sequence — vertical splits, each shipping its own tests + code + docs — not one oversized PR.
  - Blocking gate: an oversized PR blocks approval until the plan is split, or the user explicitly waives it for this run.
  - Felt anchor: reviewer defect-detection drops past ~400 lines of diff and hard above ~600 (SmartBear/Cisco; Google small-CL) — no code exists yet, so estimate by feel, never invent a line count.
- **Ambiguity**: could any requirement be read two ways? Pick one and make it explicit, or leave a `**QUESTION:**` marker for the user.
- **Completeness**: does the Testable Acceptance Criteria section cover every Goal, Success Metric/KPI, User Story, and Non-Functional/Technical Requirement — and every corner case and failure mode?
- **Human-Reviewable**: could a complete novice succeed with only this plan and the repo — no other context? Is the format pleasant enough to read that the user can verify you?
- **Artifacts Valid**: if any mermaid diagram exists, is it valid, verified via `mmdc`? A failing check routes to the `mermaid-fixer` subagent on the resolved doc path — never fixed inline.
- **Density**: spawn the `density-fixer` subagent on the resolved `spec_<slug>.md` / `plan_<slug>.md` paths — never check or rewrite density violations inline.
  - Runs last in the qualitative pass, after every content check above (including mermaid validation), before the seven formal checks begin.
  - The subagent runs `check-density.sh` and applies the `density-rules.md` rewrite patterns until exit 0, without dropping information.

## Every AC has a test

Every `### AC-N:` in the spec is proven by ≥1 test in the plan's AC-grouped coverage list.

- Mechanical half — `scripts/check-ac-coverage.sh <plan> <spec>` checks completeness (every AC in the spec's Acceptance-Criteria section has a coverage header).
  - Honesty: every cited breadcrumb must exist verbatim among Test Design breadcrumbs; a `…`-truncated or invented citation won't match.
  - Exit 1 blocks; the semantic half runs only after this passes.
- Semantic half — sequential after the mechanical half, never parallel. Dispatch `deep-reviewer` to judge whether each cited test actually *proves* its AC — the match no script can make.
- Output: orphan ACs + bogus citations (empty = pass). Block plan approval if non-empty.

## Every test has a task

`scripts/check-test-distribution.sh <plan>` asserts set-equality between the Test Design breadcrumbs (A) and the union of tasks' `**Tests (planned)**:` lists (B).

Deterministic, so a script, not a subagent. Output: `A \ B` (a designed test in no task) + `B \ A` (a task inventing a test); empty = pass. Block if non-empty.

Both AC/test checks share `scripts/extract-design-tests.sh` to reconstruct the Test Design breadcrumb (`<describe> [> class] > it`), so the format lives in one place.

Each scans only its relevant sections — never the whole file.

Authors write the two lists with bare `it()` titles, then run `scripts/normalize-list-breadcrumbs.sh <plan>` (idempotent) to upgrade them to breadcrumbs before the checks run — never hand-typed.

## How would this break?

The boundary and failure-category checklists (per `spec-template.md`) must each be present, either:

- Instantiated with one row per coverage-taxonomy item marked `covered (<recap>)` / `N/A — <reason>`, or
- Replaced wholesale by the opt-out `**DECISION:** Skip ... checklist because <reason>`.

A checklist section skipped outright fails self-review exactly like an empty placeholder row would.

"Skipped outright" means corner cases / failure modes written as flat ACs, with neither checklist rows nor an opt-out line.

Then, for every AC, ask "how would this break in production?" If no failure mode surfaces, flag it as under-specified.

Fail-closed; runs regardless of either toggle.

## PR and Task dependency DAGs

- `scripts/check-pr-dag.sh <plan>` validates the PR Breakdown's `Depends on:` graph. Passes trivially when the section reads `Single PR.` Exit 1 blocks.
- `scripts/check-tasks-dag.sh <plan>` runs the same three checks (cycle, dangling reference, duplicate label) over the Task Breakdown's `Depends on:` graph. Exit 1 blocks.

Both share `scripts/dag-check-helper.sh` for the detection algorithm — only the markdown parsing differs (PR Breakdown's single-line entries vs. Task Breakdown's heading + block).

## Every line traces to an AC (toggle)

Every piece of machinery (abstraction, dependency, knob, extra layer) must trace to a spec AC or requirement.

Output: untraceable items (empty = pass). Block if non-empty — cut it or earn it an AC.

## Right-sized plan (toggle)

Dispatch the `deep-reviewer` agent with the user's request + spec + plan. Ask: does the spec match the request (no gold-plating), and is the plan the simplest design meeting every AC?

Advisory even when its toggle is "yes" — surface findings and let the user decide, never blocks.
