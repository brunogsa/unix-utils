---
name: code-review
description: "USE for code review on a GitHub PR URL (no URL — use /auto-review on your local branch). User-invoked only; posts a PENDING review you filter and submit."
disable-model-invocation: true
---

# Code Review

Orchestrate a GitHub PR review by running the `reviewer-agent` pipeline
end-to-end. The pipeline runs serially — no nested fan-out — so the review
stays within a predictable token budget. The output is a PENDING review on
GitHub; you filter and submit manually.

Execution mode (in-session vs. `--isolate` subagent) and the fresh-session check are shared across both review callers — see "How callers dispatch" in `~/.claude/skills/reviewer-agent/SKILL.md`.

## Usage

`/code-review <pr-url> [--jira <jira-url>] [--isolate]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597` — in-session.
- `/code-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123` — in-session with Jira context.
- `/code-review https://github.com/owner/repo/pull/1597 --isolate` — wrapped in a bias-isolation subagent.

## Execution

The reviewer-agent expects these inputs:

- **Mode:** `github`
- **PR URL:** `<PR_URL>` (from the command argument)
- **Jira URL:** `<JIRA_URL>` (only if `--jira` was passed)
- **Language:** Portuguese (Brazil)

With the inputs above resolved, dispatch per "How callers dispatch" in `~/.claude/skills/reviewer-agent/SKILL.md`.

Run the fresh-session check there, then either walk the pipeline in-session or spawn the isolated subagent. The base branch is discovered inside Wave 1 from `baseRefName`.

After the pipeline finishes (either mode), the review is PENDING on
GitHub. Open `<pr-url>/files` to filter, edit, delete, or submit. Print
the review URL, per-severity counts, skipped files, and the Wave 6
summary.
