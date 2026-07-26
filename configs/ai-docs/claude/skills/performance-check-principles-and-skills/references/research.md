# Research References — Performance-Check Budgets

Citations backing every number in `SKILL.md`'s budget table. Read this when you need to defend a cut, or when proposing to dial a budget up or down.

The summary table at the bottom answers most questions on its own. Open a sibling file only when you need the full citation for one budget.

## Where each budget's citations live

The citations are split into three files so a reader loads one cluster, not all ten budgets' sources.

- [`research-claudemd-budgets.md`](research-claudemd-budgets.md) — how big CLAUDE.md may get.
  - [CLAUDE.md length](research-claudemd-budgets.md#claudemd-length) — 260 non-blank lines.
  - [CLAUDE.md words per line](research-claudemd-budgets.md#claudemd-words-per-line) — 32 words.
- [`research-skill-budgets.md`](research-skill-budgets.md) — everything measured per skill.
  - [Skill size](research-skill-budgets.md#skill-size) — 500 non-blank lines.
  - [Skill count](research-skill-budgets.md#skill-count) — 50 skills.
  - [Skill words per SKILL.md](research-skill-budgets.md#skill-words-per-skillmd) — 2048 words.
  - [Skill description length](research-skill-budgets.md#skill-description-length) — 250 chars.
  - [Skill name length](research-skill-budgets.md#skill-name-length) — 64 chars.
- [`research-instruction-load-budgets.md`](research-instruction-load-budgets.md) — how many rules a file may carry.
  - [Instruction-count budgets](research-instruction-load-budgets.md#instruction-count-budgets) — 100 in CLAUDE.md, 200 across `*-standards`.
  - [CRITICAL emphasis ratio](research-instruction-load-budgets.md#critical-emphasis-ratio) — 16% per file.

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
