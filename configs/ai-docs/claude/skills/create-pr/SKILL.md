---
name: create-pr
description: "Create a GitHub PR with a rich description. User-invoked only — auto-detects spec_<slug>.md/plan_<slug>.md for context."
disable-model-invocation: false
words-budget: 2250
---

# Create Pull Request

## Usage

`/create-pr` — no flags needed.

## Process

### 1. Gather context

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level; optional -- works without them):
  - One spec / one plan → use whichever exist.
  - Multiple specs OR multiple plans → list them numbered and ask which to use.
  - None → proceed from the changes digest (below) only.
  - Extract every ` ```mermaid ``` ` fenced block from each resolved file; include them all in the PR description as collapsibles.
  - When embedding spec/plan content beyond diagrams, prefer a curated slice over the full file.
    - Ask the user which `## ` sections matter; pull them with `~/.claude/skills/create-pr/scripts/extract-md-sections.sh <file> "<section>" ["<section>" ...]`.
    - A full-file embed routinely blows the body-size cap (see step 2.6).
- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**:
  - `<slug>` is the shared filename slug from the resolved `spec_<slug>.md`/`plan_<slug>.md`.
  - No spec/plan resolved → `<slug>` falls back to the current branch name (`/` replaced with `-`).
  - Plan's `## PR Breakdown` reads "Single PR." (or no plan resolved) → omit `<N>` entirely.
  - Plan's `## PR Breakdown` lists multiple `PR-N` entries → ask the user which `PR-N` this covers, set `<N>` to that number (e.g. `PR-2` → `2`).
- **Resolve the base branch (used below and in step 4)**:
  - `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` — same default `/implement`'s own pre-flight interview uses.
  - Every PR targets this branch directly on GitHub, dependent or not — never a parent's branch, matching the plan's own base-branch targeting.
  - Empty result (`origin/HEAD` unset) → omit `--base` in step 4 instead of passing an empty value; let `gh pr create` fall back to its own default.
- Check if branch is pushed
- **Delegate diff/log reading to a subagent** -- dispatch one `general-purpose` Agent, `model: "sonnet"`, `description: "Gather PR changes digest"`, foreground (step 2 needs the result immediately).
  - Give it the resolved base branch (above), the resolved spec/plan section slices from above, and this skill's Writing Style section so it knows what the digest feeds.
  - It reads git log vs base with **full commit bodies** -- the primary source for decisions, rationale, and scope changes (mining relies on `commit-standards`-shaped commits).
  - It reads git diff vs base too, but returns only the **changes digest** (format: `references/changes-digest.md`), never the raw diff.

### 2. Write pr-descr_<slug>_pr<N>.md

Write `./pr-descr_<slug>_pr<N>.md` in cwd -- `<slug>` and `<N>` resolved per step 1 (`_pr<N>` dropped for a single-PR plan).

Author from the changes digest (step 1), the curated spec/plan slices, and the template -- not the raw diff.

**Escape hatch**: if the digest is insufficient for a specific section, read that file's targeted diff (`git diff <base> -- <path>`); never fall back to the full diff.

**CRITICAL: Always check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

- If present, it's the base structure — keep every section and checkbox; fill with rich content from spec/plan and the changes digest.
- Add extra sections WITHIN the template (preferred) or as an appendix, **NEVER** replacing it.
- Mark checklist items as `[x]` when applicable. If no template exists, use the default below.

**CRITICAL: Testable Acceptance Criteria and Evidences are MANDATORY** regardless of the template.

- If absent, add `## Testable Acceptance Criteria` and `## Evidences` inside the template structure.
- See Writing Style for format and locality.

#### Default Template

See `references/pr-template.md` for the full template structure.

The Guia de review template, time-estimate heuristic, and file-role inference live in `~/.claude/skills/code-review-pipeline/references/reading-order-template.md` (Portuguese variant).

For a full real-world example following this structure end-to-end — including the curated spec/plan embed from step 1 — see [`references/pr-description-example.md`](references/pr-description-example.md).

**Reading guide is qualitative, not taxonomic** -- each file entry describes what the reviewer *learns* there, not just role labels.

Open with a rationale paragraph, bold the densest file, close with a minimum-viable-read shortcut. Layout + examples: see [`references/decision-quality.md`](references/decision-quality.md).

#### Writing Style

**Meta-principle: reader has no context — provide it.**

The reviewer hasn't read your spec, plan, Jira ticket, or commits, nor shares your team's vocabulary. Anything referenced must be self-contained or externally linked. Be concise but didactic.

**Second meta-principle: a small PR earns a small description.**

This is a discipline, not a hard cap:

- **CRITICAL: Write the shortest version that still teaches** -- cut any sentence that doesn't help the reviewer decide.
  - Test: would removing it lose reviewer-relevant information? If no, cut it. A one-file, one-decision PR should read in under a minute.
