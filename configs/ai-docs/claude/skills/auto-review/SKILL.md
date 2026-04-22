---
description: "Local branch review using the wave-based reviewer-agent. Multiple parallel specialists + Review Guide (business context, decisions, where to focus, incidental changes) → written to ./auto-review.md. Strongest review at the cost of 30s–3min setup."
disable-model-invocation: true
---

# Auto Review

Orchestrate a local code review by delegating to `reviewer-agent`. The subagent has no prior conversation context — it gathers the diff vs. `base-branch`, reads files from CWD, and writes the review to `./auto-review.md`.

## Usage

`/auto-review [base-branch]`

- `base-branch` defaults to `main`.

Examples:
- `/auto-review` — current branch vs. main.
- `/auto-review develop` — current branch vs. develop.

## Execution

Before launching the agent, run `/effort max` so the wave pipeline thinks as deeply as it can.

Launch a **single foreground Agent** (subagent_type: `general-purpose`, model: `opus`) with the prompt below. Replace `<BASE_BRANCH>` with the argument, or `main` when omitted.

### Agent prompt

```
Read `~/.claude/skills/reviewer-agent/SKILL.md` for your full instructions.

Mode: **local** (`/auto-review`)
Base branch: `<BASE_BRANCH>`
Language: **English**
```

After the subagent completes, the review lives at `./auto-review.md`. The skill prints the file path, per-severity counts, skipped files, and token totals.
