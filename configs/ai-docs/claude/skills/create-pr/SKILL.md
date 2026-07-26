---
name: create-pr
description: "Create a GitHub PR with a rich description. Auto-detects spec_<slug>.md/plan_<slug>.md for context."
disable-model-invocation: false
---

# Create Pull Request

## Usage

`/create-pr` — no flags needed.

Load the `doc-standards` skill before drafting — a PR description is a standalone doc, so its density cap, BLUF ordering, and collapse rules all apply.

This skill adds only what is specific to a PR, and never restates a rule `doc-standards` already owns.

## CRITICAL: the non-overlap invariant

**No content appears twice in one PR body** -- every section answers one question no other section answers.

- **Each body section owns exactly one question** -- content answering another section's question belongs there, not here.
  - Review guide → in what order do I read the files? Context → why does this PR exist? Changes → what behavior is different now?
  - Decisions → what was chosen over what, and why? Architecture → how do the pieces fit and flow? Evidences → how do I know it works?
- **A diagram outranks prose that narrates it** -- once a diagram encodes a flow, an order, or a classification, no bullet restates it.
  - A decision bullet may then add only what the diagram cannot encode: the why, the discarded alternative, or the consequence if reversed.
- **The review guide already enumerates the changed files** -- so a Changes bullet names the behavior that changed, never the file that changed.
- **CRITICAL: Copy reused content verbatim — never regenerate it** -- when a section is moved or reused, paste it; do not re-author it from the same source.
  - Regeneration paraphrases, and a paraphrase reads as new content while carrying the same facts, so the duplicate survives every review pass undetected.
- **The appendix is a complement, never a second copy** -- it exists for deep divers and AI reviewers.
  - Anything the body already says at the same altitude is stripped out of it.
  - Diagrams live in Architecture, expanded by default, and are removed from the appendix — they are the fastest part of a PR to review.
  - No spec resolved → no acceptance-criteria and no decision-catalog section anywhere; the tests and the code carry them alone.
- **CRITICAL: One subject may appear in both places ONLY at different altitudes** -- the body carries the summary or index, the appendix the full statement.
  - Test: if the two could be swapped without the reader noticing, it is a duplicate, not a summary.
  - Acceptance criteria — body states only how many are covered, appendix holds each one's Given/When/Then.
  - Decisions — body summarizes the main ones, appendix holds the full catalog verbatim from the spec/plan.
- **Links obey it too** -- a Jira/PR link already in "Jira link" or "Context" never repeats in "References", which is for follow-ups and external docs only.
- Check it before every push: any fact, diagram, decision, or link rendered in two places is a defect, not thoroughness.

## CRITICAL: the one-page goal

**The ideal description's visible text fits 64 rendered lines** -- a reviewer reaches the end of the story without scrolling, then scrolls only to read the diff.

- **CRITICAL: The 64 lines are allocated per section, never spent first-come** -- a section that overruns is borrowing from one the reviewer still has to read.
  - Jira/Linear and related-PR links: **4**.
  - Context: **17** — the heading plus at most 4 paragraphs of at most 4 lines each.
  - Changes: **9** — the heading plus 8 bullets or sub-bullets, counting the two group labels.
  - Decisions: **19** — 3 headings plus 8 bullets for Functional and 8 for Technical.
  - Architecture: **5** — the heading plus at most 4 diagrams, every one left expanded.
  - Evidences: **4** — the heading, the counted-tests line, and up to 3 collapsed manual scenarios.
  - Appendix: **6** — the heading, at most 2 lines of intro, and one collapsed block per subsection.
- **Unused Functional allowance transfers to Technical decisions, and back** -- 3 functional decisions free 5 more lines for technical ones.
  - No other pair transfers, since those two are the only sections whose split swings with the PR being mostly product or mostly implementation.
- **Only rendered text counts** -- images, diagrams, blank lines, empty anchors, and collapsed content are free.
  - A collapsed `<details>` costs only what its `<summary>` renders as, which is why the appendix fits in 6 lines however long it grows.
  - So the first lever is never "delete content" — it is "move content to where it costs nothing", which is what the appendix and the collapsed blocks exist for.
- **CRITICAL: A line over ~95 rendered characters costs two** -- it wraps in GitHub's description column, so its cost doubles while the text still reads as one bullet.
  - This is invisible to the density check, whose cap is 256 characters — nearly three rendered lines of budget spent inside one compliant bullet.
  - Rendered, not source: a markdown link shows only its label, so a 200-character URL costs nothing.