- **Never restate what the diff already shows** -- a sentence naming only a file, a line count, or "added X function" is noise the reviewer already sees.
  - Reserve prose for the *why* the diff can't show: the reasoning, the trade-off, the discarded alternative.
- **Evidences defaults to one line per claim, not a narrative** -- `**Claim** -- link/output`.
  - Expand to a paragraph only for a genuinely surprising or high-risk result; skip routine green-checks the CI tab already proves.

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
- **Always include business context** -- explain the business problem; extract from spec Background or commits. Reviewers without ticket access need it to evaluate correctness.
- **Context section in scannable layers, never one paragraph per ticket** -- ordered layers:
  1. User-facing problem.
  2. Parent goal / epic.
  3. Neighboring dependencies' status.
  4. This PR's scope as bullets+sub-bullets per ticket.
  - Multi-ticket PRs need one bullet per ticket — not a dense paragraph each.
- **Testable Acceptance Criteria — verbatim from spec** -- copy BDD content (Given/When/Then/And) from `## Testable Acceptance Criteria`; drop only "AC-N:" prefix.
  - Each AC ends with a one-line `> Covered by ...` pointer (skeleton in `references/pr-template.md`); use whichever link combination applies.
- **Evidences section — value-add only** -- categories and layout live in `references/pr-template.md` (canonical); skip anything the checks tab already shows (lint/build/security/CI badges).

##### Formatting & rendering

- **Bold topic prefix on every bullet** -- start each bullet with `**Topic** --` so reviewers scan the bold words and skip details they don't need
- **Be concise** -- one short sentence per bullet. Sub-bullets only when essential.
- **Bullet spacing follows doc-standards**.
- **One sentence per paragraph for dense factual prose** -- when a paragraph stacks ≥2 atomic claims (e.g., CI status + scope + count), split each into its own short paragraph.
  - Whitespace gives scan-anchors. Bullets stay tight; narrative stays prose.
- **Section names AND body prose in the PR's primary language** -- translate headers and recurring body terms; engineering jargon stays English. Examples: see [`references/decision-quality.md`](references/decision-quality.md).
- **Blank line BEFORE every list** -- prevents CommonMark merging ordered lists that don't start at `1.` into the preceding paragraph.
- **CRITICAL: Density caps per doc-standards** -- step 2.5 owns the script verification.
- **Never use markdown tables in PR bodies** -- they fragment scanning, break on narrow widths, separate claim from evidence. Replace with bullets where evidence is a sub-bullet or inline collapsible.
- **`>` blockquotes only for quoted content or per-bullet evidence pointers, not section intros** -- a `>` at section top creates a gray bar indented below H4 headings, inverting hierarchy.
- **JSON snippets: fully pretty-printed, one field per line** -- `JSON.stringify(obj, null, 2)` style; every nested object/array expanded vertically, including single-key.
  - NEVER inline. Only `[]` empty arrays stay on one line. Example: [`references/json-format-example.md`](references/json-format-example.md).
- **Absolute GitHub URLs for in-repo links** -- relative paths break across notifications/previews/GraphQL. Use `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (branch ref for PR-scoped, SHA for permalinks).

##### Content quality

Mandatory while drafting `pr-descr_<slug>_pr<N>.md`. Same authority as the rules above.

- **Separate planned from incidental** -- group items under `**Planned:**` (PT-BR: `**Descobertas durante o desenvolvimento, também endereçadas:**`) and briefly explain each incidental.
  - **Drop the `**Planned:**` subsection** when Architecture/Decisions already cover per-ticket scope; keep only "Discovered along the way".
- **Decisions: title is the user-visible surprise, not internal mechanism** -- mechanism details go in sub-bullets. Examples: see [`decision-quality.md`](decision-quality.md).
- **Decisions: spell out the consequence if reversed when non-obvious** -- sub-bullet showing what breaks, in plain language (e.g. "exposed to injection or DoS", not "fail-loud"). Examples: same reference.
- **Reuse rationale: ONE concrete future use, not a speculative list** -- name a specific use case with ticket ref. Same reference.
- **CRITICAL: ZERO references to untracked session docs** -- never name `spec_<slug>.md`, `plan_<slug>.md`, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
  - Reviewer can't open them. Verify with `git ls-files <name>` before referencing any `.md`; if untracked, substitute the value or delete.
  - Applies to verbatim spec copies too. Exception: git-tracked files in the repo stay.
- **Don't repeat links across sections** -- if a Jira/PR link appears in "Link do Jira" or "Context", don't repeat in "References".
  - References is for follow-ups, external docs, or links not elsewhere.
- **No shorthand the reviewer can't resolve** -- team jargon, spec-internal acronyms, and implementation jargon in Planned items all assume context the reviewer lacks.
  - Team jargon (e.g. "shadow read"): define parenthetically on first use.
  - Spec acronyms ("AC", "FR/NFR"): spell out, or describe the scenario instead of citing the ID.
  - Implementation jargon in Planned items (e.g. "(injectable NestJS)"): describe what it does, not its shape.
- **"WARNING:" prefix on operational risks** -- prefix decisions/checklist items with "WARNING:" when they need human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations).
- **Explain "how is it different"** -- when introducing a new method/function, briefly say what makes it different from existing ones. Don't just name it.
- **Don't list types/interfaces** -- type names are visible in the diff; listing is noise.
- **Incidentals must change shared state to earn a bullet** -- only incidentals that modify docs, conventions, or shared infra.
  - Skip diff/commit-visible items (merge resolutions, auto-review responses, intra-branch refactors, task-internal cleanup).
  - Group small fixes (typos, log levels) into one bullet.
  - Test: would a future contributor searching "why does X exist?" find it valuable? If no, cut.

##### Evidence & locality

- **Collapsible sections for large content** -- `<details><summary>` for payloads, long examples, API responses.
- **Evidence locality: claim adjacent OR linked to artifact** -- every claim ("PASS", "validated", "AC met") needs a collapsible with the artifact OR a deep link.
  - The link IS locality. For long lists, deep-link to one appendix; don't bloat with inline collapsibles.
- **Manual test payloads live in the Evidences appendix, not inline in TAC** -- one collapsible per scenario; ACs deep-link to `#scenario-N` (anchor mechanics: `references/pr-template.md`).
- **No claim without evidence — drop the scenario, don't park it** -- can't paste the verifiable artifact → DROP the bullet.
  - "Covered by automated tests at path/spec.ts" isn't evidence (the diff already shows it).
  - Same for sections: one that can only say "TODO collect post-merge" gets removed — TODO sections rot.
