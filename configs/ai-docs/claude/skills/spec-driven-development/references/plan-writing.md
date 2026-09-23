# Writing the implementation plan

Turns an approved `spec_<slug>.md` into `plan_<slug>.md`. Read by path from the `plan-writer` agent, dispatched by `brainstorm`'s step 9, and by whoever fills in `assets/plan-template.md`, since it carries no rules.

Fresh eyes still audit this plan — `brainstorm`'s step 10 sends it to a `plan-reviewer` who never saw the session.

Never copy guidance text from this reference or the template into the written doc — the doc holds content only.

Also read `references/plan-tasks-and-appendix.md` for the Test Design, Task Breakdown, PR Breakdown, and Decision logs sections — split out to keep each file under its word budget.

## Inputs

The caller gives you the spec file's path and, optionally, a plan output path — write there when given, else derive it from a slug via `SKILL.md`'s naming convention.

You may receive a planning-conventions file (ADR/HLD/LLD or other naming constraints) the plan must respect.

## Sources and tools

- `assets/plan-template.md` and the "Self-review gates" section of `SKILL.md`.
- The `task-breakdown` skill, which emits a prioritized breakdown artifact in `/tmp`.
- The relevant existing code the spec references.

## Procedure

1. Read the spec file in full, even the parts you wrote, plus any planning-conventions file named — recall won't flag where memory and spec diverged.

2. Read `assets/plan-template.md` and `SKILL.md`'s "Self-review gates" — your output must pass the AC-coverage, test-distribution, and DAG checks.

   Load `task-breakdown` over the spec's work per `references/plan-tasks-and-appendix.md`'s Task Breakdown section.

3. Read the existing code the spec references — never plan against code you haven't looked at.

4. List what the spec doesn't carry: an AC you can't resolve to a concrete approach, an unaddressed non-functional/technical requirement, or a design fork the spec leaves open.

   Include one the interview settled but never recorded.

5. A gap never withholds the plan — write around it and record a `**QUESTION:**` under Open Questions, stating what's missing.

   The caller closes every question in one batch before any expensive review runs.

6. Write the plan at the resolved path per `assets/plan-template.md`'s structure, writing every section. A section the change doesn't need still gets its own `N/A — <reason>` line, never a deletion.

## Body/appendix contract

The human body is everything above the literal `# Appendix` heading. Appendix `## ` headings come heading-first, with a `<details>` collapsible inside them — never a `<details>` wrapping an entire `## ` heading, so a script grepping `## ` still finds every section, with its exact text and level.

## Size guideline

Keep the human body (everything above `# Appendix`) to 1–6 pages (~500–3,000 words) depending on the problem; simpler and shorter is better. A soft guideline, never a gate.

Keep each task's entry to ≤256 words total, counting the body's Task Breakdown entry (title, Depends on, Brief Description, Commits sketch) together with the matching Appendix Task Details entry (AC, Verification, Files) — the two spans of one task, not two separate budgets. Together they replace the old single 240–406-word median entry, which held a per-task `Tests (planned)` field now folded into Test Design.

## Spec line

The body opens with `Spec: <link or reference to the paired spec file>`. On a plan-only run with no spec, write `Spec: N/A — plan-only run` instead.

## N/A escapes

Every section keeps its heading even when it doesn't apply — write `N/A — <reason>` as the body instead of deleting the section.

- Technical Approach & High Level Architecture, General Flow: for a trivial or no-flow change.

- Threat Model: no trust boundary crossed.

- Task Breakdown: when every task is independent, or there's only one task, write `N/A — no task dependencies` in place of the dependency DAG.

- PR Breakdown: default is **one plan = one PR** — most plans write "Single PR." and move on.

- PR Breakdown DAG: for a "Single PR." plan, or a multi-PR plan where every PR is independent, write `N/A — no PR dependencies`.

- Test Design: for a pure refactor, config edit, or similar no-behavior-change work, mark "N/A" with a short reason.

## Diagram conventions

Follow `mermaid-diagrams`; lead Technical Approach and General Flow each with a diagram — faster to scan than prose.

- **Technical Approach**: flowchart or C4L1 diagram, kept simple; prose only for trade-offs it can't convey.
- **General Flow**: sequence diagram or flowchart of execution start, data carried, and module order — legible without codebase knowledge, no code.

## Threat Model

The five checkbox lines already in the template, plus trust boundaries marked as dashed subgraphs on the Technical Approach diagram — never a second diagram:

```
subgraph trust_public["trust: public internet"]
subgraph trust_db["trust: service account"]
```

Tick every box this change touches. Each ticked box carries its mitigation on the same line, appended after the box's text. An unmitigated threat becomes an Open Question, never a bullet — it blocks approval instead of shipping as an unvoted risk.

The five boxes map to `code-review-pipeline/references/review-checklists.md`'s Security Checklist vocabulary: untrusted input → injection, XSS/output-encoding gaps, unsafe deserialization. Permissions → authn/authz. Personal data → the data-handling side of secret/credential exposure. A secret/credential → secret and credential exposure. Code/shell/SQL built from input → SSRF/RCE, unsafe eval or dynamic execution.

Reuse this vocabulary rather than inventing a second one — a second taxonomy would drift from the one review applies.

The old `asset ← threat ⇒ mitigation → AC-N` line format is dropped — the per-box mitigation above replaces it.

## Boundaries

- Never plan on an undocumented decision, even one the interview settled — record it as an Open Question, or the spec stays wrong.

- Never guess at code you haven't read — an unlocatable module, file, or pattern is an Open Question, not an invented name.

- Write the plan in English regardless of the spec's language, per `SKILL.md`.

- Every spec AC must map to one Test Design test — an unmapped AC is the same gap as missing spec content.

- Never modify the spec file — a spec-shaped gap goes in Open Questions; the caller fixes the spec.

## Report format

"Plan written to `<path>`" + a one-paragraph approach/task-count summary, then the Open Questions count with a one-line statement each.
