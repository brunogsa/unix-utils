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
  - Review guide: **1** — its collapsed `<summary>`, which the script charges before the first heading rather than to a section below it.
  - Jira/Linear and related-PR links: **4**.
  - Context: **17** — the heading plus at most 4 paragraphs of at most 4 lines each.
  - Changes: **9** — the heading plus 8 flat bullets, counting the two group labels.
  - Decisions: **18** — 3 headings plus 8 bullets for Functional and 7 for Technical.
  - Architecture: **5** — the heading plus at most 4 diagrams, every one left expanded.
  - Evidences: **5** — the heading, the counted-tests line, and up to 3 collapsed manual scenarios.
  - Appendix: **5** — the heading, at most 1 line of intro, and one collapsed block per subsection.
  - The eight entries sum to exactly 64, which is what makes "never spent first-come" checkable rather than aspirational.
- **Unused Functional allowance transfers to Technical decisions, and back** -- 3 functional decisions free 5 more lines for technical ones.
  - No other pair transfers, since those two are the only sections whose split swings with the PR being mostly product or mostly implementation.
- **Only rendered text counts** -- images, diagrams, blank lines, empty anchors, and collapsed content are free.
  - A collapsed `<details>` costs only what its `<summary>` renders as, which is why the appendix fits in 5 lines however long it grows.
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
- **A body over the 64 lines goes back through the cut order until it fits — it never ships over** -- re-cut, re-measure, repeat.
  - Never raise the budget to close the gap, and never push the overrun with the overrunning section merely named.
  - The cut order always has a next move, since every step relocates content to where it renders free instead of deleting it.
  - That is why "irreducible" always means the cut order was not run to the end.
  - Splitting the PR is not the remedy: the diff is already written, the appendix carries the detail, and the code carries the rest.

## Process

**Seed the TaskList before step 1 runs** -- one `[Reminder]` entry for each of steps 1-5, in execution order.

- A skipped step then stays visible as pending across a compaction, which the numbered steps alone do not survive.
- Step 6 gets no entry -- it runs only if the user asks for a change after the push, so a pending reminder would never complete.

### 1. Gather context

- Discover spec/plan in cwd by glob `spec_*.md plan_*.md` (top-level):
  - One spec / one plan → use whichever exist, auto-resolved. Multiple of either → open question **(A) Spec/plan choice**: list them numbered.
  - None found → proceed from the changes digest (below) only, auto-resolved.
- **Resolve the output filename's `<slug>` and `<N>` (used in step 2)**: `<slug>` is the shared filename slug from the resolved spec/plan filenames.
  - Fall back to the current branch name (`/` → `-`) when neither spec nor plan resolved.
  - Single PR plan or no plan resolved → omit `_pr<N>` entirely, auto-resolved.
  - Multiple `PR-N` entries in `## PR Breakdown` → open question **(B) Which PR-N**: set `<N>` to that number (e.g. `PR-2` → `2`).
- **Ask (A) and (B) in ONE interview, as two separate questions** -- a single `AskUserQuestion` call carrying both; skip either label that auto-resolved above.
  - They resolve different things — which source file to read, and which slice of a multi-PR plan this is — so one merged question would force two answers into one choice.

- Once answered, create `./pr_<slug>_pr<N>.ideal.md` right away with an HTML comment logging each answer.
  - Example: `<!-- step 1: spec=<resolved spec>; PR=2/3 -->` -- GitHub hides HTML comments in rendered bodies.
  - It is this skill's durable record, not a separate scratchpad -- it survives a mid-flow compaction that would drop the answers.
- **Derive the appendix's section list — never ask the user for it** -- it is the resolved spec/plan minus every section the body already renders.
  - Excluded, because the body owns them at the same altitude: mermaid diagrams, Background/Context, Goals, User Stories, and the plan's task breakdown.
  - Included: Testable Acceptance Criteria, Functional Decisions, Technical Decisions, Non-Functional/Technical Requirements, Test Design, and any section with no body counterpart.
  - Decisions stay here in FULL and verbatim — the body's Decisions section is a higher-altitude summary of the main ones, not a replacement.
  - `### References` joins them there as authored content, so the appendix survives even when no spec/plan resolved.

