---
name: auto-review
description: "USE for code review on a local branch (no PR URL — use /code-review). Triggers: 'review this branch' / 'audit my changes' / /auto-review. AUTONOMOUS: plan execution + end-of-branch pass."
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

## When to invoke

**Default mode (interactive):** only on explicit user trigger.

Triggers include direct `/auto-review` invocation or phrases like "review this branch" / "audit my changes" / "check what I just did" / "run a local review".

Do NOT auto-trigger from "task done" or similar; the user reserves this command.

**Autonomous mode** has two trigger points:

1. **Per-task gate during plan execution** — `/auto-review HEAD~N` after each task's commits, where N is the number of commits the task produced.
   - Fix MANDATORY findings before the next task.
   - Log RECOMMENDED/lower to plan.md as incidentals.
2. **Final pass at end-of-branch** — after `/refactor` and before `/create-pr` (sequence: refactor → final auto-review + fixes → create-pr). Catches anything refactor introduced and gives create-pr clean ground to describe.

The base argument accepts any git ref (commit SHA, branch name, `HEAD~N`), so per-task scoping reuses the full-branch flow.

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

## Acting on findings

Before applying any fix, emit the "leveraging tasklist" trigger phrase so CLAUDE.md's TaskList protocol takes over. The skill's only job here is choosing the gating mode and the category prefix per finding.

- **Interactive mode:** ask which findings to address (all MANDATORY, specific numbers, none). On selection, emit *"Selected N findings. Leveraging tasklist."*
- **Autonomous mode (per-task or end-of-branch):** MANDATORY findings are fixed without asking. Emit *"N MANDATORY findings to fix. Leveraging tasklist."* before touching code.
- Category prefix per task: `[Drift]` for collateral fixes needed to make the current task work, `[Scout]` for pre-existing issues the review surfaced, `[Refactor]` or `[Task]` otherwise.