- **Measure it, don't estimate it** -- `~/.claude/skills/create-pr/scripts/check-pr-page-fit.sh <file>` prints the total plus a per-section breakdown to check against the budgets above.
  - It prints that breakdown even when it passes, because a body can clear the 64-line total while one section has quietly eaten another's allowance.
- **CRITICAL: Measure the ideal description, never the final body** -- a repo template's structure is arbitrary, so the script cannot attribute its lines to a budgeted section.
- **Cut in this order when a section is over** -- each step moves content down an altitude rather than destroying it.
  - Repack every line past the wrap width first — 4 lines of 90 characters cost 4, while the same words as 3 lines of 120 cost 6.
  - Drop any bullet a diagram already encodes fully — the diagram is free and the bullet is not.
  - Cut Decisions to the ones that change behavior, cost, or risk; the rest already sit in the appendix catalog.
  - Merge Changes bullets that describe the same user-visible delta into one line.
  - Move a manual scenario's methodology prose inside its own collapsed block, where it costs nothing.
- **Collapse what is consulted, never what is read** -- `doc-standards` owns this rule; applied here, manual scenarios and appendix subsections collapse, but Context, Changes, and Decisions never do.
  - Hiding a section a reviewer is supposed to read means nobody reviews it, which costs more than the lines it saved.
- **A body that cannot fit after every cut is a PR that is too big** -- three screens of prose do not make a large diff reviewable.
  - Say so to the user and recommend splitting the PR, rather than raising the budget silently.

## Process

### 1. Gather context

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level):
  - One spec / one plan → use whichever exist, auto-resolved. Multiple of either → open question **(A) Spec/plan choice**: list them numbered.
  - None found → proceed from the changes digest (below) only, auto-resolved.
  - Extract every ` ```mermaid ``` ` fenced block from each resolved file — these become the Architecture section, and are excluded from the appendix.
- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**: `<slug>` is the shared filename slug from the resolved `spec_<slug>.md`/`plan_<slug>.md`.
  - Fall back to the current branch name (`/` → `-`) when neither spec nor plan resolved.
  - Single PR plan or no plan resolved → omit `<N>`, auto-resolved.
  - Multiple `PR-N` entries in `## PR Breakdown` → open question **(B) Which PR-N**: set `<N>` to that number (e.g. `PR-2` → `2`).
- **Ask every open question (A/B) together, in one message, before continuing** -- skip any label that auto-resolved above.
  - Once answered, resolve `<slug>`/`<N>` and create `pr-descr_<slug>_pr<N>.md` right away with an HTML comment logging each answer.
  - Example: `<!-- step 1: spec=spec_foo.md; PR=2/3 -->` -- GitHub hides HTML comments in rendered bodies.
  - It is this skill's durable record, not a separate scratchpad -- it survives a mid-flow compaction that would drop the answers.
- **Derive the appendix's section list — never ask the user for it** -- it is the resolved spec/plan minus every section the body already renders.
  - Excluded, because the body owns them at the same altitude: mermaid diagrams, Background/Context, Goals, User Stories, and the plan's task breakdown.
  - Included: Testable Acceptance Criteria, Functional Decisions, Technical Decisions, Non-Functional/Technical Requirements, Test Design, and any section with no body counterpart.
  - Decisions stay here in FULL and verbatim — the body's Decisions section is a higher-altitude summary of the main ones, not a replacement.
  - `### References` joins them there as authored content, so the appendix survives even when no spec/plan resolved.
  - Extract them with `~/.claude/skills/create-pr/scripts/extract-md-sections.sh <file> "<section>" ["<section>" ...]`.
