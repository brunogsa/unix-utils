# 2/3 majority merge — match key and algorithm

Read this in the **orchestrator** at flow step 4, once the 3 child reports are back. Ensemble children never need it — they only emit the `[KEY]` line SKILL.md specifies.

## Match key

**Match key = `(section-group, primary-file, anchor)`.** Two findings match iff all three fields match exactly.

Only the key counts for voting; confidence tier, line numbers, and diff wording all vary stochastically between children.

- `section-group` — integer 1–7 from §Heuristics, normalized to `1-2` at merge time (sections 1 & 2 conflate at the boundary).

- `primary-file` — the lowest file path in the finding *body* (never its header) that falls inside the audited scope.
  - For multi-file findings, take the first in-scope file alphabetically.
  - Fall back to the lexicographically lowest path overall only when no body path is in scope.
  - No line number in the key — children anchor the same defect differently, so line-exact keys silently lose votes.
  - Scope-first, not lexicographic-first: a finding citing both a scope file and CLAUDE.md must key on the scope file.
    - Otherwise whichever file a child happened to quote first — not the defect — decides the key, splitting one real finding's votes across two.

- `anchor` — the heading in `primary-file` enclosing the cited defect, derived by the children per SKILL.md's `[KEY]` spec.
  - That spec: the nearest `##`/`###` heading above the defect, verbatim — or the number alone (`9.5`, `2.1`) where the file numbers its headings.
  - Never compare anchors as emitted — children spell the same heading differently, so an exact-string key silently loses those votes.
    - Observed 2026-07-25: `subagent-flow-opt-in` vs `Subagent flow (opt-in)`; `repo-wide-static-checks` vs `repo-wide-static-checks-tests-coverage-local-mode`.
  - Normalize before comparing: lowercase, then delete every character outside `a-z0-9` (`tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9'`).
  - Two normalized anchors match iff they are equal, or one is a prefix of the other and that prefix is at least 12 characters long.
    - The 12-char floor stops a stub anchor like `run` swallowing `running-the-pipeline` and fabricating a consensus no child actually reached.
  - Without the anchor, a hub file cited by several unrelated defects collapses into one `(section-group, file)` key.
    - Example: `implement/SKILL.md` separately defective under anchors `2.1`, `9.1`, and `9.5` — the first-reported wording wins the vote and the other two defects silently vanish.

## Algorithm

1. `grep '^\[KEY\]'` over each child report → list of keys per child.
2. Normalize each key: sections 1 and 2 become group `1-2`; strip any stray `:<line>` suffix a child left on the file path; lowercase the anchor and delete every character outside `a-z0-9`.
3. Bucket the normalized keys by `(section-group, primary-file)`, then cluster the anchors inside each bucket by the equal-or-≥12-char-prefix rule above. Each cluster is one key.
   - Clustering inside the bucket is what keeps the prefix rule safe — two anchors can only merge when they already share both a section group and a file.
4. Count each clustered key once per child report — duplicates within one report still count as one vote.
5. Keep findings whose key appears in ≥2 reports. Drop the rest silently.
6. For each kept key, emit the finding body from whichever child reported it with HIGHEST confidence; tie → lexicographically first child's wording.
7. Re-number kept findings as `<section>.<index>` per §Lifecycle step 6. Numbering restarts at `.1` within each section, and a `1-2`-group finding renders under the winning body's own section.
8. Strip every `[KEY]` line before emitting the merged report — they exist for the vote, not the human reader.

## Ensemble voting vs. correlated false positives

2/3 voting filters stochastic noise (samples disagree), NOT correlated false positives (every sample flags the same wrong thing).

Surface that distinction in the handback. If a finding persists across rerun-and-fix cycles:

> "Finding survived 3/3 — likely correlated false positive. Tighten the heuristic wording or raise the confidence threshold, not just re-run."
