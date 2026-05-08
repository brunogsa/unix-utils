---
name: create-pr
description: "Create a GitHub PR with a rich description. User-invoked only — auto-detects spec.md/plan.md for context."
disable-model-invocation: true
---

# Create Pull Request

Create a GitHub PR with a rich description generated from
spec.md and plan.md context (when available).

## Usage

`/create-pr`

No flags needed. Auto-detects spec.md and plan.md in the current directory.

## Process

### 1. Gather context

- Check for spec.md and plan.md in cwd (optional -- works without them)
  - Extract all ` ```mermaid ``` ` fenced blocks from each file, including all of them in the PR description as collapsibles
- Check for PR templates in `.github/` (e.g., `PULL_REQUEST_TEMPLATE.md`)
- Run git log to see commits on current branch vs base -- **primary source**: mine commit messages for decisions, rationale, and scope changes regardless of whether spec/plan exist
- Run git diff against base branch
- Check if branch is pushed

### 2. Write pr-description.md

Write `./pr-description.md` in cwd.

**CRITICAL: Always check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

- If present, it's the base structure — keep every section and checkbox; fill with rich content from spec/plan/commits/diff.
- Add extra sections WITHIN the template (preferred) or as an appendix, **NEVER** replacing it.
- Mark checklist items as `[x]` when applicable. If no template exists, use the default below.

**CRITICAL: Testable Acceptance Criteria and Evidences are MANDATORY** regardless of the template.

- If absent, add `## Testable Acceptance Criteria` and `## Evidences` inside the template structure.
- See Writing Style for format and locality.

#### Default Template

See `references/pr-template.md` for the full template structure.

The Guia de review template, time-estimate heuristic, and file-role inference live in `~/.claude/skills/reviewer-agent/references/reading-order-template.md` (Portuguese variant).

**Reading guide is qualitative, not taxonomic** -- each file entry describes what the reviewer *learns* there, not just role labels.

Open with a rationale paragraph, bold the densest file, close with a minimum-viable-read shortcut. Layout + examples: see [`references/decision-quality.md`](references/decision-quality.md).

#### Writing Style

**Meta-principle: reader has no context — provide it.**

The reviewer hasn't read your spec, plan, Jira ticket, or commits, and doesn't share your team's vocabulary. Anything you reference must be self-contained or externally linked. Be concise but didactic.

##### Required structure & mandatory content