- **Resolve the base branch (used below and in step 5)**: run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`.
  - Every PR targets this branch directly on GitHub, never a parent's branch.
  - Empty result (`origin/HEAD` unset) → omit `--base` in step 5; let it fall back to default.
- Check if branch is pushed.
- **Delegate diff/log reading to a subagent** -- dispatch `agent(subAgent=general-purpose, title=Gather PR changes digest, model=sonnet)`, foreground (step 2 needs the result immediately).
  - Give it the resolved base branch, the resolved spec/plan slices, and this skill's Writing Style section.
  - It reads git log vs base with **full commit bodies** -- the primary source for decisions, rationale, and scope changes (mining relies on `commit-standards`-shaped commits).
  - It reads git diff vs base, but returns only the **changes digest** (`references/changes-digest.md`), never the raw diff.

### 2. Compose the ideal description

**CRITICAL: The main session orchestrates and never composes the prose itself** -- dispatch an Agent, then validate its output against the artifact.

- `agent(subAgent=general-purpose, title=Compose ideal PR description, model=sonnet)`, foreground (step 3 gates on the file it writes).
  - Give it the changes digest, the derived appendix sections, the resolved `<slug>`/`<N>`, and this skill's one-page-goal, non-overlap, and Writing Style sections.

**CRITICAL: It writes the IDEAL description in this skill's own format, ignoring any repo template** -- the repo's template is step 4's problem, not its.
- The format has to stay stable, because `check-pr-page-fit.sh` can only hold a section to its budget when it recognizes that section.
- The ideal description is never pushed as-is when a repo template exists; it is the single input step 4 builds the final body from.

Output: `./pr-descr_<slug>_pr<N>.md` in cwd -- `<slug>` and `<N>` resolved per step 1 (`_pr<N>` dropped for a single-PR plan).

Keep the file step 1 created -- never overwrite its resolved-answers comment.

Author from the changes digest (step 1), the derived appendix sections, and the template -- not the raw diff.

**Escape hatch**: if the digest is insufficient for a specific section, read that file's targeted diff (`git diff <base> -- <path>`); never fall back to the full diff.

#### Default Template

See `references/pr-template.md` for the full template. Guia de review template, time-estimate heuristic, file-role inference: [`references/reading-order-template.md`](references/reading-order-template.md) (PT-BR).

A full worked example, including the derived appendix from step 1: [`references/pr-description-example.md`](references/pr-description-example.md).

**Reading guide is qualitative, not taxonomic** -- each file entry describes what the reviewer *learns* there, not just role labels.
- Open with a rationale paragraph, bold the densest file, close with a minimum-viable-read shortcut.
- Layout + examples: [`references/decision-quality.md`](references/decision-quality.md).

#### Writing Style

**Meta-principle: reader has no context — provide it.**

The reviewer hasn't read your spec, plan, Jira ticket, or commits. Anything referenced must be self-contained or linked. Be concise but didactic.

**Second meta-principle: a small PR earns a small description** — a guideline, not a hard cap.

##### What to write

- **CRITICAL: Write the shortest version that still teaches** -- cut every sentence whose removal loses no reviewer-relevant information.
  - A one-file, one-decision PR should read in under a minute.
- **Never restate what the diff already shows** -- a sentence naming only a file, a line count, or "added X function" is noise the reviewer already sees.
  - Reserve prose for the *why* the diff can't show: the reasoning, the trade-off, the discarded alternative.
- **Required PR structure** -- [`references/pr-template.md`](references/pr-template.md) owns the section list and order; every section is mandatory unless genuinely N/A.
  - Never re-enumerate that list here — one enumeration is what keeps the two files from drifting apart.
- **Context section: business context + scannable layers, never one paragraph per ticket** -- extract the business problem from spec Background or commits.
  - Reviewers without ticket access need it to evaluate correctness.
  - Ordered layers:
  1. User-facing problem.
  2. Parent goal / epic.
  3. Neighboring dependencies' status.
  4. This PR's scope as bullets+sub-bullets per ticket.
- **CRITICAL: Changes reads as a changelog, not a narrative** -- flat one-line bullets in patch-notes voice, no sub-bullets, no `**Topic** --` prefix.
  - A bullet states the behavior that is different now; a reader should get the whole delta by skimming the bullets alone.
- **Separate planned from incidental** -- two groups in Changes: `**Planned:**` (PT-BR `**Planejado:**`) and `**Discovered along the way:**` (PT-BR `**Descobertas durante o desenvolvimento, também endereçadas:**`).
  - Drop the incidental group when Architecture/Decisions already cover per-ticket scope.
  - Only incidentals that change shared state earn a bullet (docs, conventions, shared infra).
  - Skip diff/commit-visible items (merge resolutions, auto-review responses, refactors, cleanup) and group small fixes into one bullet.
  - Test: would a future contributor searching "why does X exist?" find it valuable?
- **CRITICAL: The body summarizes the MAIN decisions at a higher altitude than the spec/plan** -- the full catalog stays in the appendix, so the body is a digest, never a copy.
  - A decision the reader could settle by opening the code is low-level — a field choice, a file location, a signature, a type. Appendix only.
  - A decision earns the body only when it changes behavior, cost, or risk in a way no single file reveals.
  - Expect a handful in the body against a dozen-plus in the catalog; if every catalog entry survived, the altitude cut was not applied.
- **Every body decision carries decided → why → considered, in that order** -- the bold line states what was decided, and the why follows it on the same line.
  - A `Considered:` sub-bullet then names the rejected alternative and why it lost.
  - Omit `Considered` only when no alternative was genuinely weighed — never write "none" or "N/A".
- **Decisions split into `### Functional` then `### Technical`** -- functional is a choice a non-engineer stakeholder could disagree with; technical is one only an engineer would weigh in on.
  - Omit either subsection when it has no decisions, rather than padding it with a placeholder.
