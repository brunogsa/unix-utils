---
name: create-pr
description: "Create a GitHub PR with a rich description. Auto-detects spec_<slug>.md/plan_<slug>.md for context."
disable-model-invocation: false
---

# Create Pull Request

## Usage

`/create-pr` — no flags needed.

## Process

### 1. Gather context

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level):
  - One spec / one plan → use whichever exist, auto-resolved. Multiple of either → open question **(A) Spec/plan choice**: list them numbered.
  - None found → proceed from the changes digest (below) only, auto-resolved.
  - Extract every ` ```mermaid ``` ` fenced block from each resolved file; include all diagrams as collapsibles.
  - Beyond diagrams, prefer a curated slice over the full file — a full embed blows the body-size cap (step 2.6).
  - A spec/plan resolved → open question **(B) Sections to pull**: which `## ` sections matter, via `~/.claude/skills/create-pr/scripts/extract-md-sections.sh <file> "<section>" ["<section>" ...]`.
- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**: `<slug>` is the shared filename slug from the resolved `spec_<slug>.md`/`plan_<slug>.md`.
  - Fall back to the current branch name (`/` → `-`) when neither spec nor plan resolved.
  - Single PR plan or no plan resolved → omit `<N>`, auto-resolved.
  - Multiple `PR-N` entries in `## PR Breakdown` → open question **(C) Which PR-N**: set `<N>` to that number (e.g. `PR-2` → `2`).
- **Ask every open question (A/B/C) together, in one message, before continuing** -- skip any label that auto-resolved above.
  - Once answered, resolve `<slug>`/`<N>` and create `pr-descr_<slug>_pr<N>.md` right away with an HTML comment logging each answer.
  - Example: `<!-- step 1: spec=spec_foo.md; sections=Architecture,Evidences; PR=2/3 -->` -- GitHub hides HTML comments in rendered bodies.
  - It is this skill's durable record, not a separate scratchpad -- it survives a mid-flow compaction that would drop the answers.
- **Resolve the base branch (used below and in step 4)**: run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`.
  - Every PR targets this branch directly on GitHub, never a parent's branch.
  - Empty result (`origin/HEAD` unset) → omit `--base` in step 4; let it fall back to default.
- Check if branch is pushed.
- **Delegate diff/log reading to a subagent** -- dispatch one Agent declared as `subagent_type=general-purpose`, `title=Gather PR changes digest`, `model=sonnet`, foreground (step 2 needs the result immediately).
  - Render its `description` per CLAUDE.md's Agent-description form.
  - Give it the resolved base branch, the resolved spec/plan slices, and this skill's Writing Style section.
  - It reads git log vs base with **full commit bodies** -- the primary source for decisions, rationale, and scope changes (mining relies on `commit-standards`-shaped commits).
  - It reads git diff vs base, but returns only the **changes digest** (`references/changes-digest.md`), never the raw diff.

### 2. Write pr-descr_<slug>_pr<N>.md

Write `./pr-descr_<slug>_pr<N>.md` in cwd -- `<slug>` and `<N>` resolved per step 1 (`_pr<N>` dropped for a single-PR plan).

Keep the file step 1 created -- never overwrite its resolved-answers comment.

Author from the changes digest (step 1), the curated spec/plan slices, and the template -- not the raw diff.

**Escape hatch**: if the digest is insufficient for a specific section, read that file's targeted diff (`git diff <base> -- <path>`); never fall back to the full diff.

**CRITICAL: Always check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).
- If present, it's the base structure -- keep every section and checkbox, fill with rich content from spec/plan and the changes digest.
- Add extra sections WITHIN it (preferred) or as an appendix, **NEVER** replacing it.
- Mark checklist items `[x]` when applicable.
- If no template exists, use the default below.

**CRITICAL: Testable Acceptance Criteria and Evidences are MANDATORY** regardless of the template.
- If absent, add `## Testable Acceptance Criteria` and `## Evidences` inside the template structure.

#### Default Template

See `references/pr-template.md` for the full template. Guia de review template, time-estimate heuristic, file-role inference: [`references/reading-order-template.md`](references/reading-order-template.md) (PT-BR).

A full worked example, including the curated spec/plan embed from step 1: [`references/pr-description-example.md`](references/pr-description-example.md).

**Reading guide is qualitative, not taxonomic** -- each file entry describes what the reviewer *learns* there, not just role labels.
- Open with a rationale paragraph, bold the densest file, close with a minimum-viable-read shortcut.
- Layout + examples: [`references/decision-quality.md`](references/decision-quality.md).

