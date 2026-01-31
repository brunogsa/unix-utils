---
description: "This skill should be used when the user asks to 'create a skill', 'add a new skill', 'make a skill for', or discusses organizing knowledge into Claude Code skills."
user-invocable: false
---

# Skill Creator

Guide for creating Claude Code skills following this project's conventions.

## Skill Location

Skills live at `~/unix-utils/configs/ai-docs/claude/skills/<skill-name>/SKILL.md`, symlinked to `~/.claude/skills/`.

## SKILL.md Structure

```markdown
---
description: "Third-person trigger description. Be specific about when to use."
user-invocable: false
---

# Skill Title

Brief intro (1-2 lines).

## Sections

Content organized by topic. Use headers, code blocks, tables, and lists.
```

## Frontmatter Fields

| Field | Required | Notes |
|-------|----------|-------|
| `description` | Yes | Triggers auto-loading. Use third-person: "This skill should be used when..." Include exact trigger phrases in quotes. |
| `user-invocable` | No | Set `false` for auto-loaded context (default). Set `true` + add `description` for `/slash` commands. |
| `name` | No | Display name (defaults to directory name). |
| `version` | No | Semver string. |

## Conventions

- **One concern per skill** -- don't mix unrelated topics.
- **Auto-loaded by default** -- use `user-invocable: false` unless the skill is a workflow triggered by `/slash`.
- **Description = trigger** -- Claude matches user intent to skill descriptions. Be concrete: include exact phrases users would say.
- **Static content only** -- `!`command`` syntax works in commands, NOT in skills. Skills are loaded as-is.
- **`@path` imports work** -- reference other files with `@~/path/to/file`.
- **Supporting files** -- put reference material in `references/` or `examples/` subdirs alongside SKILL.md.
- **Keep skills focused** -- aim for 40-200 lines. If larger, split into multiple skills or use supporting files.
- **Skill descriptions budget** -- all auto-loaded skill descriptions share ~15,000 char budget. Keep descriptions under 200 chars each.

## Examples

### Auto-loaded knowledge skill (most common)

```yaml
---
description: "Jira API shell utilities for issue CRUD, linking, querying, and status transitions"
user-invocable: false
---
```

### User-invocable workflow skill

```yaml
---
description: "Create a comprehensive code review with context gathering and GitHub posting"
user-invocable: true
---
```

## Checklist

1. Create `skills/<name>/SKILL.md` with frontmatter
2. Write focused, scannable content (headers, code blocks, tables)
3. Verify description triggers correctly (ask Claude about the topic)
4. Add symlink to `install.sh` if not already present (skills dir is symlinked as a whole)
