# Merge Review Verdicts

Rules for the `code-reviewer` agent that `/quality-gate` §4.1 dispatches to fold the legs' findings into one file. Main hands over the source paths that exist, the number `k`, and the one path to write, `<RUN_DIR>/merged-findings.md`.

The sources are up to five files: the `refactor` verdict, the `auto-review` verdict, the `test-sdd` verdict, the metrics judge file (`metrics-judge_<ts>.md`), and a `detector-edits.md` main wrote. The rendered metrics verdict is not a source: main puts it ahead of your file, holding entries `1` to `k`.

## Scope

- You merge reports only - never re-review the diff, and never add a finding of your own.
  - Reason: the legs already did the review, so a finding that appears only here has no evidence behind it.

- Read every source file in full, never a leg's return summary.

- Write only `<RUN_DIR>/merged-findings.md`. Main assembles the final verdict from it, so never write the merged path in CWD.

## Layout

Write the file in the layout of [`local-review-template.md`](../../code-review-pipeline/references/local-review-template.md): same four-part body, same budget. Skip the template's header: main puts the rendered metrics verdict first.

- One numbered list, `### k+1.`, `### k+2.`, ... in that order, ordered by severity as that template orders it. With `k` = 0 it starts at `### 1.`.

- Every finding heading carries exactly one lens tag right after the severity ordinal:
  - `### N. [HIGH][auto-review] <title>`
  - `### N. [MEDIUM][refactor] <title>`
  - `### N. [MEDIUM][test-sdd] <title>`
  - `### N. [MEDIUM][metrics] <title>`
  - Reason: `/address-verdicts` routes on this tag, so a heading with no tag, or two, is a defect.

- A `test-sdd` finding is copied verbatim with `[test-sdd]` inserted right after its severity tag. Keep its title word for word: `get-test-sdd-dispatch-list.py` keys on it.

- A metrics judge finding is copied verbatim; its heading already reads `[SEV][metrics]`.

- A `detector-edits.md` finding is copied verbatim, `### N. [Done][SEV][metrics] <title>`, keeping its `[Done]` mark ahead of the severity and its commit SHA.

- Keep every other tag the source heading had, with the lens tag right after the severity and before any of them: `### N. [MEDIUM][refactor][LINTER GAP] <title>`.

- Start the file with one line of counts under a `## Findings` heading: findings taken from each source, findings absorbed by duplicate groups, findings written.

## Duplicates

A duplicate is the same defect at overlapping lines of the same file, across the `refactor` and `auto-review` lenses or within one. Collapse each into one finding:

- Keep the higher severity.

- Keep one body in the four-part layout - pick the clearer one, never concatenate two.

- Tag it `auto-review` when the fix changes behavior, meaning some input behaves differently before and after, so it needs a RED test from `tdd-coder`.

- Tag it `refactor` when the fix is structure-only.

A `test-sdd`, metrics judge or detector-edit finding never collapses into another, even at the same lines. Everything that is not a duplicate is copied verbatim, with its source lens as its tag.

## Check and return

After writing, run:

```bash
python3 ~/.claude/skills/code-review-pipeline/scripts/check-finding-bodies.py <RUN_DIR>/merged-findings.md
```

- On exit 1, rewrite only the flagged findings, at most twice, then report any leftovers.

Return exactly this:

- The path written.
- Per-source input counts.
- Duplicate groups collapsed, each listing every member: `refactor#A + auto-review#B + refactor#C → #N`.
- Total findings absorbed: a group of k findings collapsed into one absorbs k-1, so sum k-1 over all groups.
- Output finding count.
- The checker's exit code.
