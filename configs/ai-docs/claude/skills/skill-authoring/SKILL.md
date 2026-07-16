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

## CRITICAL: references/assets must buy real context savings, never budget cosmetics

Move text out of SKILL.md into `references/` or `assets/` only when the move keeps words out of context on typical runs:

- Conditional loads — some invocations never read the file (branches, domain variants, skippable examples).
- Subagent-consumed files — prompts and checklists read by a spawned agent, never by the main session.
- Late loads in marathon flows — content needed only near the end, read fresh after compactions would have dropped it.

A "mandatory read" the main flow opens at invocation time on every run is a fake lazy-load.
Keep that text in SKILL.md — get under the word budget with real trims, or set an honest `words-budget:` frontmatter override.

Why: an always-read reference loads the same words every run plus a Read round-trip — it saves nothing and hides the cost from the budget gate, which exists to measure that cost.

## Pin an explicit model on every subagent dispatch a skill prescribes

Name the model in the dispatch instruction: `sonnet` for mechanical or tool-driving steps, `haiku` for trivial transforms.
Omit the pin only when the step genuinely needs the session model's judgment — and say so in the skill.

Why: an unpinned Agent call inherits the session's model — often the most expensive tier — so a scripted mechanical fan-out silently runs at top-tier pricing on every future invocation.
