# Merge Review Verdicts

Rules for the `code-reviewer` agent that `/quality-gate` §4.1 dispatches to fold the `refactor` and `auto-review` verdict files into one. Main hands over both source paths (or the one that exists) and the merged path to write.

## Scope

- You merge reports only - never re-review the diff, and never add a finding of your own.
  - Reason: the legs already did the review, so a finding that appears only here has no evidence behind it.

- Read both source files in full, never a leg's return summary.

## Layout

Write the merged file in the layout of [`local-review-template.md`](../../code-review-pipeline/references/local-review-template.md): same header shape, same four-part body, same budget.

- One numbered list, `### 1.`, `### 2.`, ... ordered by severity as that template orders it.

- Every finding heading carries exactly one lens tag right after the severity ordinal:
  - `### N. [HIGH][auto-review] <title>`
  - `### N. [MEDIUM][refactor] <title>`
  - Reason: `/address-verdicts` routes on this tag - `auto-review` to `tdd-coder`, `refactor` to the `refactor` agent - so a heading with no tag, or two, is a defect.

- Under the header, write one line of counts: findings taken from each lens, duplicates collapsed, findings written.

## Duplicates

A duplicate is the same defect at overlapping lines of the same file, across the two lenses or within one. Collapse each into one finding:

- Keep the higher severity.

- Keep one body in the four-part layout - pick the clearer one, never concatenate two.

- Tag it `auto-review` when the fix changes behavior, meaning some input behaves differently before and after, so it needs a RED test from `tdd-coder`.

- Tag it `refactor` when the fix is structure-only.

Everything that is not a duplicate is copied verbatim, with its source lens as its tag.

## Check and return

After writing, run:

```bash
python3 ~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py <merged path>
```

- On exit 1, rewrite only the flagged findings, at most twice, then report any leftovers.

Return exactly this:

- The merged path.
- Per-lens input counts.
- Duplicates collapsed, each as `refactor#A + auto-review#B → #N`.
- Output finding count.
- The checker's exit code.
