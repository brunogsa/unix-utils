[Template is in English. For non-English teams, translate section headers and body text to the team's primary language per the "Section names in the PR's primary language" rule in SKILL.md.]

[Review guide goes FIRST, before any content, collapsed by default:]

<details>
<summary><strong>Review guide</strong> (estimated time: {min}-{max} min)</summary>
[Generated per `~/.claude/skills/reviewer-agent/references/reading-order-template.md` — translate to the team's language as needed.]
</details>

## Summary
[From spec.md Background + Goals (when available), cross-referenced with
commit messages and diff to confirm what was actually delivered.
Condensed to 2-3 bullets. Always ground in commits, not just docs.]

## Testable Acceptance Criteria
[Format follows the "Testable Acceptance Criteria — verbatim from spec.md" rule in SKILL.md (the rule is canonical; do not restate it here). Skeleton:

```
### <AC title from spec, "AC-N:" prefix removed>
- **Given** ...
- **When** ...
- **Then** ...
- **And** ...

> Covered by [manual tests](#scenario-N), [`path/to/spec.ts`](https://github.com/<owner>/<repo>/blob/<branch>/path), and/or [contract tests](#anchor).
```

Use whichever combination of links applies — manual + integration + contract; omit any that don't apply. Source-code links MUST be absolute GitHub URLs (relative paths are unreliable in PR descriptions — see "Always use absolute GitHub URLs" rule in SKILL.md).

Do NOT inline payloads/screenshots/log output here. Those live in the Evidences appendix; the link puts the reviewer one click away.

This section comes BEFORE Architecture — it's the truth-criterion of the PR.]

## Architecture
[**ALWAYS include this section** — never silently drop it.
Mermaid diagrams extracted from spec.md/plan.md lives here, pasted verbatim (GitHub renders them natively), with highlights if possible.
Each diagram preceded by a one-line caption. All encapsulated by collapsibles, `<details><summary>Caption here</summary> … </details>`. With 2+ diagrams, leave the first open and the rest closed by default.]

### Decisions
[Decisions justify the high-level structure — they belong INSIDE Architecture, not as a peer section.

Primary: [DECISION: ...] markers from spec.md and plan.md.
Start with the Functional Decisions, then list the Technical Decisions.
Make them as short as possible, but optimize for clarity. It should be easy as possible to understand, don't assume reader the relevant context. Provide it as sub-bullet if necessary.
Merge both sources, deduplicate if necessary.]

## Changes
[Compare git diff against plan.md tasks (when available).
Two groups:

- **Planned changes**: tasks from the plan that were implemented.
- **Discovered along the way**: modifications not in the plan -- side-effects,
  cleanup, fixes discovered during implementation, scope adjustments.
  Without plan.md: organize changes from diff and commit messages.]

## Evidences

[Include ONLY categories that add value beyond GitHub's PR UI (the checks tab already renders lint/build/security/generic-CI as badges — don't duplicate them). Do NOT use markdown tables.

Typical sections worth including:

- **Manual tests** — primary evidence with no GitHub equivalent. One collapsible per scenario, each preceded by an explicit `<a id="scenario-N"></a>` anchor (GitHub does NOT auto-generate anchors from `<details><summary>` text — only from headings — so the anchor is mandatory for ACs to deep-link in). Setup/seed inventory in its own collapsible. Request + response (pretty-printed JSON, one field per line per the "JSON snippets" rule in SKILL.md).
- **High-risk CI checks worth highlighting** — e.g., a migration that takes a maintenance-window lock, or a new integration suite worth calling out by count + scope. Link the run; don't restate what the green badge already says.
- **Pre-prod / staging deploy** — only if you have the link + smoke result NOW; otherwise omit (don't park as `⚠️ TODO collect post-merge`).
- **Screenshots** — only when UI actually changed.

Drop categories without value-add (lint, generic build, security scans, "N/A — backend-only" placeholders).

Manual-test appendix layout:

```
<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — short description</summary>

`GET /v1/...` → `200 OK`, `totalItems: N`:

```json
{ ... pretty-printed ... }
```

</details>
```
]

## References
[Jira links, related PRs, etc.]
