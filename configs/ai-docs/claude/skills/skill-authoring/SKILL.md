---
name: skill-authoring
description: "Creating, editing, improving, packaging, or evaluating a skill, or writing/optimizing a SKILL.md description: Bruno's local superset of the skill-creator skill — ALWAYS load this alongside skill-creator for those tasks."
user-invocable: false
---

# Skill Authoring

Rules for writing and maintaining Claude Code skills.

## Load `skill-creator` before creating or modifying any SKILL.md

Never author skill content without it.

Why: it carries the folder structure (SKILL.md + scripts/ + references/), the progressive-disclosure rules, and the frontmatter conventions — all easy to get wrong from memory.

## Load `personal-environment` too — skills live behind a symlink

`~/.claude/skills/` symlinks into `~/unix-utils/`, so the file you edit and the path you commit are different, and `~/.claude/` is not itself a git repo.

Why: `personal-environment` carries the symlink + canonical-path rules; without them you stage from the wrong directory or assume `~/.claude/` is the repo and the commit fails.

## Skill descriptions state goal + triggers, not an inventory

State the skill's purpose and when to invoke it; don't enumerate what it covers. Detail belongs in the body.

Why: only the first 250 chars participate in `/skills` routing (Claude Code 2.1.86+ cap). Inventory burns that budget on details that don't change the trigger decision.
