# Simplify Unpushed Code

Analyze and simplify code from unpushed commits using the code-simplifier agent.

## Usage

`/simplify`

## Process

### 1. Identify Target Files

```bash
git diff --name-only @{upstream}..HEAD
```

If no unpushed commits exist, inform the user and stop.

### 2. Run Code Simplifier

Use the **Task tool** with `subagent_type=code-simplifier`. In the prompt:

- List the files identified in step 1
- Instruct it to focus only on code touched by unpushed commits
- Instruct it to read and apply principles from:
  - `~/.claude/CLAUDE.md` (global guidelines)
  - `~/.claude/skills/code-standards/SKILL.md` (code patterns)
  - `~/.claude/skills/test-standards/SKILL.md` (test patterns)
- Instruct it to NOT propose changes that alter behavior, change formatting only, add features beyond what exists, or refactor code outside the unpushed commits