#### Writing Style

**Meta-principle: reader has no context — provide it.**

The reviewer hasn't read your spec, plan, Jira ticket, or commits. Anything referenced must be self-contained or linked. Be concise but didactic.

**Second meta-principle: a small PR earns a small description** — a guideline, not a hard cap.

- **CRITICAL: Write the shortest version that still teaches** -- cut every sentence whose removal loses no reviewer-relevant information.
  - A one-file, one-decision PR should read in under a minute.
- **Never restate what the diff already shows** -- a sentence naming only a file, a line count, or "added X function" is noise the reviewer already sees.
  - Reserve prose for the *why* the diff can't show: the reasoning, the trade-off, the discarded alternative.
- **Evidences defaults to one line per claim, not a narrative** -- `**Claim** -- link/output`.
  - Expand to a paragraph only for a genuinely surprising or high-risk result.
  - Skip routine green-checks the CI tab already proves.

##### Required structure & mandatory content

- **Required PR structure** -- [`references/pr-template.md`](references/pr-template.md) owns the section list and order; every section is mandatory unless genuinely N/A.
  - It is ordered so the truth-criterion (Acceptance Criteria) precedes the design that satisfies it, and the appendices come last.
  - Never re-enumerate that list here — one enumeration is what keeps the two files from drifting apart.
- **Context section: business context + scannable layers, never one paragraph per ticket** -- extract the business problem from spec Background or commits.
  - Reviewers without ticket access need it to evaluate correctness.
  - Ordered layers:
  1. User-facing problem.
  2. Parent goal / epic.
  3. Neighboring dependencies' status.
  4. This PR's scope as bullets+sub-bullets per ticket.
- **Testable Acceptance Criteria — verbatim from spec** -- copy BDD content (Given/When/Then/And) from `## Testable Acceptance Criteria`.
  - Drop only "AC-N:" prefix.
  - Each AC ends with a one-line `> Covered by ...` pointer (skeleton in `references/pr-template.md`).

##### Formatting & rendering

- **Bullets** -- bold topic prefix (`**Topic** --`) so reviewers scan bold words first.
  - One short sentence per bullet, sub-bullets only when essential.
- **One sentence per paragraph for dense factual prose** -- a paragraph stacking ≥2 atomic claims (e.g., CI status + scope + count) splits into separate short paragraphs.
- **Section names AND body prose in the PR's primary language** -- translate headers and recurring body terms; engineering jargon stays English. Examples: [`references/decision-quality.md`](references/decision-quality.md).
- **Blank line BEFORE every list** -- prevents CommonMark merging ordered lists that don't start at `1.` into the preceding paragraph.
- **Never use markdown tables in PR bodies** -- they fragment scanning and break on narrow widths; replace with bullets where evidence is a sub-bullet or inline collapsible.
- **`>` blockquotes only for quoted content or per-bullet evidence pointers, not section intros** -- a `>` at section top creates a gray bar below H4 headings, inverting hierarchy.
- **JSON snippets: fully pretty-printed, one field per line** -- `JSON.stringify(obj, null, 2)` style, every nested object/array expanded vertically including single-key.
  - NEVER inline except `[]` empty arrays.
  - Example: [`references/json-format-example.md`](references/json-format-example.md).
