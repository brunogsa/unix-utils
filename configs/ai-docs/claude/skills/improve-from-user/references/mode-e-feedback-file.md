# Mode E - feedback file

Load this only when Step 1 detected Mode E: the arg is `feedback in <path>`.

The file is written by a caller skill (`to-spec`, `to-plan`) per [`lateral-learn.md`](lateral-learn.md), from the human's corrections to a spec or plan.

Its items are already in the unified item format, so no extraction runs: read the file and hand its items to step 2.

This mode is read-only on the feedback file and on the document it names.

- Why: the caller owns both, and may still be editing the document in parallel.

## Reading the file

- The file opens with `Document:`, `Repo:` and `References:` lines, then the items.
- Open a `References:` path only when an item's Context is too thin to generalize from.
  - Why: the caller kept those paths out of its own context to stay small, so reading them is this session's job, but never a requirement.

- An absent file, an empty file, or one with zero items hits the zero-items stop in SKILL.md.

## Per-item field hints

- **Source** - `<feedback file>:<item heading line>`.
- **Verbatim** - the human's exact words, as the caller recorded them; never reword.
- **Context** - what the item says about the document, from the item itself.
- **Outcome** - as the caller recorded it.
- **Lesson drawn** - the caller's first draft; step 2 challenges it, since the caller wrote it with the document in mind and not the rule files.

## Where a lesson lands

The run happens from `~/unix-utils`, so every target below is in the global set.

- **How a spec or plan is authored** (acceptance-criterion shape, a required spec section, a required plan task kind) → the `spec-writer` / `plan-writer` agent, or `skills/spec-driven-development/references/`.
  - Those files are `spec-writing.md`, `spec-acceptance-criteria.md`, `plan-writing.md`, `plan-tasks-and-appendix.md`, `self-review-checks.md`.

- **What a reviewer should have caught** → the `spec-reviewer` / `plan-reviewer` agent or `self-review-checks.md`.
  - Use `code-review-pipeline/references/review-principles.md` when a code reviewer would also miss it.

- **A design principle about the system being specified** → `code-standards`, or `test-standards` for test strategy.
  - Examples: a closed enum over an open string, a missing identity field is an error, a data format detected at the boundary.

  - Use the global `CLAUDE.md` when the principle is cross-cutting.

- **A fact true only of the work repo** → list it with that repo's name and do not write it, per SKILL.md step 4.
