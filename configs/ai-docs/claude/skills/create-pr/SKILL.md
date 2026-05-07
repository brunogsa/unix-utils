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

Write `./pr-description.md` in the directory where Claude Code is running.

**CRITICAL: Always check for a PR template** in `.github/` (e.g., `pull_request_template.md`,
`PULL_REQUEST_TEMPLATE.md`). If one exists, it is the **base structure** -- keep every section
and checkbox from the template.

Fill in each section with the rich content generated from
spec/plan/commits/diff.

Add extra sections as per the PR template below AFTER (as an appendix) or
WITHIN the template structure (preferred), **NEVER** replacing it.

Mark checklist items as `[x]` when applicable.

If no PR template exists, use the default template below.

**CRITICAL: Testable Acceptance Criteria and Evidences sections are MANDATORY** regardless of whether the team's PR template includes them. If the template lacks them, add explicit `## Testable Acceptance Criteria` and `## Evidences` sections inside the template structure. See Writing Style rules below for format and locality requirements.

#### Default Template

See `references/pr-template.md` for the full template structure.

The Guia de review template, time-estimate heuristic, and file-role inference live in `~/.claude/skills/reviewer-agent/references/reading-order-template.md` (Portuguese variant).

#### Writing Style

**Meta-principle: reader has no context — provide it.** Every rule below derives from this. The reviewer hasn't read your spec, plan, Jira ticket, or commits, and doesn't share your team's vocabulary. Anything you reference must be self-contained or externally linked. Be concise, but simple and didatic.

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
- **Always include business context** -- every PR must explain the business problem being solved. Extract from the spec's Background section when available, or from commit messages. Reviewers who don't know the ticket need this to evaluate correctness.
- **Testable Acceptance Criteria — verbatim from spec** -- copy the full BDD content (Given/When/Then/And bullets) as-is from the spec's `## Testable Acceptance Criteria`; drop only spec-internal numbering ("AC-N:" prefix). Each AC ends with ONE short line: `> Covered by [manual tests](#scenario-N), [path/to/spec.ts](https://github.com/.../blob/branch/path), and/or [contract tests](#anchor).` Use whichever combination applies; omit any that don't. Mandatory even if the team's template lacks the section.
- **Evidences section — include only what adds value beyond the GitHub PR UI** -- the checks tab already renders lint/build/security/CI badges; don't duplicate them. Worth including: manual tests (no GitHub equivalent — one collapsible per scenario, claim adjacent to request+response); high-risk CI checks worth a callout (e.g., a migration with maintenance-window lock); pre-prod/staging deploy (only with the link + smoke result NOW); screenshots (only when UI changed).

##### Formatting & rendering

- **Bold topic prefix on every bullet** -- start each bullet with `**Topic** --` so reviewers can scan the bold words and skip details they don't need
- **Be concise** -- one short sentence per bullet. Sub-bullets only when essential.
- **No blank lines between bullets** -- keep lists tight. GitHub adds extra spacing with blank lines.
- **One sentence per paragraph for dense factual prose** -- when a body paragraph stacks ≥2 atomic claims (e.g., CI status + scope + count), split each into its own short paragraph separated by a blank line. Whitespace gives reviewers scan-anchors. Bullets in lists stay tight (per the previous rule); flowing narrative stays prose.
- **Section names in the PR's primary language** -- when the team PR template is Portuguese (Brazilian Integrator/Arco), translate any imported English section names (`Evidences` → `Evidências`, `References` → `Referências`, `Changes` → `Mudanças`). Inconsistent language across the ToC reads as imported boilerplate.
- **Blank line BEFORE every list** -- always insert one blank line between a preceding paragraph (e.g., `**Essencial** (~10min):`) and the first list item. Without it, ordered lists that don't start at `1.` (e.g., a "Completo" continuation `6. ...`) silently merge into the paragraph per CommonMark spec. Defensive rule: always add the blank line, regardless of list type or start number — costs nothing, prevents the regression.
- **Max ~100 chars per line** -- break longer lines into top-level bullet + sub-bullets
- **Never use markdown tables in PR bodies** -- tables fragment scanning, break on narrow widths, and put related details (claim + evidence) into separate cells with no place to nest collapsibles. Replace with bullet lists where each item has its evidence as a sub-bullet or inline collapsible.
- **`>` blockquotes only for actual quoted content or per-bullet evidence pointers, not for section intros** -- a `>` paragraph at the top of a section creates a gray left bar that sits visually indented relative to the H4 headings below it, inverting the hierarchy. Use plain paragraphs for section intros, contextual notes, or summaries. Reserve `>` for: quoted commits/issues/external text, or per-AC "Covered by ..." pointer lines (one-liners where the visual offset signals "this is meta about the bullet above").
- **JSON snippets: fully pretty-printed, one field per line** -- use `JSON.stringify(obj, null, 2)` style — each key on its own line, 2-space indentation, every nested object/array expanded vertically, including single-key objects. NEVER inline objects (`{ "sku": "X" }` or `{ "sku": "X", "id": "Y" }`); only `[]` for empty arrays may stay on one line. Example: see [`references/json-format-example.md`](references/json-format-example.md).
- **Always use absolute GitHub URLs for in-repo file links** -- relative paths are unreliable across GitHub UI surfaces (notifications, embedded previews, GraphQL extracts). Use `https://github.com/<owner>/<repo>/blob/<branch>/<path>`. Use the branch ref for PR-scoped links (follows future pushes); use the commit SHA for permalinks.

