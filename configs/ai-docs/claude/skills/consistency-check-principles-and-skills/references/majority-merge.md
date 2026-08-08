# 2/3 majority merge — two-tier match and algorithm

Read this in the **orchestrator** at flow step 4, once the 3 child reports are back. Ensemble children never need it — they only emit the `[KEY]` line SKILL.md specifies.

## Two tiers, one vote

The `[KEY]` line is a canonical anchor and tier 1's deterministic fast path — not the whole merge mechanism.

Tier 1 clusters findings by the key alone, no judgment. Tier 2 is orchestrator judgment over the bodies of whatever tier 1 leaves unmatched.

Both feed the same ≥2/3 vote from §Lifecycle.

## Tier 1: match key

**Match key = `(section-group, primary-file, cited-lines)`.** Two findings match iff the first two fields are equal and their line sets overlap.

Only the key counts here; confidence tier, header phrasing, and diff wording all vary stochastically between children.

- `section-group` — integer 1–8 from §Heuristics, normalized to `1-2` at merge time (sections 1 & 2 conflate at the boundary).

- `primary-file` — the lowest file path in the finding *body* (never its header) that falls inside the audited scope.
  - For multi-file findings, take the first in-scope file alphabetically.
  - Fall back to the lexicographically lowest path overall only when no body path is in scope.
  - Scope-first, not lexicographic-first: a finding citing both a scope file and CLAUDE.md must key on the scope file.
    - Otherwise whichever file a child happened to quote first — not the defect — decides the key, splitting one real finding's votes across two.

- `cited-lines` — the line numbers the finding cites in `primary-file`, emitted by the children per SKILL.md's `[KEY]` spec.
  - Two line sets match iff any line in one falls within ±3 of any line in the other; the tolerance absorbs a child citing a `[Why]` instead of its `[Instruction]`.

  - Match on overlap, never on set equality — children cite different subsets of the same conflict, so an exact-set key silently loses those votes.

  - This field replaced an enclosing-`##`-heading `anchor`, which failed to hold even within one section.
    - One defect keyed `subagent-flow-opt-in` by one child and `Subagent flow (opt-in)` by another (observed 2026-07-25) — spelling drift alone split its votes.

  - Lines identify the defect itself, so that failure dissolves — a heading only ever identified the neighborhood the defect sat in.
  - Line numbers are safe to key on because all 3 children read the same static tree; never re-run a merge against an edited file.

## Tier 1: algorithm

1. `grep '^\[KEY\]'` over each child report → list of keys per child.

2. Normalize each key: sections 1 and 2 become group `1-2`; strip any stray `:<line>` suffix a child left on the file path; parse `lines=` into a set of integers.

3. Bucket the normalized keys by `(section-group, primary-file)`, then cluster the line sets inside each bucket by the ±3-overlap rule above, merging transitively. Each cluster is one key.
   - Clustering inside the bucket is what keeps the overlap rule safe — two line sets can only merge when they already share both a section group and a file.

4. Count each clustered key once per child report — duplicates within one report still count as one vote.

## Tier 2: orchestrator judgment on bodies (NEW)

Tier 1 under-merges by design: bucketing by `(section-group, primary-file)` happens BEFORE the line test, so two children filing the same defect under different heuristics, or differently-cited files, never reach the overlap check.

For every finding still a singleton after tier 1 (1 vote, not yet ≥2), read its body against every other singleton from the other two reports.

Merge two singletons only if they describe the same defect: same rule(s), same file(s), same behavior. A merged pair counts as 2 votes; a merged trio counts as 3.

**Worked example (2026-08-08 run).** Children 1 and 3 flagged `skills/refactor/SKILL.md:11,136,140`: the skill claims it "never edits code," while `agents/refactor.md` makes "Load the refactor skill" step 1 and applies edits at step 3.

Child 1 filed it under §1 Contradictions; child 3 filed it under §7 Term consistency — tier 1's bucketing means groups `1-2` and `7` never meet.

The finding scored 1 vote per key and dropped, though 2 of 3 samples located the identical defect.

Reading both bodies, the orchestrator sees the same rule, file, and behavior, and merges them into one 2-vote finding.

## GUARD: same defect only, never proximity

**CRITICAL:** tier 2 merges on the SAME DEFECT, never on mere proximity. Two findings about different rules in the same file, or under the same heading, are NOT a match.

This exact failure happened here: a broad `### TaskList discipline` heading once fused a `:184`/`:301` finding with a `:316`/`:372` one into a bogus 3-vote consensus, emitting the wrong body (observed 2026-07-25).

Line-based tier 1 closed that hole for identical-key findings, but tier 2's free-text reading reopens it — nothing stops merging on "same file" or "same heading" instead of "same defect."

Treat the refactor example above as the positive case, and this one as the negative, before merging any tier-2 pair.

## Cross-section rendering

For each kept key — tier 1 or tier 2 — emit the finding body from whichever child reported it with HIGHEST confidence; tie → lexicographically first child's wording.

Re-number kept findings as `<section>.<index>` per §Lifecycle step 6, restarting at `.1` within each section.

When a merge spans sections — a `1-2`-group key, or any tier-2 cross-section merge — the finding renders under the winning body's own section, never a hybrid.

Strip every `[KEY]` line before emitting the merged report — they exist for the vote, not the human reader.

## Ensemble voting vs. correlated false positives

2/3 voting filters stochastic noise (samples disagree), NOT correlated false positives (every sample flags the same wrong thing).

Surface that distinction in the handback. If a finding persists across rerun-and-fix cycles:

> "Finding survived 3/3 — likely correlated false positive. Tighten the heuristic wording or raise the confidence threshold, not just re-run."
