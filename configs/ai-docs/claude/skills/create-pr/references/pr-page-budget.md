# PR body budget: non-overlap invariant and one-page goal

Read before drafting a PR body. `pr-writer` loads this; `SKILL.md` points here.

## CRITICAL: the non-overlap invariant

**No content appears twice** -- each section answers one unique question.

- **Each body section owns exactly one question** -- answers belong nowhere else.
  - Review guide → order of reading? Context → why this PR? Changes → what's different?

  - Decisions → what chosen over what, why? Architecture → how pieces fit? Evidences → verification?

- **A diagram outranks prose that restates it** -- no bullet repeats encoded flows.
  - Decision bullets add only what diagrams can't: why, discarded options, consequences.

- **Review guide lists changed files** -- so Changes names behavior, not files.
- **CRITICAL: Copy reused content verbatim** -- paste when moved; don't re-author.
  - Paraphrasing hides duplicates as new content.

- **Appendix complements, never copies** -- duplicates at the same altitude are stripped.
  - Diagrams live in Architecture, expanded, removed from appendix.
  - No spec resolved → no acceptance-criteria or decision sections; code carries them.

- **CRITICAL: One subject may appear both places ONLY at different altitudes** -- body summary, appendix full.
  - Test: if swappable without notice, it's duplicate not summary.
  - Acceptance criteria: body states count, appendix holds Given/When/Then.
  - Decisions: body summarizes, appendix holds full catalog verbatim.

- **Links obey it** -- don't repeat in References, reserved for follow-ups.

- Before push: duplicated facts, diagrams, decisions, or links are defects.

## CRITICAL: the one-page goal

**The ideal description fits 64 rendered lines** -- reviewers reach the end without scrolling.

- **CRITICAL: Split those 64 lines across the sections** -- an overrun is recut per the cut order, never absorbed by a section still unwritten.
  - Review guide: **1** — its collapsed `<summary>`, charged before the first heading, not to any section below.
  - Jira/Linear and related-PR links: **4**.
  - Context: **17** — the heading plus at most 4 paragraphs of at most 4 lines each.
  - Changes: **9** — the heading plus 8 flat bullets, counting the two group labels.
  - Decisions: **18** — 3 headings plus 8 bullets for Functional and 7 for Technical.
  - Architecture: **5** — the heading plus at most 4 diagrams, every one left expanded.
  - Evidences: **5** — the heading, the counted-tests line, and up to 3 collapsed manual scenarios.
  - Appendix: **5** — the heading, at most 1 line of intro, and one collapsed block per subsection.
  - The eight entries sum to exactly 64.

- **Unused Functional allowance transfers to Technical decisions, and back** -- 3 functional decisions free 5 more lines for technical ones.
  - No other pair transfers -- only these two sections' split swings with the PR's product/implementation mix.

- **Only rendered text counts** -- images, diagrams, blank lines, empty anchors, and collapsed content are free.
  - A collapsed `<details>` costs only what its `<summary>` renders as — why the appendix fits in 5 lines however long it grows.
  - So the first lever is never "delete content" — it is "move content to where it costs nothing."

- **CRITICAL: A line over ~95 rendered characters costs two** -- it wraps in GitHub's description column, doubling its cost while it still reads as one bullet.
  - This is invisible to the density check (256-char cap) — nearly three rendered lines inside one compliant bullet.
  - Rendered, not source: a markdown link shows only its label, so a 200-character URL costs nothing.

- **Measure it, don't estimate it** -- `~/.claude/skills/create-pr/scripts/check-pr-page-fit.sh <file>` prints the total plus a per-section breakdown against the budgets above, on every outcome including a pass.

- **CRITICAL: Measure the ideal description, never the final body** -- a repo template's structure is arbitrary, so the script cannot attribute its lines to a budgeted section.

- **Cut in this order when a section is over** -- each step moves content down an altitude rather than destroying it.
  - Repack past wrap width first: 4×90 chars cost 4; same words as 3×120 cost 6.

  - Drop bullets diagrams already encode.
  - Cut Decisions to those changing behavior, cost, or risk.
  - Merge Changes bullets describing the same delta.
  - Move scenario methodology prose to its collapsed block.

- **Collapse what is consulted, not what is read** -- manual scenarios and appendix collapse; Context, Changes, Decisions don't.

- **Bodies over 64 lines recut through the order until they fit** -- never ship over.
  - Never raise budgets, never skip cut steps.
  - The cut order always has a move.
  - "Irreducible" means the order wasn't run to the end.
  - Splitting the PR isn't the remedy: diff is written, appendix details, code rests.