- **CRITICAL: Both halves of a spec/plan reach the PR by script, never by re-authoring** -- the main session derives the list, and step 2's agent runs the extractors.
  - Sections: `~/.claude/skills/create-pr/scripts/extract-md-sections.sh <file> "<section>" ["<section>" ...]`.
  - Diagrams: `~/.claude/skills/create-pr/scripts/extract-mermaid-blocks.sh <file> [<file> ...]` — every fenced `mermaid` block becomes the Architecture section, and leaves the appendix.
  - A re-summarized section or a re-drawn diagram diverges from what the spec/plan was reviewed against, and nothing downstream catches the divergence.
- **Resolve the base branch (used in step 5)**: run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`.
  - Every PR targets this branch directly on GitHub, never a parent's branch.
  - Empty result (`origin/HEAD` unset) → omit `--base` in step 5; let it fall back to default.
- **Ensure the branch is pushed** -- `git push -u origin <branch>` when it has no upstream, so step 5 only has to create the PR.
- **Delegate diff/log reading to a subagent** -- dispatch `agent(subAgent=changes-gatherer, title=Gather PR changes digest)`, foreground (step 2 needs the result immediately).
  - Give it the resolved base branch and a `/tmp` artifact path; it writes the full commit log and diff there and returns only the **changes digest** (`references/changes-digest.md`).
  - The digest is what step 2 authors from, so the raw diff never enters the main session's context.

### 2. Compose the ideal description

**CRITICAL: The main session orchestrates and never composes the prose itself** -- dispatch the agent, then validate its output against the artifact.

- `agent(subAgent=pr-writer, title=Compose ideal PR description)` in mode `ideal`, foreground (step 3 gates on the file it writes).
  - Give it four things: the changes digest, the resolved spec/plan paths, the derived appendix section list, and the output path `./pr_<slug>_pr<N>.ideal.md`.
  - It loads this skill and `doc-standards` itself, runs the extractors, and loops on the density and page-fit gates before returning — none of that belongs in the dispatch prompt.

**CRITICAL: It writes the IDEAL description in this skill's own format, ignoring any repo template** -- the repo's template is step 4's problem, not its.
- The format has to stay stable, because `check-pr-page-fit.sh` can only hold a section to its budget when it recognizes that section.
- The ideal description is never pushed as-is when a repo template exists; it is the single input step 4 builds the final body from.

Output: `./pr_<slug>_pr<N>.ideal.md` in cwd -- `<slug>` and `<N>` resolved per step 1 (`_pr<N>` dropped for a single-PR plan).

Keep the file step 1 created -- never overwrite its resolved-answers comment.

Author from the changes digest (step 1), the extracted spec/plan sections, and the template -- not the raw diff.

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
- **CRITICAL: ZERO references to untracked session docs** -- never name the spec file, the plan file, gitignored `.md`, internal task/AC numbers, commit SHAs in prose, or internal dependency files.
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

Re-run both gates on `pr_<slug>_pr<N>.ideal.md` in the main session, even though the agent already looped on them.

- What is being confirmed is the artifact, not the agent's account of the artifact.
- **Density** -- `~/.claude/skills/doc-standards/scripts/check-density.sh <file>` must print no violation.
- **Page fit** -- `~/.claude/skills/create-pr/scripts/check-pr-page-fit.sh <file>` must not exit 3.
  - Exit 0 → fits with room. Exit 2 → still fits, with under a fifth of the page left. Exit 3 → over the 64 lines, and the only failing outcome.
  - Read the per-section breakdown on every outcome, pass included: a body can clear the 64-line total while one section has quietly eaten another's allowance.
- Either gate failing → send the file back to the same `pr-writer` agent with the script output, and never hand-fix the prose in the main session.
  - Loop that hand-off until the gate stops failing — a body over the budget is never pushed, per the one-page goal's cut-until-it-fits rule.

**Never pause for user review** -- once both gates pass, continue straight to step 4.

### 4. Fit the ideal description to the repo's PR template

**Check `.github/` for a PR template** (`pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`).

**No template found → copy the ideal description into the final body** -- `cp pr_<slug>_pr<N>.ideal.md pr_<slug>_pr<N>.final.md`, then skip the rest of this step.
- The copy keeps one push path instead of two: step 5 always pushes the `.final.md`, whatever produced it.

**Template found → dispatch the merge** -- the main session again orchestrates rather than composing.
- `agent(subAgent=pr-writer, title=Fit PR description to repo template)` in mode `final`, foreground (step 5 gates on its output).
- Give it exactly three paths: the verified `pr_<slug>_pr<N>.ideal.md`, the repo's template file, and the output `./pr_<slug>_pr<N>.final.md`.
- It re-reads the rules below from this skill, and runs the body-size gate itself.

**CRITICAL: The repo's template is the base structure, never the thing being replaced.**
- Keep every section and checkbox, filling them from the ideal description rather than re-deriving content from the diff.
- Preserve its checklist verbatim -- never rewrite, reorder, or prune the items; the default template carries no checklist, so the repo's is the only one.
- Mark checklist items `[x]` when applicable.
- Add whatever the ideal description carries that the template has no slot for WITHIN it (preferred) or as an appendix, **NEVER** replacing it.
- **CRITICAL: `## Evidences` is MANDATORY** regardless of the template -- add it inside the template structure when absent.

