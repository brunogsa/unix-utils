---
description: "Local branch review via the reviewer-agent skill, dispatched as a subagent for bias isolation. The subagent reads the diff vs. base-branch, walks specialists serially in one session (no further fan-out), and writes the review to ./auto-review.md."
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

After the subagent returns, the review is at `./auto-review.md`. Print the
file path, per-severity counts, skipped files, and the Wave 6 summary.
