# Research References — Performance-Check Budgets

Citations backing every number in `SKILL.md`'s budget table. Read this when you need to defend a cut, or when proposing to dial a budget up or down.

## Table of contents

- [CLAUDE.md length](#claudemd-length)
- [CLAUDE.md words per line](#claudemd-words-per-line)
- [Skill size](#skill-size)
- [Skill count](#skill-count)
- [Skill words per SKILL.md](#skill-words-per-skillmd)
- [Skill description length](#skill-description-length)
- [Skill name length](#skill-name-length)
- [Instruction-count budgets](#instruction-count-budgets)
- [CRITICAL emphasis ratio](#critical-emphasis-ratio)
- [Summary](#summary)

---

## CLAUDE.md length

**Budget: 260 non-blank lines**

### Marker-convention re-derivation (200 → 260)

The 200 below was anchored on "a line roughly equals an instruction" — true for the pre-marker imperative style.

The marker convention broke that 1:1 mapping: every `[Instruction]` now carries a `[Why]` line beneath it, plus optional `[Example]` lines.

So ~100 instructions cost ~200 non-blank lines as instruction+why pairs alone, before any header or the Counting-conventions meta section.

That makes the 100-instruction budget and a 200-line budget mathematically incompatible — you cannot use the full instruction budget without breaching 200 lines.

The fix keeps instruction *count* (≤100) as the real adherence gate and re-derives the line cap to **260** = ~200 (pairs at full instruction budget) + ~60 (current header/meta/example overhead).

The line budget now guards only marker-overhead bloat, not instruction load — the count budget already does the latter.

### Jaroslawicz et al. 2025 — instruction adherence peaks at 150–200

*How Many Instructions Can LLMs Follow at Once?* arXiv:2507.11538
https://arxiv.org/abs/2507.11538

IFScale benchmark across 20 frontier models. Key findings:

- "Mid-range peaks around 150–200 instructions" before selective attention degrades.
- Best models drop to 68% accuracy at 500 instructions.
- Reasoning models hold up better through 100–250.

**Implication:** the 150–200 peak applies to *instruction count*, which the marker convention now measures directly (≤100 budget). The line cap (260) is a separate marker-overhead guard — see the re-derivation above.

### Community consensus — 200 ideal, 300 ceiling

- HumanLayer, *Writing a good CLAUDE.md* — https://www.humanlayer.dev/blog/writing-a-good-claude-md
- anthropics/claude-code#5502 — community report of CLAUDE.md adherence decay — https://github.com/anthropics/claude-code/issues/5502

### arXiv 2603.13351 — context interference

*Prompt Complexity Dilutes Structured Reasoning* — https://arxiv.org/html/2603.13351v1

A STAR task scored 100% on an isolated prompt, but 0–30% when surrounded by competing instructions. Supports trimming CLAUDE.md aggressively even when under the line budget.

### Anthropic — Claude Code best practices

https://code.claude.com/docs/en/best-practices — "Keep CLAUDE.md short and human-readable." No numeric cap; informs the "keep lean" stance rather than a specific number.

---

## CLAUDE.md words per line

**Budget: 32 words per line**

No external source. User preference backing the "Prefer scannable shape" principle in CLAUDE.md.

Acts as a prose-bloat guard:

- 32 words is ~2 full sentences or ~200 characters — the upper edge of comfortable scanning.
- Most principles should come in well under.
- The budget is a ceiling, not a target.

---

## Skill size

**Budget: 500 non-blank lines per SKILL.md**

### Anthropic official — skill authoring best practices

*Skill authoring best practices* — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

Explicit mandates:
- SKILL.md body **under 500 lines** for optimal performance
- `description` max 1024 chars
- `name` max 64 chars
- Reference files >100 lines should include a table of contents
- Reference links one level deep

### Anthropic — skill-creator reference

https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md — progressive-disclosure folder layout (SKILL.md + scripts/ + references/) and writing patterns.

---

## Skill count

**Budget: 50 skills**

*Skill authoring best practices* — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

Anthropic's official docs design description-based routing for scale.

They state twice that Claude "choose[s] the right Skill from potentially 100+ available Skills."

So the platform is built to route across 100+; raw count is not the constraint Anthropic warns about.

Metadata preload cost is also negligible: ~30–50 tokens per skill (name + ≤250-char description).

So 50 skills ≈ 1.5–2.5k tokens, ~1% of a 200k window — the old "keep preload small" rationale does not bind at this scale.

The real (soft) guardrail is routing sharpness: more near-overlapping descriptions make the router's pick harder.

50 sits at half of Anthropic's documented 100+ scale — a 2× safety margin — while giving headroom so the cap forces consolidation only when skills genuinely proliferate.

---

## Skill words per SKILL.md

**Budget: 2048 words per SKILL.md**

No external source. User preference. Co-binds with the 500-line cap:

- At ~4 words per line (typical for imperative instructions with bullets), 500 lines ≈ 2000 words.
- The 2048 value gives a small cushion above the line co-bind.
- Keeps skill bodies readable in one sitting (~8–10 minutes).

---

## Skill description length

**Budget: 250 characters per `description` frontmatter field**

### Claude Code — `/skills` display cap (the routing-effective limit)

*Claude Code changelog v2.1.86* — https://github.com/anthropics/claude-code/issues/40121

Verbatim from the changelog:

> "Skill descriptions in the `/skills` listing are now capped at 250 characters to reduce context usage."

The `/skills` listing is what Claude consults when deciding whether to invoke a skill.

- Anything past character 250 in your description **does not participate in routing**.
- Front-load triggers and core context within those 250.

The same issue clarifies that `SLASH_COMMAND_TOOL_CHAR_BUDGET` increases the overall metadata budget across skills but does not remove the per-description 250-char cap.

### Anthropic — frontmatter validation hard cap (failure threshold)

*Skill authoring best practices* — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

> "`description`: Must be non-empty. Maximum 1024 characters. Cannot contain XML tags."

This is the validation cap; descriptions longer than 1024 chars fail at load time.

We don't budget against 1024 because the routing cap (250) is a much stricter effective limit, but it remains the absolute ceiling.

### Anthropic — skill-creator authoring guidance

*skill-creator SKILL.md* — https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md

Two concrete patterns for the description:
- "Include both what the skill does AND specific contexts for when to use it. All 'when to use' info goes here, not in the body."
- "Make the skill descriptions a little bit 'pushy'." Skills tend to **under-trigger**; explicit trigger contexts help.

Per Anthropic's API docs the metadata layer (name + description) is "always in context":

- Approximately 100 tokens / ~100 words per skill at session start.
- With 50 skills loaded, that's ~5,000 tokens before any conversation begins.

### Why 250, not 1024

- The 1024 cap is the *failure* threshold; the 250 cap is the *effective* trigger budget — only the first 250 chars are read by the router.
- A description longer than 250 isn't broken, but the tail is wasted from a discovery standpoint and bloats the always-loaded metadata layer.
- Aligning the budget with the routing-effective length keeps every char working.

### No published empirical ablation

*Berkeley Function Calling Leaderboard (BFCL) v4* — https://gorilla.cs.berkeley.edu/leaderboard.html

BFCL v4 measures function-calling accuracy broadly, but no public study isolates *description length* as an independent variable affecting routing.

- Search results across BFCL, ToolBench, and academic repositories surfaced no description-length ablation.
- The 250 budget therefore anchors on Anthropic's product cap, not an evaluation result.

---

## Skill name length

**Budget: 64 characters per skill name**

### Anthropic — frontmatter validation hard cap

*Skill authoring best practices* — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

> "`name`: Maximum 64 characters. Must contain only lowercase letters, numbers, and hyphens. Cannot contain XML tags. Cannot contain reserved words: 'anthropic', 'claude'."

This budget enforces only the length cap. The other rules (charset, reserved words, XML) belong in a stricter frontmatter-validation skill if needed; performance-check stays focused on size budgets.

### Skill name resolution

For Claude Code skills, the `name` field is optional in the frontmatter — when absent, the directory name is used.

- The 64-char cap applies to whichever resolves: explicit field if present, else `basename` of the skill directory.
- The audit script measures the directory name because that's what Claude Code displays in `/skills` and what users invoke via `/<skill-name>`.

---

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

---

## Summary

| Budget | Value | Anchor |
|---|---|---|
| CLAUDE.md non-blank lines | 260 | Marker-convention re-derivation ([Why] pairs ~2× lines/instruction); count is the real gate |
| CLAUDE.md words per line | 32 | User preference; prose-bloat guard |
| Skill total count | 50 | Half of Anthropic's documented 100+ routing scale; preload cost negligible (~1% of context) |
| Skill non-blank lines | 500 | Anthropic official best practice |
| Skill words per SKILL.md | 2048 | User preference; co-binds with 500 lines at ~4 words/line |
| Skill description chars | 250 | Claude Code 2.1.86 `/skills` listing cap |
| Skill name chars | 64 | Anthropic frontmatter validation hard cap |
| CLAUDE.md [Instruction] count | 100 | Deliberately tight share — well under IFScale 500 ceiling |
| *-standards [Instruction] total | 200 | Deliberately tight share — well under IFScale 500 ceiling |
| CRITICAL ratio per file | 16% | Reasoned (Pareto + Miller + ConInstruct); flagged for re-derivation |

When dialling any budget, update both this file and `SKILL.md`'s table.

If a sourced value changes (e.g., Anthropic updates their skill-size guidance, or the 250-char `/skills` cap moves), update the linked URL and re-check every skill for overage against the new ceiling.