##### Content quality

- **Separate planned from incidental** -- group items under `**Planned:**` and a descriptive incidental label (PT-BR: `**Descobertas durante o desenvolvimento, também endereçadas:**`; EN: `**Discovered along the way, also addressed:**`). The longer label sets context that these were not in original scope. For each incidental, briefly explain why it had to be fixed now (e.g., "blocked green CI on this branch").
- **CRITICAL: ZERO references to untracked session docs in the PR body** -- never name `spec.md`, `plan.md`, gitignored `.md` files, internal task/AC numbers, commit SHAs in prose, or internal dependency source files. The reviewer cannot open them. Verify with `git ls-files <name>` before referencing any `.md` — if untracked, substitute the actual value (or delete). This applies to verbatim copies from spec too: scrub references inside copied content. Exception: external links and git-tracked files in the same repo (e.g., `agents.md`, `CLAUDE.md`, source files) stay.
- **Don't repeat links across sections** -- if a Jira link or PR link appears in "Link do Jira" or "Context", don't repeat it in "References". The references section is for follow-up tasks, external docs, or links not already present elsewhere in the PR.
- **Explain domain terms inline on first use** -- when a bullet uses a team-specific term ("bulk-failure", "all_skus row", "shadow read"), define it parenthetically on first mention. Don't assume the reviewer shares your vocabulary.
- **Frame as user/system impact, not internal model** -- prefer "afetando os fluxos de orders, invoicing, sync" over "compartilhada com os fluxos de write". Reviewers care about consequences, not data-flow taxonomy.
- **Plain language in decisions, not insider shorthand** -- decisions are read outside the immediate task. State the concrete consequence if reversed (e.g., "exposed to injection or DoS"), not the abstract property ("fail-loud"). Replace team jargon with what it means in plain terms.
- **⚠️ marker on operational risks** -- prefix decisions and checklist items with ⚠️ when they require human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations). Reviewers and on-call need to spot these while skimming.
- **Explain the "how is it different"** -- when mentioning a new method/function, briefly say what makes it different from existing ones. Don't just name it.
- **Don't list types/interfaces** -- type names are visible in the diff. Listing them in the PR is noise.
- **Drop implementation jargon from planned items** -- don't say "(injectable NestJS)" or "(pure function)". Describe what it does for the reviewer, not the DI framework details.
- **No scope-internal acronyms without definition** -- "AC" (acceptance criteria), "FR/NFR" (functional/non-functional requirement), team-specific shorthand only make sense to people who read the spec. Spell out in full on first use, or use plain language ("the scenario where ..." instead of "AC-7").
- **Incidentals must change shared state to earn a bullet** -- include only incidentals that modify docs, conventions, or shared infra (anything a future developer benefits from knowing). Skip items the diff/commit history already shows: merge-conflict resolutions, auto-review feedback responses, intra-branch refactors, task-internal cleanup. Group remaining small fixes (typos, log levels, error messages) into a single bullet.
  - Test: would a future contributor searching "why does X exist?" find this bullet valuable? If no, cut it.

##### Evidence & locality

- **Collapsible sections for large content** -- use `<details><summary>` for reference payloads, long examples, or API responses.
- **Evidence locality: claim adjacent OR linked to the artifact** -- every claim ("PASS", "validated", "AC met") must be followed by either a collapsible with the artifact or a deep link to it in an appendix/source file. The link IS locality. For long lists (e.g., 18 ACs), use deep links to a single appendix; don't bloat the truth-criterion list with inline collapsibles.
- **Manual test payloads live in an Evidences appendix, not inline in TAC** -- one collapsible per scenario inside the manual-tests subsection of Evidences. Each `<details>` block must be preceded by an explicit `<a id="scenario-N"></a>` line — GitHub does NOT auto-generate anchors from `<details><summary>` text, only from headings. ACs link to `#scenario-N` (short, stable IDs). This keeps TAC scannable AND keeps locality (one click away).
- **No claim without evidence — absent evidence means drop the scenario, not park it** -- if you can't paste the verifiable artifact (request+response, screenshot, log), DROP the bullet. "Covered by automated tests at `path/to/spec.ts`" is not evidence; the reviewer already has that via the diff. Same rule applies to whole sections: if "Pre-prod pipeline" can only say "⚠️ TODO collect post-merge", remove the section. TODO sections rot, add noise, and dilute the surrounding evidence.
- **Coverage-only scenarios — group, don't enumerate** -- when a whole group of scenarios is exercised exclusively by an automated test suite (e.g., contract tests, integration tests) with no manual evidence per scenario, write ONE intro sentence pointing to the suite + CI link, then list scenarios as plain prose bullets without empty collapsibles. Don't repeat the same `<details>covered by tests</details>` shell on each one.

Bullet-style example (hard-to-scan vs scannable): see [`references/bullet-style-example.md`](references/bullet-style-example.md).

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
