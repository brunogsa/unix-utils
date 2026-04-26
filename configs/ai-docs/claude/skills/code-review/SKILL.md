---
description: "GitHub PR review via the reviewer-agent skill. User-invoked only — wraps reviewer-agent in a subagent and posts a PENDING review."
disable-model-invocation: true
---

# Code Review

Orchestrate a GitHub PR review by dispatching **one** subagent that runs the
`reviewer-agent` pipeline end-to-end. The subagent boundary isolates the
review from the current session's conversation (bias removal). Everything
inside the subagent runs serially in that single session — no nested
fan-out — so the review stays within a predictable token budget.

The output is a PENDING review on GitHub; you filter and submit manually.

## Usage

`/code-review <pr-url> [--jira <jira-url>]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597`
- `/code-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123`

## Execution

For maximum thinking depth on the wave pipeline, the user may run
`/effort max` before invoking this command.

Spawn a single Agent with these inputs in the prompt body:

- **Mode:** `github`
- **PR URL:** `<PR_URL>` (from the command argument)
- **Jira URL:** `<JIRA_URL>` (only if `--jira` was passed)
- **Language:** Portuguese (Brazil)

Tell the subagent to read `~/.claude/skills/reviewer-agent/SKILL.md` and
follow it as the orchestrator. The base branch is discovered inside the
pipeline's Wave 1 from `baseRefName`. The subagent runs the full pipeline
itself — do not spawn additional Agents from here.

After the subagent returns, the review is PENDING on GitHub. Open
`<pr-url>/files` to filter, edit, delete, or submit. Print the review URL,
per-severity counts, skipped files, and the Wave 6 summary.
