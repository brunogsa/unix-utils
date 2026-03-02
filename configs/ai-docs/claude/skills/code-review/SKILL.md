---
description: "GitHub PR code review using an isolated foreground subagent, posting changelog and inline comments via gh CLI"
disable-model-invocation: true
---

# Code Review

GitHub PR code review using an isolated foreground subagent. The subagent has no main session context -- it gathers PR metadata, diff, files, existing comments, and Jira context itself, then posts the review to GitHub.

## Usage

`/code-review <pr-url> [--jira <jira-url>]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597`
- `/code-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123`

## Execution

Launch a **single foreground Agent** (subagent_type: `general-purpose`) with the following prompt.

Replace `<PR_URL>` with the actual PR URL. Include the `Jira URL` line only if `--jira` was provided.

### Agent Prompt

```
Read `~/.claude/skills/reviewer-agent/SKILL.md` for your full instructions.

Mode: **github** (`/code-review`)
PR URL: `<PR_URL>`
Jira URL: `<JIRA_URL>`
Language: **Portuguese (Brazil)**
```

After the subagent completes, the review has been posted to GitHub. No further processing needed.
