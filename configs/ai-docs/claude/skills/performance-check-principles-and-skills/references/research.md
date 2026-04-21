# Research References — Performance-Check Budgets

Citations backing every number in `SKILL.md`'s budget table. Read this when you need to defend a cut, or when proposing to dial a budget up or down.

## Table of contents

- [CLAUDE.md length](#claudemd-length)
- [CLAUDE.md words per line](#claudemd-words-per-line)
- [Skill size](#skill-size)
- [Skill count](#skill-count)
- [Skill words per SKILL.md](#skill-words-per-skillmd)
- [Summary](#summary)

---

## CLAUDE.md length

**Budget: 200 non-blank lines**

### Jaroslawicz et al. 2025 — instruction adherence peaks at 150–200

*How Many Instructions Can LLMs Follow at Once?* arXiv:2507.11538
https://arxiv.org/abs/2507.11538

IFScale benchmark across 20 frontier models. Key finding: "mid-range peaks around 150–200 instructions" before selective attention degrades. Best models drop to 68% accuracy at 500 instructions. Reasoning models hold up better through 100–250.

**Implication:** 200 non-blank lines is at the upper edge of the empirical safe zone. A line roughly equals an instruction for imperative-style rule-based CLAUDE.md files.

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

No external source. User preference backing the "Prefer scannable shape" principle in CLAUDE.md. Acts as a prose-bloat guard — 32 words is ~2 full sentences or ~200 characters, the upper edge of comfortable scanning. Most principles should come in well under; the budget is a ceiling, not a target.

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

**Budget: 32 skills**

No external source. User preference. Anthropic's skill-authoring docs mention Claude choosing "from potentially 100+ available Skills" — 32 is conservative, keeps metadata preload small, and forces consolidation when the surface grows.

---

## Skill words per SKILL.md

**Budget: 2048 words per SKILL.md**

No external source. User preference. Co-binds with the 500-line cap: at ~4 words per line (typical for imperative instructions with bullets), 500 lines ≈ 2000 words. The 2048 value gives a small cushion above the line co-bind while keeping skill bodies readable in one sitting (~8–10 minutes).

---

## Summary

| Budget | Value | Anchor |
|---|---|---|
| CLAUDE.md non-blank lines | 200 | HumanLayer community + Jaroslawicz 2025 peak (150–200) |
| CLAUDE.md words per line | 32 | User preference; prose-bloat guard |
| Skill total count | 32 | User preference; conservative vs. Anthropic's 100+ reference |
| Skill non-blank lines | 500 | Anthropic official best practice |
| Skill words per SKILL.md | 2048 | User preference; co-binds with 500 lines at ~4 words/line |

When dialling any budget, update both this file and `SKILL.md`'s table. If a sourced value changes (e.g., Anthropic updates their skill-size guidance), update the linked URL and re-check every skill for overage against the new ceiling.
