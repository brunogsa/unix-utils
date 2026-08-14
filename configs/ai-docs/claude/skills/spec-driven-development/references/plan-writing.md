# Writing the implementation plan

Turns an approved `spec_<slug>.md` into `plan_<slug>.md`. Read by path from `brainstorm`'s step 9, as a conversation fork.

Also read once by whoever fills in `assets/plan-template.md`, since that skeleton carries no rules.

## What running as a fork means here

You carry the whole brainstorm session — interview, trade-offs, the approach that won. That's a convenience, not a licence: the spec is what the next reader gets.

A decision living only in memory is missing — see Boundaries.

Fresh eyes still audit this plan: `brainstorm`'s step 10 sends it to a `deep-reviewer` that never saw the session.

## Inputs

The caller gives you the spec file's path and, optionally, a plan output path — write there when given, or derive it from a given slug via `SKILL.md`'s naming convention.

You may receive a planning-conventions file (ADR/HLD/LLD or other naming constraints) the plan must respect.

## Sources and tools

- `assets/plan-template.md` and the "Self-review gates" section of `SKILL.md`.
- The `task-breakdown` skill, which emits a prioritized breakdown artifact in `/tmp`.
- The relevant existing code the spec references.

## Procedure

1. Read the spec file in full, even where you remember writing it, plus any planning-conventions file named.

   Recall won't flag where memory and spec diverged.

2. Read `assets/plan-template.md` and `SKILL.md`'s "Self-review gates" — the plan must pass the AC-coverage, test-distribution, and DAG checks run on your output.

   Load `task-breakdown` over the spec's work per this file's Task Breakdown section below.

3. Read the existing code the spec references. Don't plan against a codebase you haven't looked at.

4. List what the spec doesn't carry:
   - An AC you can't resolve to a concrete approach.
   - An unaddressed non-functional/technical requirement.
   - A design fork the spec leaves open — including one the interview settled but never recorded.

5. A gap never withholds the plan — write around it and record a `**QUESTION:**` under Open Questions, stating what's missing.

   The caller closes every question in one batch before any expensive review runs.

6. Write the plan at the resolved path, following `assets/plan-template.md`'s structure — write every section.

   One the change doesn't need still gets its own `N/A — <reason>` line, never a deletion.

## Diagram conventions

Lead Technical Approach and General Flow each with a diagram — faster to scan than prose. Follow `mermaid-diagrams`.

- **Technical Approach**: flowchart or C4L1 context diagram, kept simple; prose only for trade-offs it can't convey.
- **General Flow**: sequence diagram or flowchart of where execution starts, what data it carries, which modules run in order — legible without codebase knowledge, no code.

## Threat Model vocabulary

Reuse the vocabulary from `code-review-pipeline/references/review-checklists.md#Security Checklist` — injection, output-encoding gaps, unsafe deserialization, authn/authz, secret exposure, SSRF, unsafe dynamic execution.

A second taxonomy would drift from the one the review actually applies.

An unmitigated threat is an Open Question, not a table row — that blocks approval instead of shipping as an unvoted risk.

## Task Breakdown section

Load `task-breakdown` before authoring — it orders tasks (unblockers first, riskiest PoC next), extracts thin contract tasks, splits sub-steps, and emits a `/tmp` artifact.

Populate from that artifact: order becomes the numbering (execution, not narrative, order), links become each `Depends on:`, sub-steps become the title breadcrumb and commit sketch.

Lead with a task-dependency DAG (mermaid, `mmdc`-validated) when a task names a real dependency; else `N/A — no task dependencies`.

Each task produces at least one base commit (tests, code, IaC/docs together; RED/GREEN lives inside it).

At execution, a refactor/scout/drift/`/auto-review` follow-up becomes its own extra commit; a substantial addition becomes a new peer task. Refactors are isolated tasks by definition.

Sub-step breadcrumb: optional, semicolon-separated parenthetical after the title — `### N. Title (sub-step; sub-step)`; keep ~4 items or split the task.

## Files and Commits fields

`Files (logical order)` grounds the task's subagent as its starting set, so it skips re-discovering the map; keep accurate, though the subagent may touch more.

`Commits (sketch, minimum)` is a floor. Drift fixes, scout findings, refactor sub-steps, and `/auto-review` follow-ups become extra commits, each tagged `[Drift]`/`[Scout]`/`[Refactor]`.

## PR Breakdown section

Split past one-plan-one-PR when the work is too large to review well in one sitting.

Felt size (guide, not gate): defect-detection drops sharply past ~400 diff lines, falls off above ~600 (SmartBear/Cisco study; Google guidance).

No code exists yet — estimate by feel, never invent a line number.

Splitting rules:
- Vertical, never horizontal — each PR ships its own tests+code+docs+infra; never "PR-1 = tests, PR-2 = code."
- Prefer independent PRs; a dependent sequence is fine.
- Each PR independently reviewable/mergeable, in order if dependent.
- Sequence by `task-breakdown`'s priorities — unblockers and riskiest PoC first.
- Don't over-split (~50-line floor) — catch one giant PR, not many tiny ones.

One `### PR-N.` heading per PR, one level above Task Breakdown's `### N.`.

The orchestrating agent, never the author, writes two fields inline, absent until then:
- `[<status>]` (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`) after `PR-N.`, at batch-end.
- Backtick-wrapped `**Branch**:`, once that PR's batch pushes — load-bearing: `parse-pr-breakdown.sh` reads the branch name between the backticks.

Each field is its own line; parsers read the first found per PR. Free prose after is for the reviewer.

Lead the PR headings with a PR-dependency DAG (mermaid, `mmdc`-validated) when any PR names a real dependency; else `N/A — no PR dependencies`.

## Boundaries

- Never plan on a decision the spec doesn't record, including one the interview settled.

  - Recording it as an Open Question routes it into the spec; planning on it leaves the spec wrong forever.

- Never guess at code you haven't read — an unlocatable module, file, or pattern is an Open Question, not an invented name.

- Write the plan in English regardless of the spec's language, per `SKILL.md`.

- Every spec AC must map to one Test Design test — an unmapped AC is the same gap class as missing spec content.

- Never modify the spec file — a spec-shaped gap goes in Open Questions; the caller fixes the spec.

## Report format

"Plan written to `<path>`" + a one-paragraph summary of approach and task count, then the Open Questions count and a one-line statement of each.
