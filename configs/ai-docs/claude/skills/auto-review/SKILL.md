---
description: "USE when finishing a coherent change before pushing/PR-ing — at task boundaries during autonomous plan execution, before /create-pr, or when the user says 'review this branch' / 'audit my changes' / 'check what I just did' / 'run a local review'. Spawns reviewer-agent (8 serial specialists + validator + drop off-diff) in an isolated subagent; writes ./auto-review_YYYY-MM-DD_HH-MM.md. Use even on small diffs — tiny-PR fast-path keeps cost low."
disable-model-invocation: false
---

# Auto Review

Orchestrate a local code review by dispatching **one** subagent that runs the
`reviewer-agent` pipeline end-to-end. The subagent boundary isolates the
review from the current session's conversation (bias removal). Everything
inside the subagent runs serially in that single session — no nested
fan-out — so the review stays within a predictable token budget.

## Usage

`/auto-review [base-branch]`

- `base-branch` defaults to the repo's default branch (auto-detected; works
  for `main`, `master`, or anything else).

Examples:
- `/auto-review` — current branch vs. the repo's default (auto-detected).
- `/auto-review develop` — current branch vs. `develop`.
- `/auto-review HEAD~2` — review only the last 2 commits (per-task scoping).

## Per-task usage during autonomous execution

In autonomous mode, gate each task before moving to the next:

`/auto-review HEAD~N`

where N is the number of commits the just-finished task produced. The base argument accepts any git ref (commit SHA, branch name, `HEAD~N`), so per-task scoping reuses the full-branch flow.

If MANDATORY findings surface, fix before the next task. If only RECOMMENDED/lower, log to plan.md as incidentals and continue.

## Execution

For maximum thinking depth on the wave pipeline, the user may run
`/effort max` before invoking this command.

Resolve `<BASE_BRANCH>`:

- If the user passed an argument, use it as-is.
- Else run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`
  and use that.
- If detection fails (no `origin/HEAD` set), ask the user which branch to
  diff against rather than guessing.

Spawn a single Agent with these inputs in the prompt body:

- **Mode:** `local`
- **Base branch:** `<BASE_BRANCH>` (resolved above)
- **Language:** English

Tell the subagent to read `~/.claude/skills/reviewer-agent/SKILL.md` and
follow it as the orchestrator. The subagent runs the full pipeline itself
— do not spawn additional Agents from here.

After the subagent returns, the review is at `./auto-review_<timestamp>.md`
(Wave 6 summary contains the exact resolved path). Print the file path,
per-severity counts, skipped files, and the Wave 6 summary. Multiple runs
accumulate as separate timestamped files — preserves ordering across
per-task and end-of-branch invocations.
