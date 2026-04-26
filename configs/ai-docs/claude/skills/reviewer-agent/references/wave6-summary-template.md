# Wave 6 — Summary template

Print a terminal summary reporting the review-level counts. Both modes share
the structure below; only the output path / review URL differ.

## github mode

```
PR #<n>: <title>
<pr-url>

PENDING review created: <review_url>
Review ID: <review_id>

Findings posted: <N>
  MANDATORY: <m>
  RECOMMENDED: <p>
  NITPICK: <q>
  OPTIONAL: <o>
  COMPLIMENT: <r>
  QUESTION: <s>

Dropped findings (one line each, for validation):
  [Wave 3 FP ]  path:line — <first 80 chars of body> — dropped because <reason>
  [Wave 4 off]  path:line — <first 80 chars of body>

Totals: <y> false positives, <z> off-diff dropped.

Skipped files (not reviewed):
  binary: <list from work_dir/skipped-binary.txt>
  deleted: <list from work_dir/skipped-deleted.txt>

Open <pr-url>/files to filter and submit.
```

The per-finding drop list exists so you can sanity-check the filter while the
threshold is tuned LOW. If real findings are disappearing, tighten Wave 3. If
noise is surviving, loosen.

## local mode

Same structure as github mode, but with `${out_file}` (the timestamped path)
as the output path and no review URL or review ID line.
