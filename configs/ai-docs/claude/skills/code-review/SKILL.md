---
description: "GitHub PR code review using the wave-based reviewer-agent. Produces a single PENDING review (not published) with a Review Guide in the body and validated inline comments — so you filter and submit manually."
disable-model-invocation: true
---

# Code Review

Orchestrate a GitHub PR review by delegating to `reviewer-agent`. The subagent has no prior conversation context — it gathers PR metadata, diff, files, existing comments, and Jira snippet itself, then posts a PENDING review to GitHub. You review it in the UI and submit on your own terms.

## Usage

`/code-review <pr-url> [--jira <jira-url>]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597`
- `/code-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123`

## Execution

Before launching the agent, run `/effort max` to ensure maximum thinking depth for the wave pipeline.

Launch a **single foreground Agent** (subagent_type: `general-purpose`, model: `opus`) with the prompt below. Replace `<PR_URL>` and optionally `<JIRA_URL>`.

### Agent prompt (without Jira)

```
Read `~/.claude/skills/reviewer-agent/SKILL.md` for your full instructions.

Mode: **github** (`/code-review`)
PR URL: `<PR_URL>`
Language: **Portuguese (Brazil)**
```

### Agent prompt (with --jira)

```
Read `~/.claude/skills/reviewer-agent/SKILL.md` for your full instructions.

Mode: **github** (`/code-review`)
PR URL: `<PR_URL>`
Jira URL: `<JIRA_URL>`
Language: **Portuguese (Brazil)**
```

After the subagent completes, the review is PENDING on GitHub — open `<pr-url>/files` to filter, edit, delete, or submit. The skill prints the review URL, per-severity counts, skipped files, and token totals.