**CRITICAL: Never run the page-fit check on the final body** -- the budget was already enforced on the ideal description, the only source the final body draws content from.

### 5. Create the draft PR

- **Body size** -- GitHub rejects a PR body over 65,536 characters, a hard API limit distinct from the density cap.
  - Run `~/.claude/skills/create-pr/scripts/check-pr-body-size.sh pr_<slug>_pr<N>.final.md`, which is the only gate the no-template copy path has ever run on that file.
  - Exit 0 → safe. Exit 2 → close to the cap, trim soon.
  - Exit 3 → over the cap: send it back to `pr-writer`, which drops the appendix's lowest-value sections (Test Design first, then Non-Functional Requirements) and re-checks.
- **Create the PR as a draft with no chat-side review gate** -- `gh pr create --draft --body-file pr_<slug>_pr<N>.final.md --base <base-branch>`.
  - `<base-branch>` is the value step 1 resolved, dropped entirely when empty.
  - The user reviews on GitHub, where the rendered body is the artifact they will actually judge; a chat-side approval would review a different one.
- Return the PR URL.

### 6. Apply post-push changes

The user may hand-edit the body on GitHub, or ask for a change in chat. Either way:

- **Pull GitHub's current body into the file first** -- `gh pr view <n> --json body`, so a hand-edit made there is not overwritten by the next push.
- **Edit `pr_<slug>_pr<N>.final.md` only** -- the `.ideal.md` is deliberately left to drift once the PR exists.
  - Re-deriving the final body from it would discard the user's own edits, and nobody reads the ideal description after the push.
- **Confirm with the user before writing to GitHub** -- the local edit is cheap to revise; the pushed body notifies reviewers.
- **Updating an existing PR's body: never use `gh pr edit --body-file`** — it eagerly queries `repository.pullRequest.projectCards` (Projects classic).
  - Where that's sunset it errors and silently fails the write, sometimes still exiting 0.
  - Write via the REST API instead, which touches no Projects data:
  ```bash
  gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>
  ```
  - Afterwards read the body back (`gh pr view <n> --json body`) and confirm it matches the file.

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
