---
name: pr-review
description: "USE for code review on a GitHub PR URL (no URL — use /auto-review on your local branch). Posts a PENDING review you filter and submit."
disable-model-invocation: true
---

# PR Review

Orchestrate a GitHub PR review by running the `code-review-pipeline` pipeline
end-to-end. The pipeline runs serially — no nested fan-out — so the review
stays within a predictable token budget. The output is a PENDING review on
GitHub; you filter and submit manually.

Execution mode (in-session vs. `--isolate` subagent) is shared across both review callers, and the pipeline auto-decides it from the mode without ever asking — see "How callers dispatch" in `~/.claude/skills/code-review-pipeline/SKILL.md`.

A running A/B experiment (below) currently overrides that shared default
for pr-review only — see "A/B experiment: review-isolation".

## Usage

`/pr-review <pr-url> [--jira <jira-url>] [--isolate]`

Examples:
- `/pr-review https://github.com/owner/repo/pull/1597` — in-session.
- `/pr-review https://github.com/owner/repo/pull/1597 --jira https://company.atlassian.net/browse/PROJ-123` — in-session with Jira context.
- `/pr-review https://github.com/owner/repo/pull/1597 --isolate` — wrapped in a bias-isolation subagent.

## A/B experiment: review-isolation

Question under test: does running the pipeline in a fresh dedicated main
session (arm A) vs. a fresh subagent (arm B) change review quality or cost.
Tracked in the `usage-audit` skill's `usage-history/experiments.md`
(`review-isolation` row) — remove this section once that row settles
(`kept`/`reverted`).

- Compute `arm` from the PR number, before any dispatch: even → `A`,
  odd → `B`. Deterministic and balanced across PRs, no infra needed.
- Print `[ABTest] experiment=review-isolation arm=<A|B> pr=<number>`
  immediately after computing the arm, before Wave 0 starts.
- If `--isolate` was passed, the run is forced to arm B regardless of
  PR parity — append ` override=manual` to the printed marker in that
  case, so forced runs can be excluded from the analysis.
- **Arm A (fresh main session):** check directly whether this session
  already did prior unrelated work — don't skip the question the way
  github mode normally does.
- If it did, stop and tell the user to `/clear` and re-invoke
  `/pr-review` — a contaminated session skews both review quality and
  the cost measurement.
- This "stop if contaminated" check encodes the user's standing policy
  that pr-review always runs in a fresh session.
- Otherwise, walk every wave (0 → 6) inline, per code-review-pipeline's
  "Inline — `Mode: github` without `--isolate`" dispatch.
- **Arm B (fresh subagent):** dispatch per code-review-pipeline's
  "Isolated — `Mode: local`, or `--isolate` passed" path — spawn the
  sonnet-pinned wrapper Agent, unconditionally.
- A new Agent is inherently fresh, so no session check is needed here.

## Execution

The code-review-pipeline expects these inputs:

- **Mode:** `github`
- **PR URL:** `<PR_URL>` (from the command argument)
- **Jira URL:** `<JIRA_URL>` (only if `--jira` was passed)
- **Language:** Portuguese (Brazil)

With the inputs above resolved, compute the arm and print the marker per
"A/B experiment: review-isolation" above, then run Arm A or Arm B as
assigned there. The base branch is discovered inside Wave 1 from
`baseRefName`.

After the pipeline finishes (either arm), the review is PENDING on
GitHub. Open `<pr-url>/files` to filter, edit, delete, or submit. Print
the review URL, per-severity counts, skipped files, and the Wave 6
summary.
