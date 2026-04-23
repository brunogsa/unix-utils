# Validator Rubric (Wave 3, inline self-check)

You run this rubric inline in the reviewer-agent session — there is no separate
agent call. For each finding in the flat list, work through the two checks
below in order. This combines the old "false-positive filter" and
"line-range validator" into one pass so each file is loaded at most once per
finding, not twice.

---

## Per-finding checks

### Check 1 — False positive?

Read the file at `{finding.path}` under `{repo_root}` (reuse an open Read if
the prior finding was in the same file). Focus on `start_line..line ± 10`.

Ask yourself: **is the claim visibly present in the code?**

**Drop** ONLY when you have clear, specific evidence the claim doesn't hold:

- The cited code literally doesn't exist at any nearby line.
- The code already does what the specialist asked for (the suggestion is a no-op).
- The issue depends on a behavior the file explicitly prevents (e.g., a guard
  clause immediately above the flagged block).

**Keep** in every other case — including when uncertain. The specialist had
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
EXCEPTION: if severity is OPTIONAL, the range may fall outside — snap it to
the closest commentable line in the same hunk.

Do **not** adjust just for style — only when the current anchor actually
misleads the reader about where the issue is.

---

## Hard rules

- Don't touch severity, body, or scope_tag. The specialist owns those.
- Don't invent new findings; validate the ones you have.
- Don't widen/tighten findings that are already anchored correctly.
- Err toward KEPT throughout. Calibration happens by reading the drop log in
  the Wave 6 summary, not by being aggressive here.
