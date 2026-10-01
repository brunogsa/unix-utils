---
name: pr-review
description: "USE for code review on a GitHub PR URL (no URL — use /auto-review on your local branch). Posts a PENDING review you filter and submit."
---

# PR Review

Orchestrate a GitHub PR review by running the `code-review-pipeline` pipeline end-to-end inside one background `code-reviewer` orchestrator. Wave 2 reviews inline in that agent by default and fans its eight rubrics out, one agent each, only past the pipeline's diff-size gate. The output is a PENDING review on GitHub; you filter and submit manually.

The dispatch is the same for both review callers — see "How callers dispatch" in `~/.claude/skills/code-review-pipeline/SKILL.md`.

## Usage

`/pr-review <pr-url> [--jira <jira-url>]`

Examples:
- `/pr-review https://github.com/owner/repo/pull/1597`
- `/pr-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123` — with Jira context.

## Execution

The code-review-pipeline expects these inputs:

- **Mode:** `github`
- **PR URL:** `<PR_URL>` (from the command argument)
- **Jira URL:** `<JIRA_URL>` (only if `--jira` was passed)
- **Language:** Portuguese (Brazil)

With the inputs above resolved, spawn `agent(subAgent=code-reviewer, title=Run code-review pipeline)` in the background, with the inputs in its prompt body and the instruction to read `~/.claude/skills/code-review-pipeline/SKILL.md` and orchestrate every wave (0 → 6) from there. Wait for its completion notification. The base branch is discovered inside Wave 1 from `baseRefName`.

After the orchestrator reports back, the review is PENDING on GitHub. Open `<pr-url>/files` to filter, edit, delete, or submit. Print the review URL, per-severity counts, skipped files, and the Wave 6 summary from its report.

## Flowchart (human-facing)

[`assets/flowchart.md`](assets/flowchart.md) diagrams this skill's flow for the human. Don't load it — non-authoritative, the steps above win; regenerate it whenever the flow changes.
