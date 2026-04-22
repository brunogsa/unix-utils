---
description: "GitHub PR code review using the wave-based reviewer-agent. Produces a single PENDING review (not published) with a Review Guide in the body and validated inline comments — so you filter and submit manually."
disable-model-invocation: true
---

# Code Review

Orchestrate a GitHub PR review by running `reviewer-agent` directly in the current session. The pipeline gathers PR metadata, diff, files, and optional Jira snippet, then posts a PENDING review to GitHub. You review it in the UI and submit on your own terms.

For an unbiased review, start a **fresh Claude Code session** before invoking this command — the current session's conversation would otherwise color the review.

## Usage

`/code-review <pr-url> [--jira <jira-url>]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597`
- `/code-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123`

## Execution

For maximum thinking depth on the wave pipeline, the user may run `/effort max` before invoking this command.

In the **current session** (no subagent wrapper):

1. Read `~/.claude/skills/reviewer-agent/SKILL.md` and follow it as the orchestrator.
2. Use these inputs:
   - **Mode:** `github`
   - **PR URL:** `<PR_URL>` (from the command argument)
   - **Jira URL:** `<JIRA_URL>` (only if `--jira` was passed)
   - **Language:** Portuguese (Brazil)

The base branch is read from the PR's `baseRefName` inside reviewer-agent's Wave 1 — no need to resolve it here. Reviewer-agent's pipeline spawns its own specialists/validators as parallel subagents per its design. The main session is the orchestrator.

After the pipeline completes, the review is PENDING on GitHub — open `<pr-url>/files` to filter, edit, delete, or submit. Print the review URL, per-severity counts, skipped files, and the Wave 8 summary.