- **Decisions: title the user-visible surprise, not the internal mechanism** -- mechanism details go in sub-bullets.
  - Spell out the consequence if reversed, in plain language (e.g. "exposed to injection or DoS", not "fail-loud").
  - Drop any bullet a diagram below encodes FULLY; keep one that adds the why, the rejected alternative, or the cost of reversing it.
- **Reuse rationale: ONE concrete future use, not a speculative list** -- name a specific use case with a ticket ref.
- **Explain differences, not just names** -- introducing a new method/function, briefly say what makes it different from existing ones; don't list types/interfaces.
- **"WARNING:" prefix on operational risks** -- prefix decisions/checklist items with "WARNING:" when they need human coordination (maintenance windows, on-call handoff, manual deploy steps, irreversible migrations).
- **CRITICAL: ZERO references to untracked session docs** -- never name `spec_<slug>.md`, `plan_<slug>.md`, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
  - The reviewer can't open them, so verify with `git ls-files <name>` first.
  - Substitute the value or delete if untracked — git-tracked repo files stay.
  - This outranks "copy reused content verbatim": pasted spec/plan text is stripped of every `AC-N`/`PR-N`/`D-N`/`R-N`/`OQ-N` token, in the appendix as much as the body.
  - Replace an inline token with the behavior it names; drop it outright when the surrounding sentence already names that behavior.
- **No shorthand the reviewer can't resolve** -- define team jargon, spec acronyms ("AC", "FR/NFR"), and implementation jargon on first use, per `doc-standards`' self-describing rules.

##### Evidence

- **CRITICAL: Evidences proves the work was tested, in the fewest words that convince** -- automated coverage first, then manual evidence; nothing else belongs here.
- **CRITICAL: Automated coverage is ONE counted line, and nothing more** -- how many tests were added and how many acceptance criteria they cover, pointing at the appendix for the criteria themselves.
  - A bare "covered by automated tests at path/spec.ts" is not evidence; the counted line is, because the number is checkable against the diff.
- **CRITICAL: Never index the acceptance criteria in the body** -- no per-criterion bullets, and no happy-path / failure / corner-case groups.
  - The tests already prove coverage and the appendix already states each criterion, so a body-side index is a third copy that costs a third of the page.
- **Manual evidence covers only what automation could not prove** -- omit the part entirely when everything is automated.
- **Every manual scenario is a `<details>` COLLAPSED by default** -- the reader expands only what they want to audit.
  - Each is preceded by an explicit `<a id="scenario-N"></a>` anchor, since GitHub generates anchors from headings but never from `<summary>` text.
  - Its methodology goes INSIDE the collapsed block: 2-3 sentences on what you ran, against what, and what you looked at, then just enough output to show it passed.
  - Methodology left above the block is visible prose the budget pays for, while the same words inside it cost nothing.
- **No claim without evidence — drop the scenario, don't park it** -- can't paste the verifiable artifact → DROP the bullet.
  - A "TODO collect post-merge" section gets removed since TODO sections rot.
- **Skip what the checks tab already renders as a badge** -- lint, generic build, and security scans; screenshots only when UI actually changed.

##### How to format it

- **Bullets** -- bold topic prefix (`**Topic** --`) so reviewers scan bold words first.
  - One short sentence per bullet, sub-bullets only when essential.
  - Hard-to-scan vs scannable: [`references/bullet-style-example.md`](references/bullet-style-example.md).
- **One sentence per paragraph for dense factual prose** -- a paragraph stacking ≥2 atomic claims (e.g., CI status + scope + count) splits into separate short paragraphs.
- **Section names AND body prose in the PR's primary language** -- translate headers and recurring body terms; engineering jargon stays English. Examples: [`references/decision-quality.md`](references/decision-quality.md).
- **Blank line BEFORE every list** -- prevents CommonMark merging ordered lists that don't start at `1.` into the preceding paragraph.
- **Never use markdown tables in PR bodies** -- they fragment scanning and break on narrow widths; replace with bullets where evidence is a sub-bullet or inline collapsible.
- **`>` blockquotes only for quoted content or per-bullet evidence pointers, not section intros** -- a `>` at section top creates a gray bar below H4 headings, inverting hierarchy.
- **JSON snippets: fully pretty-printed, one field per line** -- `JSON.stringify(obj, null, 2)` style, every nested object/array expanded vertically including single-key.
  - NEVER inline except `[]` empty arrays.
  - Example: [`references/json-format-example.md`](references/json-format-example.md).