- **Required PR structure (in this order)** -- canonical sections, all mandatory unless N/A. Translate to the team's language per the rule below.
  1. Jira link
  2. Context — business problem (see "Always include business context")
  3. Testable Acceptance Criteria — verbatim from spec; truth-criterion
  4. Architecture — diagrams + Decisions as a subsection (don't promote Decisions to a peer)
  5. Changes — Planned + Discovered along the way (see "Separate planned from incidental")
  6. Checklist — preserve the team's checklist verbatim
  7. Evidences — value-add only; manual-test appendix lives here
  8. References — last
- **Always include business context** -- explain the business problem; extract from spec Background or commit messages. Reviewers without ticket access need this to evaluate correctness.
- **Context section in scannable layers, never one paragraph per ticket** -- ordered layers:
  1. User-facing problem.
  2. Parent goal / epic.
  3. Neighboring dependencies' status.
  4. This PR's scope as bullets+sub-bullets per ticket.
  - Multi-ticket PRs need one bullet per ticket — not a dense paragraph each.
- **Testable Acceptance Criteria — verbatim from spec** -- copy BDD content (Given/When/Then/And) from `## Testable Acceptance Criteria`; drop only "AC-N:" prefix.
  - Each AC ends with one line: `> Covered by [manual tests](#scenario-N), [path/to/spec.ts](https://github.com/.../blob/branch/path), and/or [contract tests](#anchor).` Use whichever combination applies.
  - Mandatory even if the template lacks the section.
- **Evidences section — only what adds value beyond GitHub PR UI** -- skip what the checks tab already shows (lint/build/security/CI badges).
  - Worth including: manual tests (collapsible per scenario, claim adjacent to request+response).
  - High-risk CI checks (e.g., maintenance-window migration).
  - Pre-prod/staging deploy (only with link + smoke result NOW).
  - Screenshots (only when UI changed).

##### Formatting & rendering

- **Bold topic prefix on every bullet** -- start each bullet with `**Topic** --` so reviewers can scan the bold words and skip details they don't need
- **Be concise** -- one short sentence per bullet. Sub-bullets only when essential.
- **No blank lines between bullets** -- keep lists tight. GitHub adds extra spacing with blank lines.
- **One sentence per paragraph for dense factual prose** -- when a body paragraph stacks ≥2 atomic claims (e.g., CI status + scope + count), split each into its own short paragraph.
  - Whitespace gives scan-anchors. Bullets stay tight; flowing narrative stays prose.
- **Section names AND body prose in the PR's primary language** -- translate headers and recurring body terms; engineering jargon stays English. Examples: see [`references/decision-quality.md`](references/decision-quality.md).
- **Blank line BEFORE every list** -- prevents CommonMark merging ordered lists that don't start at `1.` into the preceding paragraph. Defensive: always insert, regardless of list type or start number.
- **CRITICAL: Density caps verified by script** -- every prose line, bullet, and sub-bullet ≤256 chars / ≤32 words. Break longer lines into bullet + sub-bullets, or into more (shorter) paragraphs.
  - Run `~/.claude/skills/doc-standards/scripts/check-density.sh pr-description.md` after writing the body, before showing the user.
  - Output: `<line>:<chars>:<words>` per violation. Exit 1 = violations to fix; iterate until exit 0.
  - Rewrite patterns (paragraph → bullets+sub-bullets, long bullet → bullet + sub-bullets): see `~/.claude/skills/doc-standards/references/density-rules.md`.
- **Never use markdown tables in PR bodies** -- tables fragment scanning, break on narrow widths, separate claim from evidence. Replace with bullets where evidence is a sub-bullet or inline collapsible.
- **`>` blockquotes only for quoted content or per-bullet evidence pointers, not section intros** -- a `>` at section top creates a gray bar visually indented below H4 headings, inverting hierarchy.
  - Use plain paragraphs for intros; reserve `>` for quoted external text or per-AC "Covered by..." one-liners.
- **JSON snippets: fully pretty-printed, one field per line** -- `JSON.stringify(obj, null, 2)` style; every nested object/array expanded vertically, including single-key.
  - NEVER inline. Only `[]` empty arrays stay on one line. Example: [`references/json-format-example.md`](references/json-format-example.md).
- **Absolute GitHub URLs for in-repo links** -- relative paths break across notifications/previews/GraphQL. Use `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (branch ref for PR-scoped, commit SHA for permalinks).

##### Content quality

- **Separate planned from incidental** -- group items under `**Planned:**` (PT-BR: `**Descobertas durante o desenvolvimento, também endereçadas:**`) and briefly explain each incidental.
  - **Drop the `**Planned:**` subsection** when Architecture/Decisions already cover per-ticket scope; keep only "Discovered along the way".
- **Decisions: title is the user-visible surprise, not internal mechanism** -- mechanism details go in sub-bullets. Examples: see [`references/decision-quality.md`](references/decision-quality.md).
- **Decisions: spell out the consequence if reversed when non-obvious** -- sub-bullet showing what breaks. Examples: same reference.
- **Reuse rationale: ONE concrete future use, not a speculative list** -- name a specific use case with ticket ref. Examples: same reference.
- **CRITICAL: ZERO references to untracked session docs** -- never name `spec.md`, `plan.md`, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
  - Reviewer can't open them. Verify with `git ls-files <name>` before referencing any `.md`; if untracked, substitute the actual value or delete.
  - Applies to verbatim spec copies too. Exception: git-tracked files in the same repo stay.
- **Don't repeat links across sections** -- if a Jira/PR link appears in "Link do Jira" or "Context", don't repeat in "References".
  - References section is for follow-ups, external docs, or links not elsewhere.
- **Explain domain terms inline on first use** -- define team-specific terms ("bulk-failure", "all_skus row", "shadow read") parenthetically on first mention. Don't assume shared vocabulary.
- **Frame as user/system impact, not internal model** -- "afetando fluxos de orders, invoicing, sync" beats "compartilhada com fluxos de write". Consequences over taxonomy.
- **Plain language in decisions, not insider shorthand** -- state the concrete consequence if reversed (e.g., "exposed to injection or DoS"), not the abstract property ("fail-loud"). Replace jargon with plain terms.
- **⚠️ marker on operational risks** -- prefix decisions/checklist items with ⚠️ when they need human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations).
- **Explain "how is it different"** -- when introducing a new method/function, briefly say what makes it different from existing ones. Don't just name it.
- **Don't list types/interfaces** -- type names are visible in the diff. Listing them is noise.
- **Drop implementation jargon from planned items** -- don't say "(injectable NestJS)" or "(pure function)". Describe what it does for the reviewer.
- **No scope-internal acronyms without definition** -- "AC", "FR/NFR", team shorthand only make sense to spec readers. Spell out on first use, or use plain language ("the scenario where..." instead of "AC-7").
- **Incidentals must change shared state to earn a bullet** -- only incidentals that modify docs, conventions, or shared infra.
  - Skip diff/commit-visible items (merge resolutions, auto-review responses, intra-branch refactors, task-internal cleanup).
  - Group small fixes (typos, log levels) into one bullet.
  - Test: would a future contributor searching "why does X exist?" find this valuable? If no, cut.

##### Evidence & locality

- **Collapsible sections for large content** -- `<details><summary>` for payloads, long examples, API responses.
- **Evidence locality: claim adjacent OR linked to artifact** -- every claim ("PASS", "validated", "AC met") needs a collapsible with the artifact OR a deep link.
  - The link IS locality. For long lists (e.g., 18 ACs), use deep links to one appendix; don't bloat with inline collapsibles.
- **Manual test payloads live in Evidences appendix, not inline in TAC** -- one collapsible per scenario in the manual-tests subsection.
  - Each `<details>` needs an explicit `<a id="scenario-N"></a>` line above it (GitHub doesn't auto-anchor `<summary>` text, only headings).
  - ACs link to `#scenario-N`. Keeps TAC scannable, locality one click away.
- **No claim without evidence — drop the scenario, don't park it** -- can't paste the verifiable artifact → DROP the bullet.
  - "Covered by automated tests at path/spec.ts" isn't evidence (the diff already shows it).
  - Same for sections: if "Pre-prod pipeline" can only say "⚠️ TODO collect post-merge", remove the section. TODO sections rot and dilute.
- **Coverage-only scenarios — group, don't enumerate** -- when an automated suite covers many scenarios with no manual evidence, write ONE intro pointing to the suite + CI link.
  - Then list scenarios as plain bullets. Don't repeat empty `<details>covered by tests</details>` shells.

Bullet-style example (hard-to-scan vs scannable): see [`references/bullet-style-example.md`](references/bullet-style-example.md).

### 2.4. Resolve TODO-Questions

While drafting, you may leave `// TODO: Question - <factual question>` markers for non-obvious behavior the reviewer would want clarified. Example prompts: see [`references/decision-quality.md`](references/decision-quality.md).

Before step 3, resolve every TODO:

- **If the answer adds reviewer value** — investigate the code, replace the TODO with the answer inline (concise prose, not the full investigation).
- **If the answer is internal-only** — strip the TODO entirely.

A TODO must NEVER survive into the final PR push — they're embarrassing to reviewers and signal the author didn't finish the doc.

### 2.5. Verify density

Run `~/.claude/skills/doc-standards/scripts/check-density.sh pr-description.md`. Output is `<line>:<chars>:<words>` per violation; exit 0 means clean.

For each violation, rewrite per `~/.claude/skills/doc-standards/references/density-rules.md` (paragraph → bullets+sub-bullets, long bullet → bullet + sub-bullets) without dropping information. Re-run until exit 0 before moving to step 3.

### 3. Review with user

Present the pr-description.md content for review.
Wait for approval or edits before creating the PR.

### 3.5. Learn from user edits

After the user edits pr-description.md, diff the original against their version.
Identify patterns in what was added, removed, or reworded. Present proposed improvements
to THIS skill's writing style guidelines (step 2) for user approval.

Apply approved improvements before creating the PR. This makes the skill self-improving over time.

### 4. Create the PR

- Push branch if needed (with -u)
- Create PR as **draft** using `gh pr create --draft` with the content from rich-pr-description.md
- Return the PR URL
