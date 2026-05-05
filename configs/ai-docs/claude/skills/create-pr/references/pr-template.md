[Review guide goes FIRST, before any content, collapsed by default:]

<details>
<summary><strong>Guia de review</strong> (tempo estimado: {min}-{max} min)</summary>
[Generated per `~/.claude/skills/reviewer-agent/references/reading-order-template.md` (Portuguese variant)]
</details>

## Summary
[From spec.md Background + Goals (when available), cross-referenced with
commit messages and diff to confirm what was actually delivered.
Condensed to 2-3 bullets. Always ground in commits, not just docs.]

## Testable Acceptance Criterias
[From spec.md "Testable Acceptance Criteria", which are BDD-like. Keep thei sections: happy path, corner cases, failure scenarios etc]

## Architecture
[**ALWAYS include this section** — never silently drop them.
Mermaid diagrams extracted from spec.md/plan.md lives here, pasted verbatim (GitHub renders them natively), with highlights if possible.
Each diagram preceded by a one-line caption. All encapsulated by collapsibles, `<details><summary>Caption here</summary> … </details>`. The first always open by default. If 2+ diagrams, make those closed by default.]

### Key Decisions
[Primary: [DECISION: ...] markers from spec.md and plan.md.
Start with the Functional Decisions, then list the Technical Decisions.
Make them as short as possible, but optimize for clarity. It should be easy as possible to understand, don't assume reader the relevant context. Provide it as sub-bullet if necessary
Merge both sources, deduplicate if necessary.]

## Changes
[Compare git diff against plan.md tasks (when available).
Two groups:
- **Planned changes**: tasks from the plan that were implemented
- **Drift changes**: modifications not in the plan -- side-effects,
  cleanup, fixes discovered during implementation, scope adjustments.
  Without plan.md: organize changes from diff and commit messages.]

## Evidences it works
[Proof the tests pass and the used methodology. Evidences of manual tests, screenshots etc]

## References
[Jira links, related PRs, etc.]
