# Writing the implementation plan

The procedure that turns an approved `spec_<slug>.md` into `plan_<slug>.md`. Read by path from `brainstorm`'s step 9, which dispatches it as a conversation fork.

## What running as a fork means here

You carry the whole brainstorm session — the interview, the trade-off discussion, the approach that won. Nothing was withheld from you.

That inheritance is a convenience, not a licence. The spec is what the next reader gets, and they will have none of it.

So a decision living only in your memory of the interview is, for every purpose that matters, missing — and this file's Boundaries treat it that way.

Fresh eyes still audit this plan: `brainstorm`'s step 10 sends it to a `deep-reviewer` that has never seen the session. Write for that reader, not for the one who remembers.

## Inputs

The caller gives you the spec file's path, and a plan output path.

- The plan output path is optional. When the caller gives one, write there.

- When the caller gives a slug instead, derive the output path from `SKILL.md`'s naming convention — the single definition of plan naming.

  - Deriving it there keeps one owner for the filename format, so a caller that never reads the library cannot spell a stale name.

You also receive an optional planning-conventions file (an ADR/HLD/LLD, or other naming constraints the plan must respect).

## Sources and tools

- `assets/plan-template.md` and the "Self-review gates" section of `SKILL.md`.

- The `task-breakdown` skill, which emits a prioritized breakdown artifact in `/tmp`.

- The relevant existing code the spec references.

## Procedure

1. Read the spec file in full, even where you remember writing it. Read any planning-conventions file the caller named.

   Reading it beats recalling it: the spec is the only version the reviewer and the implementer will ever see, and your memory of the interview will not flag where the two diverged.

2. Read `assets/plan-template.md` and the "Self-review gates" section of `SKILL.md`.

   The plan you write must satisfy the AC-coverage, test-distribution, and DAG checks listed there — the caller runs them on your output the moment you return.

   Also load the `task-breakdown` skill and run it over the spec's work — it emits a prioritized breakdown artifact in `/tmp`.

   Populate the plan's Task Breakdown section from that artifact, and sequence the PR Breakdown by the same priority order.

3. Read the relevant existing code the spec references — the modules, files, and patterns the plan's Task Breakdown depends on.

   Don't plan against a codebase you haven't looked at.

4. List what the spec doesn't carry:

   - Any acceptance criterion you can't resolve to a concrete approach.

   - Any non-functional/technical requirement left unaddressed.

   - Any design fork the plan needs decided that the spec leaves open — including one the interview settled but the spec never wrote down.

5. A gap never withholds the plan.

   Write the plan around each one and record it as a `**QUESTION:**` entry under the plan's Open Questions, stating exactly what's missing and what the plan can't settle without it.

   The caller closes them all in one batch before any expensive review runs, so a gap costs a question there rather than a refused plan here.

6. Write the plan at the resolved output path, following `assets/plan-template.md`'s structure.

   Include: Technical Approach, Threat Model, General Flow, Test Design (AC → test coverage), Task Breakdown, PR Breakdown, Open Questions, Technical Decisions.

   Write every one of them — a section the change doesn't need gets its own `N/A — <reason>` line, never a deletion. Drop nothing on a caller's say-so.

## Boundaries

- Never plan on a decision the spec doesn't record, including one you remember the interview settling.

  - Recording it as an Open Question is what routes it back into the spec, where the next reader will actually find it; planning on it silently leaves the spec wrong forever.

- Never guess at code you haven't read.

  - If the spec references a module, file, or pattern you can't locate, record that as an Open Question too — don't invent a plausible-sounding name.

- Write the plan in English regardless of the spec's language, matching `SKILL.md`'s convention.

- Every AC in the spec's Acceptance Criteria section must map to at least one test in the plan's Test Design section.

  - An unmapped AC is the same class of gap as missing spec content, so surface it rather than skip it silently.

- Never modify the spec file — you read it, you don't edit it.

  - A spec-shaped gap still goes in the plan's Open Questions; the caller decides how to fix the spec.

## Report format

"Plan written to `<path>`" + a one-paragraph summary of the approach and task count, then the count of Open Questions you recorded and a one-line statement of each.
