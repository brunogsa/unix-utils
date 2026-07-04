---
name: auto-review
description: "USE for code review on a local branch (no PR URL — use /code-review). Triggers: 'review this branch' / 'audit my changes' / /auto-review."
disable-model-invocation: false
---

# Auto Review

Orchestrate a local code review by running the `reviewer-agent` pipeline
end-to-end. The pipeline runs serially — no nested fan-out — so the review
stays within a predictable token budget.

Execution mode (in-session vs. `--isolate` subagent) and the fresh-session check are shared across both review callers — see "How callers dispatch" in `~/.claude/skills/reviewer-agent/SKILL.md`.

## Usage

`/auto-review [base-branch] [--isolate]`

- `base-branch` defaults to the repo's default branch (auto-detected; works
  for `main`, `master`, or anything else).
- `--isolate` opts into the bias-isolation subagent wrapper. Off by default.

Examples:
- `/auto-review` — current branch vs. the repo's default (auto-detected), runs in-session.
- `/auto-review develop` — current branch vs. `develop`, in-session.
- `/auto-review HEAD~2` — review only the last 2 commits.
- `/auto-review --isolate` — current branch vs. default, wrapped in a subagent.
- `/auto-review main --isolate` — explicit base + isolated.

## When to invoke

Direct `/auto-review` invocation or phrases like "review this branch" / "audit my changes" / "check what I just did" / "run a local review".

Another skill's flow may also dispatch it (e.g. `/implement`'s batch-end tail).

The base argument accepts any git ref (commit SHA, branch name, `HEAD~N`), so you can scope the review to a subset of commits and still reuse the full-branch flow.

## Execution

Resolve `<BASE_BRANCH>`:

- If the user passed an argument, use it as-is.
- Else run `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'`
  and use that.
- If detection fails (no `origin/HEAD` set), ask the user which branch to
  diff against rather than guessing.

### Resolve `<SPEC_PLAN_PATHS>` (local-mode `{pr_context}` source)

The reviewer-agent's local-mode `{pr_context}` is "spec + plan" content
(see `reviewer-agent/references/common-preamble.md`). In CWDs that hold
multiple session-scoped specs/plans, the orchestrator must pick which
files feed the review — guessing would silently drop intent.

Discover candidates in CWD (top-level only, not recursive):

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

Apply this decision tree:

- **Zero matches** → set `<SPEC_PLAN_PATHS>=<none>`. Tell the user explicitly
  that the review will run without spec/plan context.
- **Exactly one spec file AND exactly one plan file** (e.g. `spec_auth.md` +
  `plan_auth.md`) → use both. Print the resolved paths; no prompt needed.
- **Any other shape** (multiple specs, multiple plans, only spec, only plan,
  mixed counts) → ALWAYS prompt the user with a numbered list and these
  options:
  - `all` — use every discovered file
  - one or more numbers (comma-separated, e.g. `1,3,5`) — use just those
  - `none` — skip spec/plan context entirely
  - `cancel` — abort the review

Render the prompt like:

```
Found multiple spec/plan files in CWD. Which should feed the review?

  1. spec_dbma-877.md
  2. spec_watchable-scenarios.md
  3. plan_integrator.md
  4. plan_partial-success-no-fanout.md

Reply with: all | <numbers> | none | cancel
```

Wait for the user's reply before proceeding. Resolve their selection into
an absolute-path list and store it as `<SPEC_PLAN_PATHS>` (space-separated,
or the literal string `<none>`).

### Dispatch the reviewer pipeline

The reviewer-agent expects these inputs:

- **Mode:** `local`
- **Base branch:** `<BASE_BRANCH>` (resolved above)
- **Language:** English
- **Spec/plan files for `{pr_context}`:** `<SPEC_PLAN_PATHS>` (resolved above)
  - If `<none>`, no spec/plan is available — proceed with commit messages +
    diff only.
  - Otherwise, the listed absolute paths must be read verbatim and their
    concatenated content used as `{pr_context}` for every specialist
    (replacing the default `spec_<slug>.md` + `plan_<slug>.md` lookup).

With the inputs above resolved, dispatch per "How callers dispatch" in `~/.claude/skills/reviewer-agent/SKILL.md`.

Run the fresh-session check there, then either walk the pipeline in-session or spawn the isolated subagent.

After the pipeline finishes (either mode), the review is at
`./auto-review_<timestamp>.md` (Wave 6 summary contains the exact resolved
path). Print the file path, per-severity counts, skipped files, and the
Wave 6 summary. Multiple runs accumulate as separate timestamped files,
preserving their order when the user runs several reviews in one CWD.

## Acting on findings

Before applying any fix, emit the "leveraging tasklist" trigger phrase so CLAUDE.md's TaskList protocol takes over. The skill's only job here is choosing the category prefix per finding.

- Ask which findings to address (all MANDATORY, specific numbers, none). On selection, emit *"Selected N findings. Leveraging tasklist."*
- Category prefix per task: `[Drift]` for collateral fixes needed to make the current task work, `[Scout]` for pre-existing issues the review surfaced, `[Refactor]` or `[Task]` otherwise.

## Verify the full check matrix after fixes — MANDATORY

After ALL approved fixes are applied (at the end of the batch, not after each), run the full post-change verification gate — load and follow `~/.claude/skills/reviewer-agent/references/verify-check-matrix.md`.

Review-driven fixes look mechanical, but renames, contract changes, removed code, and type-narrowing tweaks all surface failures here — not at edit time.
