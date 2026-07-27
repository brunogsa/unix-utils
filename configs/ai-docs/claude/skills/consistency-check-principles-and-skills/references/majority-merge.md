# 2/3 majority merge — match key and algorithm

Read this in the **orchestrator** at flow step 4, once the 3 child reports are back. Ensemble children never need it — they only emit the `[KEY]` line SKILL.md specifies.

## Match key

**Match key = `(section-group, primary-file, cited-lines)`.** Two findings match iff the first two fields are equal and their line sets overlap.

Only the key counts for voting; confidence tier, header phrasing, and diff wording all vary stochastically between children.

- `section-group` — integer 1–8 from §Heuristics, normalized to `1-2` at merge time (sections 1 & 2 conflate at the boundary).

- `primary-file` — the lowest file path in the finding *body* (never its header) that falls inside the audited scope.
  - For multi-file findings, take the first in-scope file alphabetically.
  - Fall back to the lexicographically lowest path overall only when no body path is in scope.
  - Scope-first, not lexicographic-first: a finding citing both a scope file and CLAUDE.md must key on the scope file.
    - Otherwise whichever file a child happened to quote first — not the defect — decides the key, splitting one real finding's votes across two.

- `cited-lines` — the line numbers the finding cites in `primary-file`, emitted by the children per SKILL.md's `[KEY]` spec.
  - Two line sets match iff any line in one falls within ±3 of any line in the other; the tolerance absorbs a child citing a `[Why]` instead of its `[Instruction]`.

  - Match on overlap, never on set equality — children cite different subsets of the same conflict, so an exact-set key silently loses those votes.

  - This field replaced an enclosing-`##`-heading `anchor`, which failed in both directions and needed spelling normalization to half-work.
    - Split votes: one defect keyed `subagent-flow-opt-in` by one child and `Subagent flow (opt-in)` by another (observed 2026-07-25).

    - Fabricated votes: a broad heading hosts unrelated defects, so `### TaskList discipline` merged a `:184`/`:301` finding with a `:316`/`:372` one into a bogus 3-vote consensus, emitting the wrong body (observed 2026-07-25).

  - Lines identify the defect itself, so both failures dissolve — a heading only ever identified the neighborhood the defect sat in.
  - Line numbers are safe to key on because all 3 children read the same static tree; never re-run a merge against an edited file.

## Algorithm

1. `grep '^\[KEY\]'` over each child report → list of keys per child.

2. Normalize each key: sections 1 and 2 become group `1-2`; strip any stray `:<line>` suffix a child left on the file path; parse `lines=` into a set of integers.

3. Bucket the normalized keys by `(section-group, primary-file)`, then cluster the line sets inside each bucket by the ±3-overlap rule above, merging transitively. Each cluster is one key.
   - Clustering inside the bucket is what keeps the overlap rule safe — two line sets can only merge when they already share both a section group and a file.

4. Count each clustered key once per child report — duplicates within one report still count as one vote.
5. Keep findings whose key appears in ≥2 reports. Drop the rest silently.
6. For each kept key, emit the finding body from whichever child reported it with HIGHEST confidence; tie → lexicographically first child's wording.
7. Re-number kept findings as `<section>.<index>` per §Lifecycle step 6. Numbering restarts at `.1` within each section, and a `1-2`-group finding renders under the winning body's own section.

8. Strip every `[KEY]` line before emitting the merged report — they exist for the vote, not the human reader.

## Ensemble voting vs. correlated false positives

2/3 voting filters stochastic noise (samples disagree), NOT correlated false positives (every sample flags the same wrong thing).

Surface that distinction in the handback. If a finding persists across rerun-and-fix cycles:

> "Finding survived 3/3 — likely correlated false positive. Tighten the heuristic wording or raise the confidence threshold, not just re-run."