- **Absolute GitHub URLs for in-repo links** -- relative paths break across notifications/previews/GraphQL; use `https://github.com/<owner>/<repo>/blob/<branch>/<path>` (branch ref for PR-scoped, SHA for permalinks).

### 3. Verify the ideal description

All three checks below must pass before step 4. Never pause for user review — once they pass, continue.

- **Resolve every TODO-Question** -- while drafting you may leave `// TODO: Question - <factual question>` markers for non-obvious behavior a reviewer would want clarified (example prompts: [`references/decision-quality.md`](references/decision-quality.md)).
  - Answer adds reviewer value → investigate the code and replace the TODO with the answer inline, as concise prose rather than the full investigation.
  - Internal-only → strip it entirely.
  - A TODO must NEVER survive into the final PR push.
- **Density** -- dispatch `agent(subAgent=density-fixer, title=Fix PR description density)` on `pr-descr_<slug>_pr<N>.md`; it must exit clean.
- **Page fit** -- run `~/.claude/skills/create-pr/scripts/check-pr-page-fit.sh pr-descr_<slug>_pr<N>.md`.
  - Exit 0 → fits, but still read the breakdown it prints and hold every section to its own budget.
  - Exit 2 → close; trim the worst section in the breakdown.
  - Exit 3 → over; apply the cuts in the one-page-goal rule above, then re-run.

### 4. Fit the ideal description to the repo's PR template

**Check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

**No template found → the ideal description IS the final body** -- skip the rest of this step; step 5 pushes `pr-descr_<slug>_pr<N>.md`.

**Template found → dispatch a second Agent to merge the two** -- the main session again orchestrates rather than composing.
- `agent(subAgent=general-purpose, title=Fit PR description to repo template, model=sonnet)`, foreground (step 5 gates on its output).
- Give it exactly two inputs: the verified `pr-descr_<slug>_pr<N>.md` and the repo's template file.
- It writes `./pr-body_<slug>_pr<N>.md`, and that file — not the ideal description — is what step 5 pushes.

**CRITICAL: The repo's template is the base structure, never the thing being replaced.**
- Keep every section and checkbox, filling them from the ideal description rather than re-deriving content from the diff.
- Preserve its checklist verbatim -- never rewrite, reorder, or prune the items; the default template carries no checklist, so the repo's is the only one.
- Mark checklist items `[x]` when applicable.
- Add whatever the ideal description carries that the template has no slot for WITHIN it (preferred) or as an appendix, **NEVER** replacing it.
- **CRITICAL: `## Evidences` is MANDATORY** regardless of the template -- add it inside the template structure when absent.

**CRITICAL: Never run the page-fit check on the final body** -- the budget was already enforced on the ideal description, the only source the final body draws content from.

### 5. Create the PR

- **Body size** -- GitHub rejects a PR body over 65,536 characters, a hard API limit distinct from the density cap.
  - Run `~/.claude/skills/create-pr/scripts/check-pr-body-size.sh <file>` on the file this step pushes, since the repo's template adds content the ideal description never carried.
  - Exit 0 → safe. Exit 2 → close to the cap, trim soon.
  - Exit 3 → over the cap: drop the appendix's lowest-value sections (Test Design first, then Non-Functional Requirements) via `extract-md-sections.sh`, then re-run before proceeding.
- Push branch if needed (with -u)
- Create PR as **draft** using `gh pr create --draft --body-file <file> --base <base-branch>`.
  - `<file>` is the one step 4 resolved; `<base-branch>` is the value step 1 resolved, dropped entirely when empty.
- **Updating an existing PR's body: never use `gh pr edit --body-file`** — it eagerly queries `repository.pullRequest.projectCards` (Projects classic).
  - Where that's sunset it errors and silently fails the write, sometimes still exiting 0.
  - Write via the REST API instead, which touches no Projects data:
  ```bash
  gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>
  ```
  - After either path, read the body back (`gh pr view <n> --json body`) and confirm it matches the file.
- Return the PR URL

### 6. Learn from user feedback

If the user later changes the pushed PR body — in chat, or by hand-editing either `.md` — diff the edit against the pushed version.

Apply the fix to `pr-descr_<slug>_pr<N>.md` first, then regenerate the final body from it, so the two never drift.

Per CLAUDE.md's infer-the-general-rule rule, propose the inferred rule as a Writing Style update, and apply it once approved.

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
