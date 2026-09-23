# Writing the implementation plan

Turns an approved `spec_<slug>.md` into `plan_<slug>.md`. Read by path from the `plan-writer` agent, dispatched by `brainstorm`'s step 9, and by whoever fills in `assets/plan-template.md`, since it carries no rules.

Fresh eyes still audit this plan — `brainstorm`'s step 10 sends it to a `plan-reviewer` who never saw the session.

Never copy guidance text from this reference or the template into the written doc — the doc holds content only.

## Inputs

The caller gives you the spec file's path and, optionally, a plan output path — write there when given, else derive it from a slug via `SKILL.md`'s naming convention.

You may receive a planning-conventions file (ADR/HLD/LLD or other naming constraints) the plan must respect.

## Sources and tools

- `assets/plan-template.md` and the "Self-review gates" section of `SKILL.md`.
- The `task-breakdown` skill, which emits a prioritized breakdown artifact in `/tmp`.
- The relevant existing code the spec references.

## Procedure

1. Read the spec file in full, even the parts you wrote, plus any planning-conventions file named — recall won't flag where memory and spec diverged.

2. Read `assets/plan-template.md` and `SKILL.md`'s "Self-review gates" — your output must pass the AC-coverage, test-distribution, and DAG checks. Load `task-breakdown` over the spec's work per this file's Task Breakdown section below.

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

Keep each task's Brief Description to ≤256 words — this now spans two places: the body's Task Breakdown entry (title, Depends on, Brief Description, Commits sketch) plus the matching Appendix Task Details entry (AC, Verification, Files). Together they replace the old single 240–406-word median entry, which held a per-task `Tests (planned)` field now folded into Test Design.

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

The old `asset ← threat ⇒ mitigation → AC-N` line format is dropped — the per-box mitigation above replaces it.

## Test Design

Test titles designed before implementation — bodies come during each RED-GREEN cycle. Review before coding starts.

**Integration tests (outer layer)** — the stable user-facing contract. Design all titles upfront, grouped by scenario class so a thin class is a visible gap:

- **Happy cases** — the expected success paths.
- **Corner cases** — boundary/edge inputs handled deliberately (off-by-one, empty, single-vs-many, precision residue, optional field present/absent).
- **Failure scenarios** — every way it fails: guard rejections, downstream errors, partial success, retry-vs-DLQ classification.

Annotate every `it()` with a trailing `// AC-<n>… T<n>… [on-demand]` comment: the ACs it proves, the tasks that write it, and `[on-demand]` when pulled mid-cycle rather than upfront. This section is the single source — the annotation replaces both the AC-coverage list and the per-task `Tests (planned)` field, so no test title is ever written twice.

**Unit tests for pre-known pure helpers** — only helpers we know will exist regardless of design or implementation choices (e.g., obvious normalizers, parsers, validators). Skip this subsection if none.

Tests for helpers pulled on demand during RED-GREEN are designed at the moment the caller first needs them (test-first at the point of pull) — designing them eagerly would force premature signatures.

## Task Breakdown section

Load `task-breakdown` before authoring: it orders tasks (unblockers first, riskiest PoC next), extracts thin contract tasks, splits sub-steps, and emits a `/tmp` artifact.

Populate from it: order becomes the numbering (execution, not narrative order), links become each `Depends on:`, sub-steps become the title breadcrumb and commit sketch.

Lead with a task-dependency DAG (mermaid, `mmdc`-validated) when a task names a real dependency; else `N/A — no task dependencies`.

Each task produces at least one base commit (tests, code, IaC/docs together; RED/GREEN lives inside it). At execution, a refactor/scout/drift/`/auto-review` follow-up becomes its own extra commit; a substantial addition becomes a new peer task. Refactors are isolated tasks.

Sub-step breadcrumb: optional, semicolon-separated parenthetical after the title — `### N. Title (sub-step; sub-step)`; keep ~4 items or split the task.

**Brief Description** is either a short paragraph of at most 4 sentences, or a bullet list of one sentence per bullet — never a longer prose block.

## Task Details section

Lives in the Appendix, one `<details>` entry per task, in the exact shape the template shows. Never use a `### N.` heading inside Task Details — the task's identity lives in the body's Task Breakdown entry; Task Details is keyed by its `Task N —` summary line only.

Field placement:

- **Testable Acceptance criteria** and **Verification** live only in Task Details, never in the body entry.

- **Files (logical order)** lives only in Task Details — it grounds the task's subagent as its starting set, skipping re-discovery; keep it accurate, though the subagent may touch more.

- Title, **Depends on**, **Brief Description**, and **Commits (sketch, minimum)** live only in the body's Task Breakdown entry.

Adding a task always writes both entries — a task with only one is incomplete.

**Tests (planned)**: dropped everywhere except one opt-out — when a task's tests are fully covered elsewhere and none apply, state `**Tests (planned)**: N/A — <reason>` inside that task's body entry. This is the one surviving use of the field.

A plan-only run (no spec) carries each task's acceptance criteria inline in its Task Details entry, since there's no spec AC to point back to.

`Commits (sketch, minimum)` is a floor — drift fixes, scout findings, refactor sub-steps, and `/auto-review` follow-ups become extra commits, each tagged `[Drift]`/`[Scout]`/`[Refactor]`.

## PR Breakdown section

Split past one-plan-one-PR when the work is too large to review well in one sitting. Felt size (guide, not gate): defect-detection drops sharply past ~400 diff lines, falls off above ~600 (SmartBear/Cisco, Google). No code exists yet — estimate by feel, never invent a line number.

Splitting rules:
- Vertical, never horizontal — each PR ships its own tests+code+docs+infra; never "PR-1 = tests, PR-2 = code."
- Prefer independent PRs; a dependent sequence is fine.
- Each PR independently reviewable/mergeable, in order if dependent.
- Sequence by `task-breakdown`'s priorities — unblockers and riskiest PoC first.
- Don't over-split (~50-line floor) — catch one giant PR, not many tiny ones.

One `### PR-N.` heading per PR, one level above Task Breakdown's `### N.`.

Only the orchestrating agent writes two inline fields, absent until then:
- `[<status>]` (`[Doing]`/`[Done]`/`[Blocked]`/`[Deferred]`/`[Dropped]`) after `PR-N.`, at batch-end.
- Backtick-wrapped `**Branch**:`, once that PR's batch pushes — `parse-pr-breakdown.sh` reads the branch name between the backticks.

Each field is its own line; parsers read the first found per PR. Free prose after is for the reviewer.

Lead the PR headings with a PR-dependency DAG (mermaid, `mmdc`-validated) when any PR names a real dependency; else `N/A — no PR dependencies`.

## Decision logs

Both the Functional Decisions (spec) and Technical Decisions (plan) logs live in the Appendix, are chronological, and are editable until the user approves and signals execution start.

At that point, insert the divider line already present in the template and switch to append-only: entries above stay frozen, revisions become new entries appended below with `**Supersedes:**` references rather than in-place edits.

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist.

## Boundaries

- Never plan on an undocumented decision, even one the interview settled — record it as an Open Question, or the spec stays wrong.

- Never guess at code you haven't read — an unlocatable module, file, or pattern is an Open Question, not an invented name.

- Write the plan in English regardless of the spec's language, per `SKILL.md`.

- Every spec AC must map to one Test Design test — an unmapped AC is the same gap as missing spec content.

- Never modify the spec file — a spec-shaped gap goes in Open Questions; the caller fixes the spec.

## Report format

"Plan written to `<path>`" + a one-paragraph approach/task-count summary, then the Open Questions count with a one-line statement each.
