---
description: "Local code review of current branch vs base using an isolated foreground subagent"
disable-model-invocation: true
---

# Auto Review

Local code review using an isolated foreground subagent. The subagent has no main session context -- it gathers everything itself, ensuring an unbiased review.

## Usage

`/auto-review [base-branch]`

- `base-branch` defaults to `main`

Examples:
- `/auto-review` -- review current branch vs main
- `/auto-review develop` -- review current branch vs develop

## Execution

Launch a **single foreground Agent** (subagent_type: `general-purpose`) with the following prompt.

Replace `<BASE_BRANCH>` with the actual base branch argument (or `main` if omitted).

### Agent Prompt

```
Read `~/.claude/skills/reviewer-agent/SKILL.md` for your full instructions.

Mode: **local** (`/auto-review`)
Base branch: `<BASE_BRANCH>`
Language: **English**
```

After the subagent completes, the review is written to `./auto-review.md`. No further processing needed.
