# Simplify Unpushed & Uncommitted Code

Analyze and simplify code from unpushed commits and uncommitted changes using the code-simplifier agent.

## Usage

`/refactor`

## Process

### Identify Target Files

Collect files from both unpushed commits and uncommitted changes (staged + unstaged + untracked):

```bash
# Unpushed commits
git diff --name-only @{upstream}..HEAD

# Uncommitted changes (staged + unstaged)
git diff --name-only HEAD

# Untracked files
git ls-files --others --exclude-standard
```

Deduplicate and merge the lists. If no files are found, inform the user and stop.

### Run Code Simplifier

Use the **Task tool** with `subagent_type=code-simplifier`. In the prompt:

- List the files identified above
- Instruct it to focus only on code touched by unpushed commits or uncommitted changes
- Instruct it to read and apply principles from:
  - `~/.claude/CLAUDE.md` (global guidelines)
  - `~/.claude/skills/code-standards/SKILL.md` (code patterns)
  - `~/.claude/skills/test-standards/SKILL.md` (test patterns)
- Instruct it to NOT propose changes that alter behavior, change formatting only, add features beyond what exists, or refactor code outside the changed files
