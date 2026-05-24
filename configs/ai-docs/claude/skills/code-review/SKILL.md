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

**Default: run in the calling session.** Specialist passes stream live so
the user can watch findings as they land. Right choice in fresh sessions
or when the user wants visibility into each wave.

**Opt-in `--isolate` flag: dispatch a subagent.** The subagent boundary
removes any bias from the current session's conversation. Use when the
review runs inside a long-lived session that already has opinions about
the PR.

## Usage

`/code-review <pr-url> [--jira <jira-url>] [--isolate]`

Examples:
- `/code-review https://github.com/owner/repo/pull/1597` — in-session.
- `/code-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123` — in-session with Jira context.
- `/code-review https://github.com/owner/repo/pull/1597 --isolate` — wrapped in a bias-isolation subagent.

## Execution

For maximum thinking depth on the wave pipeline, the user may run
`/effort max` before invoking this command.

The reviewer-agent expects these inputs:

- **Mode:** `github`
- **PR URL:** `<PR_URL>` (from the command argument)
- **Jira URL:** `<JIRA_URL>` (only if `--jira` was passed)
- **Language:** Portuguese (Brazil)

**Default — run in the calling session (no `--isolate`):**

Read `~/.claude/skills/reviewer-agent/SKILL.md` and execute its wave
pipeline directly in this session. Treat the inputs above as if they
arrived in the skill's "Parse the input header" step. Walk every wave
(0 → 6) yourself; do not spawn any Agent. The base branch is discovered
inside Wave 1 from `baseRefName`. Each specialist pass streams into the
conversation, giving the user live visibility.

**Opt-in — `--isolate` was passed:**

Spawn a single Agent and put the inputs above in its prompt body. Tell
the subagent to read `~/.claude/skills/reviewer-agent/SKILL.md` and follow
it as the orchestrator. The subagent runs the full pipeline itself — do
not spawn additional Agents from there. The user sees only the final
summary, not the per-wave progress; the trade-off buys bias isolation
from the calling session's conversation history.

After the pipeline finishes (either mode), the review is PENDING on
GitHub. Open `<pr-url>/files` to filter, edit, delete, or submit. Print
the review URL, per-severity counts, skipped files, and the Wave 6
summary.
