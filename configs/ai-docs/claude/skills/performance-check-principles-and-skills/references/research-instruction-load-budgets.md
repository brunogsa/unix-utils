# Research — instruction-count and CRITICAL-emphasis budgets

Citations behind the adherence numbers: CLAUDE.md at most 100 `[Instruction]` markers, the `*-standards` total at most 200, and at most a 16% CRITICAL ratio per file.

These govern how many rules a file may carry. The CLAUDE.md line and word caps are separate — see [`research-claudemd-budgets.md`](research-claudemd-budgets.md).

[`research.md`](research.md) indexes all three files and carries the summary table.

## Instruction-count budgets

**Budgets: CLAUDE.md ≤ 100 [Instruction], `*-standards` total ≤ 200 [Instruction]**

The two numbers sit deliberately well under the published 500-instruction adherence ceiling, splitting capacity by where each surface lives in the assembled prompt.

The combined 300 leaves ~200 instructions of slack against the 500 cliff — buffer for repo-level CLAUDE.md, ad-hoc rules, and inevitable drift.

### Jaroslawicz et al. 2026 — 500-instruction ceiling

*How Many Instructions Can LLMs Follow at Once?* — arXiv:2507.11538 — https://arxiv.org/abs/2507.11538

IFScale benchmark, 500 keyword-inclusion instructions across 20 frontier models. Headline results:
- Best frontier models drop to **68% accuracy at 500 instructions**.
- Claude-Sonnet-class models follow a **linear-decay** pattern starting around 150–200 instructions.
- Earlier instructions retain stronger adherence than later ones (recency bias on the tail).

The 500 ceiling is the absolute upper bound; beyond it, adherence collapses for every model in the benchmark. Our split keeps the cross-file load at or below that line.

### Why the 100 / 200 split (and not the full 500)

- **CLAUDE.md ≤ 100** — always-loaded principles compete with every system-prompt token.
  - Tightening to 100 (half the 200 line ceiling) forces the cross-cutting set to stay genuinely cross-cutting; domain-specific goes to a skill.

- ***-standards ≤ 200** — covers lazy-loaded skills (`code-`, `test-`, `doc-`, `debug-`, `commit-standards`).
  - These enter context only when triggered, so per-load bandwidth is larger than CLAUDE.md's — but the cross-skill sum still must leave attention room.

- **Why not budget the full 500?** — the IFScale 500 ceiling is where adherence has already started decaying.
  - Leaving ~200 of slack gives room for repo-level CLAUDE.md, ad-hoc rules, and marker drift. Burning to 500 puts you at the cliff with no headroom.

The split is enforced as **two independent per-bucket budgets** rather than one summed check. Rationale:
- Failure mode is specific — the report tells you exactly which bucket overflowed.
- No derived total to maintain.
- The split is intentional capacity allocation, not arithmetic — borrowing slack between buckets would defeat the purpose.

### Why deterministic markers, not LLM judgment

Counting [Instruction] markers with `grep`/`awk` runs in milliseconds and never drifts. LLM-driven counting is slow, non-deterministic, and would itself consume part of the instruction budget it's trying to measure.

---

## CRITICAL emphasis ratio

**Budget: ≤ 16% of [Instruction] count per file**

This is a **reasoned** budget, not a measured one.

No published study directly fits a ratio of emphasis tokens to instruction count against adherence. The number rests on three converging anchors plus a power-of-2 rounding for cleanliness.

### Anchor 1 — Pareto 80–20

Long-established management heuristic: ~20% of items drive ~80% of value.

Applied to elevated rules, this argues that the genuinely-trump-others subset sits around 20% of the total. We trim slightly below (16%) to leave headroom and discourage emphasis creep.

### Anchor 2 — Miller's 7 ± 2

Miller, *The Magical Number Seven, Plus or Minus Two: Some Limits on Our Capacity for Processing Information* (Psychological Review, 1956) — https://psychclassics.yorku.ca/Miller/

Human working memory caps near 7 ± 2 items. LLMs have wider attention but the same shape applies to *priority* items in conflict.

Too many CRITICAL constraints competing at decision time degrades arbitration. At 16% of ~200 CLAUDE.md instructions ≈ 32 critical items, or ~48 across CLAUDE.md + *-standards.

Still above the cognitive cap, but the cap argues for the *direction* of constraint, not the exact number.

### Anchor 3 — ConInstruct (2026) on conflict degradation

*ConInstruct: Evaluating LLMs on Conflict Detection and Resolution in Instructions* — arXiv:2511.14342 — https://arxiv.org/abs/2511.14342

When many instructions claim priority simultaneously, frontier LLMs cannot reliably detect or resolve the conflicts.

They default to whichever rule has higher salience (recency, position, emphasis). A small priority subset preserves the tiebreaker function; a large one defeats it.

### Why 16% and not 20%

- **Power-of-2** rounding (16 = 2⁴) — keeps the budget cleanly memorable and signals it's a chosen line, not a measured one.
- Sits just below the **20% emphasis cliff** suggested by Pareto and general signal-processing principles.
- Leaves a margin against gradual creep — when the budget is tight, demoting a "soft critical" stays easy.

### Caveat — flagged for re-derivation when data lands

If a published ablation on emphasis-to-instruction ratios appears (specifically for instruction-following prompts), re-derive this budget from that data instead of from anchors.

Until then: 16% with citations to the three anchors above.
