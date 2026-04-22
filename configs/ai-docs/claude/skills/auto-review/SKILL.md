---
description: "Local branch review using the wave-based reviewer-agent. Multiple parallel specialists + Review Guide (business context, decisions, where to focus, incidental changes) → written to ./auto-review.md. Strongest review at the cost of 30s–3min setup."
disable-model-invocation: true
---

# Auto Review

Orchestrate a local code review by running `reviewer-agent` directly in the current session. The pipeline reads the diff vs. `base-branch`, reads files from CWD, and writes the review to `./auto-review.md`.

For an unbiased review, start a **fresh Claude Code session** before invoking this command — the current session's conversation would otherwise color the review.

## Usage

`/auto-review [base-branch]`

- `base-branch` defaults to the repo's default branch (auto-detected; works for `main`, `master`, or anything else).

Examples:
- `/auto-review` — current branch vs. the repo's default (auto-detected).
- `/auto-review develop` — current branch vs. develop.

## Execution

For maximum thinking depth on the wave pipeline, the user may run `/effort max` before invoking this command.

Resolve `<BASE_BRANCH>`:
- If the user passed an argument, use it as-is.
- Else, run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'` and use that.
- If detection fails (no origin HEAD set), ask the user which branch to diff against rather than guessing.

Then, in the **current session** (no subagent wrapper):

1. Read `~/.claude/skills/reviewer-agent/SKILL.md` and follow it as the orchestrator.
2. Use these inputs:
   - **Mode:** `local`
   - **Base branch:** `<BASE_BRANCH>` (resolved above)
   - **Language:** English

Reviewer-agent's pipeline spawns its own specialists/validators as parallel subagents per its design. The main session is the orchestrator.

After the pipeline completes, the review lives at `./auto-review.md`. Print the file path, per-severity counts, skipped files, and the Wave 8 summary.