- **Coverage-only scenarios — group, don't enumerate** -- when an automated suite covers many scenarios with no manual evidence, write ONE intro pointing to the suite + CI link.
  - Then list scenarios as plain bullets. Don't repeat empty `<details>covered by tests</details>` shells.

Bullet-style example (hard-to-scan vs scannable): see [`references/bullet-style-example.md`](references/bullet-style-example.md).

### 2.4. Resolve TODO-Questions

While drafting, you may leave `// TODO: Question - <factual question>` markers for non-obvious behavior the reviewer would want clarified. Example prompts: see [`references/decision-quality.md`](references/decision-quality.md).

Before step 3, resolve every TODO:

- **If the answer adds reviewer value** — investigate the code, replace the TODO with the answer inline (concise prose, not the full investigation).
- **If the answer is internal-only** — strip the TODO entirely.

A TODO must NEVER survive into the final PR push.

### 2.5. Verify density

Delegate to the `density-fixer` subagent (Agent tool) on `pr-descr_<slug>_pr<N>.md`; it must exit clean before step 3.

### 2.6. Verify body size

GitHub rejects a PR body over 65,536 characters — a hard API limit, distinct from the density cap.

Run `~/.claude/skills/create-pr/scripts/check-pr-body-size.sh pr-descr_<slug>_pr<N>.md`. Exit 0 = safe; exit 2 = close to the cap, trim soon; exit 3 = over the cap, trim now.

Over the cap? Re-scope embedded spec/plan content to fewer `## ` sections via `extract-md-sections.sh` (see step 1), then re-run this check before step 3.

### 3. Review with user

Present the pr-descr_<slug>_pr<N>.md content for review.
Wait for approval or edits before creating the PR.

### 3.5. Learn from user edits

Diff the user's edited pr-descr_<slug>_pr<N>.md against your original; infer the general rule behind each edit and propose updates to this skill's Writing Style for approval.
Apply approved updates before creating the PR — the skill self-improves.

### 4. Create the PR

- Push branch if needed (with -u)
- Create PR as **draft** using `gh pr create --draft --body-file pr-descr_<slug>_pr<N>.md --base <base-branch>`, where `<base-branch>` is the value resolved in step 1.
  - Resolved value was empty → drop `--base` from the command entirely, per step 1's fallback.
- **Updating an existing PR's body: never use `gh pr edit --body-file`** — write via the REST API instead:
  ```bash
  gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@pr-descr_<slug>_pr<N>.md
  ```
  - `gh pr edit` eagerly queries `repository.pullRequest.projectCards` (Projects **classic**); where classic Projects is sunset it errors on that query and the body write silently fails.
  - The REST `PATCH .../pulls/{n}` endpoint touches no Projects data, so `-F body=@file` (reads the value from a file) writes cleanly.
  - After either path, read the PR body back (`gh pr view <n> --json body`) and confirm the first lines match pr-descr_<slug>_pr<N>.md.
  - The GraphQL error can exit non-zero even when nothing was written.
- Return the PR URL
