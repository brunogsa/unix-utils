# Writing acceptance criteria

Read once by the authoring agent while filling in `assets/spec-template.md`. Rules only — the skeleton carries none, so they live here.

Never copy guidance text from this or the template into the written doc — the doc holds content only.

Read `references/spec-acceptance-criteria.md` alongside this file for the Testable Acceptance Criteria section — split out to keep each file under its word budget.

## Body/appendix contract

The human body is everything above the literal `# Appendix` heading. It ends there, and every section below is AI-only.

Appendix `## ` headings come heading-first, with a `<details>` collapsible inside — never wrapping an entire heading. Every heading keeps its exact text and level, so grepping `## ` still finds each section.

## Size guideline

Keep the human body (everything above `# Appendix`) to 1–6 pages (~500–3,000 words) depending on the problem; simpler and shorter is better. This is a soft guideline, never a gate.

Keep each AC's Given/When/Then body to ≤128 words — roughly the 70th percentile of what specs already write, so this tightens existing practice instead of inventing new discipline.

A flat file-wide cap punishes a large spec or sits meaningless on a small one; a per-AC cap scales with the feature and still catches one bloated AC in an otherwise-compliant file.

## Background / Context

Why this change is needed — business context, pain point, or opportunity.

## Goals and Success Metrics / KPIs

What we want to achieve (outcomes, not implementation).

## User Stories

Pattern: `As a <role>, I want <capability> so that <benefit>.` — one per bullet.

## Non-Functional and Technical Requirements

Prompt: performance, security, module reuse. Instantiate what applies, skip the rest.

## N/A escapes

Every section keeps its heading even when it doesn't apply — write `N/A — <reason>` as the body instead of deleting the section:

- Context Diagram: for a trivial or no-flow change (one-line config, copy tweak).
- User Stories: when no distinct user role applies, bare `N/A` with no reason clause needed.

Follow the `mermaid-diagrams` skill for the Context Diagram's conventions — lead with a C4L1 context diagram (plus sequence diagrams when a flow needs them), from the perspective of the users in the User Stories and Acceptance Criteria. A validated picture is the fastest way for the reviewer to grasp the system boundary; add prose only for what it can't show.

## Functional Decisions log

Lives in the Appendix. Chronological log, editable during refinement.

Once the user approves the plan and signals execution start, insert the divider line already present in the template and switch to append-only — revisions become new entries with `**Supersedes:**` references rather than in-place edits.

Entries above the divider stay editable until execution starts; afterwards, append below it only.

Each decision is its own collapsed `<details>`, with the summary carrying a one-line gist of the choice.

`__Chose__`: approach. `__because__`: reason. `__Discarded__`: alternative plus why it lost. `__Supersedes__`: first ~60 chars of prior entry replaced.