- **Absolute GitHub URLs for in-repo links** -- relative paths break across notifications/previews/GraphQL; use `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (branch ref for PR-scoped, SHA for permalinks).

##### Content quality

- **Separate planned from incidental** -- two groups in Changes: `**Planned:**` (PT-BR `**Planejado:**`) and `**Discovered along the way:**` (PT-BR `**Descobertas durante o desenvolvimento, também endereçadas:**`).
  - Drop the incidental group when Architecture/Decisions already cover per-ticket scope.
  - Only incidentals that change shared state earn a bullet (docs, conventions, shared infra).
  - Skip diff/commit-visible items (merge resolutions, auto-review responses, refactors, cleanup) and group small fixes into one bullet.
  - Test: would a future contributor searching "why does X exist?" find it valuable?
- **Decisions: title the user-visible surprise, not the internal mechanism** -- mechanism details go in sub-bullets.
  - Spell out the consequence if reversed, in plain language (e.g. "exposed to injection or DoS", not "fail-loud").
- **Reuse rationale: ONE concrete future use, not a speculative list** -- name a specific use case with a ticket ref.
- **CRITICAL: ZERO references to untracked session docs** -- never name `spec_<slug>.md`, `plan_<slug>.md`, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
  - The reviewer can't open them, so verify with `git ls-files <name>` first.
  - Substitute the value or delete if untracked — git-tracked repo files stay.
- **Don't repeat links across sections** -- if a Jira/PR link appears in "Link do Jira" or "Context", don't repeat in "References" (that's for follow-ups, external docs, or links not elsewhere).
- **No shorthand the reviewer can't resolve** -- define team jargon on first use.
  - Spell out spec acronyms ("AC", "FR/NFR") and implementation jargon by what it does, not its shape.
- **"WARNING:" prefix on operational risks** -- prefix decisions/checklist items with "WARNING:" when they need human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations).
- **Explain differences, not just names** -- introducing a new method/function, briefly say what makes it different from existing ones; don't list types/interfaces.

##### Evidence & locality

- **Evidence locality: claim adjacent OR linked to artifact** -- every claim ("PASS", "validated", "AC met") needs a `<details><summary>` collapsible with the artifact, OR a deep link.
  - For long lists, deep-link to one appendix rather than bloat with inline collapsibles.
- **Manual test payloads live in the Evidences appendix, not inline in TAC** -- one collapsible per scenario.
  - ACs deep-link to `#scenario-N` (anchor mechanics: `references/pr-template.md`).
- **No claim without evidence — drop the scenario, don't park it** -- can't paste the verifiable artifact → DROP the bullet.
  - "Covered by automated tests at path/spec.ts" isn't evidence (the diff already shows it).
  - A "TODO collect post-merge" section gets removed since TODO sections rot.
- **Coverage-only scenarios — group, don't enumerate** -- when a suite covers many scenarios with no manual evidence:
  - Write ONE intro pointing to the suite + CI link.
  - List scenarios as plain bullets, not empty `<details>covered by tests</details>` shells.

Bullet-style example (hard-to-scan vs scannable): see [`references/bullet-style-example.md`](references/bullet-style-example.md).

### 2.4. Resolve TODO-Questions

While drafting, you may leave `// TODO: Question - <factual question>` markers for non-obvious behavior the reviewer would want clarified (example prompts: [`references/decision-quality.md`](references/decision-quality.md)).

Before step 3, resolve every TODO.
- If the answer adds reviewer value, investigate the code and replace the TODO with the answer inline (concise prose, not the full investigation).
- If internal-only, strip it entirely.
- A TODO must NEVER survive into the final PR push.

### 2.5. Verify density

Delegate to the `density-fixer` subagent (Agent tool) on `pr-descr_<slug>_pr<N>.md`; it must exit clean before step 3.

### 2.6. Verify body size

GitHub rejects a PR body over 65,536 characters — a hard API limit, distinct from the density cap.

Run `~/.claude/skills/create-pr/scripts/check-pr-body-size.sh pr-descr_<slug>_pr<N>.md`:
- Exit 0 → safe.
- Exit 2 → close to the cap (trim soon).
- Exit 3 → over the cap (re-scope embedded spec/plan content to fewer `## ` sections via `extract-md-sections.sh` from step 1, then re-run before proceeding).

### 3. Create the PR

Once steps 2.5 and 2.6 both pass, proceed directly — never pause for user review before pushing.

- Push branch if needed (with -u)
- Create PR as **draft** using `gh pr create --draft --body-file pr-descr_<slug>_pr<N>.md --base <base-branch>`, where `<base-branch>` is the value resolved in step 1 (dropped entirely when empty).
- **Updating an existing PR's body: never use `gh pr edit --body-file`** — it eagerly queries `repository.pullRequest.projectCards` (Projects classic).
  - Where that's sunset it errors and silently fails the write, sometimes still exiting 0.
  - Write via the REST API instead, which touches no Projects data:
  ```bash
  gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@pr-descr_<slug>_pr<N>.md
  ```
  - After either path, read the body back (`gh pr view <n> --json body`) and confirm it matches the file.
- Return the PR URL

### 3.5. Learn from user feedback

If the user later changes the pushed PR body — in chat, or by hand-editing pr-descr_<slug>_pr<N>.md — diff the edit against the pushed version.

Per CLAUDE.md's infer-the-general-rule rule, propose the inferred rule as a Writing Style update, and apply it once approved.
