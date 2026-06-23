---
name: skill-authoring
description: "Load when creating or editing a SKILL.md: skill folder structure, frontmatter, and how descriptions route in /skills. USE when authoring/modifying a skill or writing its description."
user-invocable: false
---

# Skill Authoring

Rules for writing and maintaining Claude Code skills.

## Load `skill-creator` before creating or modifying any SKILL.md

Never author skill content without it.

Why: it carries the folder structure (SKILL.md + scripts/ + references/), the progressive-disclosure rules, and the frontmatter conventions — all easy to get wrong from memory.

## Skill descriptions state goal + triggers, not an inventory

State the skill's purpose and when to invoke it; don't enumerate what it covers. Detail belongs in the body.

Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap). Inventory burns that budget on details that don't change the trigger decision.
