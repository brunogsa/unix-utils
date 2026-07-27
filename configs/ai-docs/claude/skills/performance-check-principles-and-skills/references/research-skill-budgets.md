# Research — skill count, size, and metadata budgets

Citations behind the five per-skill numbers: 500 non-blank lines, 2048 words, 50 total skills, 250 description chars, and 64 name chars.

[`research.md`](research.md) indexes all three research files and carries the summary table.

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

