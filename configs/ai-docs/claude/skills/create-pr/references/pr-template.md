---
# performance-check budget override, not part of the template itself.
# This file's size is set by the filled-in PR template it reproduces --
# every section, budget note, and bracketed instruction is inherent to
# the artifact, so trimming would make the template misleading rather
# than smaller. Raised from the 1024-word bundled default to the next
# power of two that fits.
words-budget: 2048
---

[Template is in English. For non-English teams, translate section headers and body text to the team's primary language per the "Section names in the PR's primary language" rule in SKILL.md.]

[Every section below obeys SKILL.md's non-overlap invariant: nothing rendered here may also appear in the appendix, and nothing in the appendix may repeat a body section.]

[It also obeys SKILL.md's one-page goal: the whole file, appendix included, fits 64 rendered lines.

Each section below opens with its own line allowance. SKILL.md owns those budgets, the measurement, and the cut order; the numbers here are a recap, not a second source of truth.

Images, diagrams, blank lines, and collapsed content are free — a collapsed `<details>` costs only what its `<summary>` renders as.]

[Budget: 1 line — this collapsed `<summary>`. It goes FIRST, before any content, and its one line is charged before the first heading rather than to a section below it.

This file owns the `<details>` wrapper and the summary label; `references/reading-order-template.md` supplies only what goes inside.]

<details>
<summary><strong>Review guide</strong> (estimated time: {min}-{max} min)</summary>
[Generated per `references/reading-order-template.md` — translate the wrapper's label and the contents to the team's language as needed.]
</details>

## Jira link
[Budget: 4 lines. Bullet list of the ticket(s) this PR closes, plus any related PR. Omit only when the repo tracks no tickets.]

## Context
[Budget: 17 lines — this heading plus at most 4 paragraphs of at most 4 lines each.

Business context in scannable layers, per the "Context section" rule in SKILL.md (the rule is canonical; do not restate it here).

Source it from the spec's Background + Goals when available, cross-referenced with commit messages and the diff to confirm what was actually delivered.

Always ground in commits, not just docs. This section carries the PR's summary — there is no separate Summary heading.]

## Changes
[Budget: 9 lines — this heading plus 8 bullets, counting both group labels toward the 8.

A changelog, not a narrative — read like game patch notes: one flat line per change, no sub-bullets, no bold-topic prose.

Each bullet names the BEHAVIOR that changed, never the file that changed; the review guide already lists the files.

Two groups, per the "Separate planned from incidental" rule in SKILL.md, which owns the group labels and what earns a bullet in each.

Without the plan: derive the bullets from the diff and commit messages.]

## Decisions
[Budget: 18 lines — 3 headings plus 8 bullets for Functional and 7 for Technical, with either subsection free to spend the other's unused allowance.

Decisions come BEFORE Architecture: the reviewer learns what was chosen, then sees it rendered in the diagrams.

This is a HIGH-LEVEL SUMMARY of the main decisions. The full catalog lives verbatim in the appendix — see SKILL.md's altitude rule, which is canonical.

Source: [DECISION: ...] markers from the spec and the plan, merged and deduplicated, then cut down to the ones that change behavior, cost, or risk.

Anything a reader could settle by opening the code — a field choice, a file location, a signature — stays in the appendix only.

Each entry reads decided → why → considered:

```
- **<what was decided, stated as the outcome>** — <why, in one clause>.
  - Considered: <the rejected alternative> — <why it lost>.
```

Drop `Considered` only when no alternative was genuinely weighed, and drop every entry the Architecture diagrams already encode.

Omit either subsection when it has no decisions; never pad it with a placeholder.]

### Functional
[Product/behavior choices a non-engineer stakeholder could disagree with.]

### Technical
[Implementation choices only an engineer would weigh in on.]

## Architecture
[Budget: 5 lines — this heading plus at most 4 diagrams, each costing only its one-line caption.

**ALWAYS include this section** — never silently drop it.

Every mermaid diagram extracted from the spec and the plan lives here, pasted verbatim (GitHub renders them natively), with highlights if possible.

Each diagram sits in its own `<details open><summary>One-line caption</summary> … </details>`, expanded by default, including when there are several.

Diagrams are the fastest thing in the PR to review, so they must not start collapsed.]

## Evidences
[Budget: 5 lines — this heading, the counted-tests line, and up to 3 collapsed manual scenarios.

Prove the change was tested, in the fewest words that still convince. Two parts, in this order: automated coverage, then manual evidence.

**Automated coverage is ONE line**: how many tests were added and how many acceptance criteria they cover, pointing at the appendix for the criteria themselves.

Never index the criteria here — no per-criterion bullets, no happy-path/failure/corner-case groups.

The tests are in the diff and the criteria are in the appendix, so a body-side index is a third copy of both.

**Manual evidence** covers only what automation could not prove. Omit the part entirely when everything is automated.

Each manual scenario sits in its own `<details>`, COLLAPSED by default, preceded by an explicit `<a id="scenario-N"></a>` anchor.

Its methodology goes INSIDE that collapsed block, not above it: 2-3 sentences in plain words on what you ran, against what, and what you looked at.

Then just enough log output or screenshots to show it ran and passed — not the full transcript.

GitHub does NOT auto-generate anchors from `<details><summary>` text — only from headings — which is why the explicit anchor is mandatory.

Drop lint, generic build, and security scans: the checks tab already renders those as badges. Screenshots only when UI actually changed.

Manual-scenario layout:

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

## Appendix — optional reading
[Budget: 5 lines — this heading, at most 1 line of intro, and one collapsed block per subsection.

Collapsed by default, and explicitly labelled optional: the body plus the diff is the complete review. Its audience is deep divers and AI reviewers.

One `<details>` per subsection below. Omit the whole section only when it would be empty.

Source-code links MUST be absolute GitHub URLs (relative paths are unreliable in PR descriptions — see the "Absolute GitHub URLs" rule in SKILL.md).]

### References
[Follow-ups, external docs, and related PRs.

A link already rendered in "Jira link" or "Context" never repeats here — that is the non-overlap invariant applied to links.]

### <spec & plan details>
[Contents are DERIVED, not chosen — the resolved spec/plan minus every section the body already renders.

SKILL.md's "Derive the appendix's section list" owns the included/excluded lists. Never re-enumerate them here, since one enumeration is what keeps the two files from drifting.

Omit these subsections entirely when no spec/plan resolved.

Acceptance criteria live here and ONLY here — the body's Evidences carries just their count, never their titles or their BDD body.

The decision catalog likewise lives here in full and verbatim, including the low-level entries the body's summary cut.

Keep the spec's BDD content (Given/When/Then/And) verbatim EXCEPT for its numbered lookup tokens: strip every `AC-N`, `PR-N`, `D-N`, `R-N`, and `OQ-N`, wherever it sits.

That is doc-standards' ban on citing a doc by a number that renumbers on the next edit, and it outranks the verbatim rule.

A criterion's own `AC-N:` heading prefix just disappears; a token cited inline is replaced by the behavior it names, or dropped when the sentence already names it.

Keep the spec's own criterion grouping as `### ` headings, so each criterion nests one level under its group:

```
### <group from spec — e.g. Happy path / Corner cases / Failure modes>

#### <AC title from spec, "AC-N:" prefix removed>
- **Given** ...
- **When** ...
- **Then** ...
- **And** ...

> Covered by [manual tests](#scenario-N), [`path/to/spec.ts`](https://github.com/<owner>/<repo>/blob/<branch>/path), and/or [contract tests](#anchor).
```

Use whichever combination of links applies — manual + integration + contract; omit any that don't apply.

Do NOT inline payloads/screenshots/log output here. Those live in Evidences; the link puts the reviewer one click away.]
