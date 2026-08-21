# Validator Rubric (Wave 3, inline self-check)

You run this rubric inline in the code-review-pipeline session — there is no separate
agent call. For each finding in the flat list, work through the two checks
below in order. This combines the old "false-positive filter" and
"line-range validator" into one pass so each file is loaded at most once per
finding, not twice.

---

## Pre-pass — dedup across lenses

Run this once over the whole list, before any per-finding check. It reads no files, so doing it first spares you from validating a finding you are about to drop.

Wave 2 walks the diff once per lens, eight lenses in one pass. Two lenses landing on the same defect from different angles is expected, not a bug
— you are the first step that holds the full merged list and can tell.

Two findings are duplicates when **all three** hold:

- Same `path`.
- `start_line..line` ranges overlap by at least one line.
- The summary line (the second line of `body`) describes the same underlying defect — not merely the same symptom or the same function.

Different `scope_tag` values do **not** make them distinct. Two lenses reaching one defect from different rubrics is the exact case this pre-pass exists for.

Distinct defects that happen to share a line both stay. A null check and a unit-conversion bug on the same line are two findings, not one.

Keep exactly one of each duplicate set, by this order:

1. Highest severity — `MANDATORY` > `RECOMMENDED` > `NITPICK` > `OPTIONAL` > `QUESTION`.
2. Still tied → highest `confidence`.
3. Still tied → the one appearing first in the merged array.

Record each dropped duplicate: `path:line — <first 80 chars of body> — duplicate of <kept scope_tag>`.

Log them even though they are routine. The drop log is where a rubric-boundary problem in Wave 2's rubric files becomes visible.

Wave 6 surfaces that log, so a rising duplicate count is where you would notice two rubrics' scopes overlapping more than they should.

---

## Per-finding checks

### Check 1 — False positive?

Read the file at `{finding.path}` under `{repo_root}` (reuse an open Read if
the prior finding was in the same file). Focus on `start_line..line ± 10`.

Ask yourself: **is the claim visibly present in the code?**

**Drop** ONLY when you have clear, specific evidence the claim doesn't hold:

- The cited code literally doesn't exist at any nearby line.
- The code already does what the finding asked for (the suggestion is a no-op).
- The issue depends on a behavior the file explicitly prevents (e.g., a guard
  clause immediately above the flagged block).

**Keep** in every other case — including when uncertain. Wave 2's lens had
the same context you have. Dropping a real finding is worse than keeping noise.

When you drop, record one sentence: `path:line — <first 80 chars of body> — dropped because <reason>`.

### Check 2 — Line range (kept findings only)

Is `start_line..line` the tightest range that captures the problem?

- Off by a few lines, but the issue is clearly in the same hunk → **update**
  `start_line` and `line` to the correct anchor.
- The range spans 5 lines but the issue is on 1 → **shrink**.
- The range is 1 line but the suggestion block replaces 3 → **widen**.
- Range is fine as-is → **leave alone**.

Constraint: the final range must be contained in `commentable-lines.txt`.
Wave 4 drops any finding whose range falls outside it, at every severity —
the filter reads no `severity` field, so OPTIONAL buys no exemption.

So an OPTIONAL finding about pre-existing code must be snapped to the closest
commentable line in the same hunk. Left off-diff, it never reaches Wave 5.

Do **not** adjust just for style — only when the current anchor actually
misleads the reader about where the issue is.

---

## Hard rules

- Don't touch severity, body, or scope_tag. Wave 2's lens owns those.
- Don't invent new findings; validate the ones you have.
- Don't widen/tighten findings that are already anchored correctly.
- Err toward KEPT throughout. Calibration happens by reading the drop log in
  the Wave 6 summary, not by being aggressive here.
