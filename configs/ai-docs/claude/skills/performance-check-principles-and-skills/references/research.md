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
- [Summary](#summary)

---

## CLAUDE.md length

**Budget: 200 non-blank lines**

### Jaroslawicz et al. 2025 — instruction adherence peaks at 150–200

*How Many Instructions Can LLMs Follow at Once?* arXiv:2507.11538
https://arxiv.org/abs/2507.11538

IFScale benchmark across 20 frontier models. Key findings:

- "Mid-range peaks around 150–200 instructions" before selective attention degrades.
- Best models drop to 68% accuracy at 500 instructions.
- Reasoning models hold up better through 100–250.

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

**Budget: 32 skills**

No external source. User preference. Anthropic's skill-authoring docs mention Claude choosing "from potentially 100+ available Skills" — 32 is conservative, keeps metadata preload small, and forces consolidation when the surface grows.

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
- With 32 skills loaded, that's ~3,200 tokens before any conversation begins.

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

## Summary

| Budget | Value | Anchor |
|---|---|---|
| CLAUDE.md non-blank lines | 200 | HumanLayer community + Jaroslawicz 2025 peak (150–200) |
| CLAUDE.md words per line | 32 | User preference; prose-bloat guard |
| Skill total count | 32 | User preference; conservative vs. Anthropic's 100+ reference |
| Skill non-blank lines | 500 | Anthropic official best practice |
| Skill words per SKILL.md | 2048 | User preference; co-binds with 500 lines at ~4 words/line |
| Skill description chars | 250 | Claude Code 2.1.86 `/skills` listing cap |
| Skill name chars | 64 | Anthropic frontmatter validation hard cap |

When dialling any budget, update both this file and `SKILL.md`'s table.

If a sourced value changes (e.g., Anthropic updates their skill-size guidance, or the 250-char `/skills` cap moves), update the linked URL and re-check every skill for overage against the new ceiling.
