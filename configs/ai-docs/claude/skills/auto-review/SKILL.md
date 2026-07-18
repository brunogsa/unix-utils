---
name: auto-review
description: "USE for code review on a local branch (no PR URL — use /pr-review). Triggers: 'review this branch' / 'audit my changes' / /auto-review."
disable-model-invocation: false
---

# Auto Review

Orchestrate a local code review by running the `code-review-pipeline` pipeline
end-to-end, always inside an isolated subagent. The pipeline runs serially —
no nested fan-out — so the review stays within a predictable token budget.

auto-review always dispatches isolated, never in-session. The invoking
session usually authored the code under review, and a same-session author
reviewing its own output carries "already convinced myself" bias — isolation
gives the review fresh context instead. Keeping the pipeline's read load out
of main context is a secondary benefit.

See "How callers dispatch" → "Isolated" in
`~/.claude/skills/code-review-pipeline/SKILL.md` for the subagent mechanics
that dispatch reuses (prompt body, reading this SKILL.md, orchestrating from
there). auto-review overrides the model choice: the pipeline's default
isolated wrapper pins `model: "sonnet"`, but auto-review spawns the
`deep-reviewer` agent (opus) instead — review judgment is the product here,
so it earns the top tier, unlike mechanical spawns, which pin sonnet.

## Usage

`/auto-review [base-branch]`

- `base-branch` defaults to the repo's default branch (auto-detected; works
  for `main`, `master`, or anything else).

Every invocation runs isolated — there is no in-session mode left to opt
into or out of.

Examples:
- `/auto-review` — current branch vs. the repo's default (auto-detected).
- `/auto-review develop` — current branch vs. `develop`.
- `/auto-review HEAD~2` — review only the last 2 commits.

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

The code-review-pipeline's local-mode `{pr_context}` is "spec + plan" content
(see `code-review-pipeline/references/common-preamble.md`). In CWDs that hold
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

The code-review-pipeline expects these inputs:

- **Mode:** `local`
- **Base branch:** `<BASE_BRANCH>` (resolved above)
- **Language:** English
- **Spec/plan files for `{pr_context}`:** `<SPEC_PLAN_PATHS>` (resolved above)
  - If `<none>`, no spec/plan is available — proceed with commit messages +
    diff only.
  - Otherwise, the listed absolute paths must be read verbatim and their
    concatenated content used as `{pr_context}` for every specialist
    (replacing the default `spec_<slug>.md` + `plan_<slug>.md` lookup).

With the inputs above resolved, always dispatch isolated: spawn the
`deep-reviewer` agent (`subagent_type: deep-reviewer`) — its definition pins
model and effort, so no explicit `model` parameter is needed in the dispatch.
Put the resolved inputs in its prompt body, and tell it to read
`~/.claude/skills/code-review-pipeline/SKILL.md` and orchestrate from there
— per that file's "Isolated" dispatch mode under "How callers dispatch",
substituting deep-reviewer (opus) for the pipeline's default sonnet-pinned
wrapper.

Skip the pipeline's fresh-session check: that check exists only to pick
between in-session and isolated, and auto-review never picks — it always
isolates.

After the pipeline finishes, the review is at
`./report_auto-review_<timestamp>.md` or `.html` — extension per the html-artifacts
router (Wave 6 summary contains the exact resolved path).
Print the file path, per-severity counts, skipped files, and the
Wave 6 summary. Multiple runs accumulate as separate timestamped files,
preserving their order when the user runs several reviews in one CWD.

**Report only — the skill stops here.** `/auto-review` produces the report and applies nothing.

The user reads it and decides later which findings to act on — by hand, or by asking the AI to triage and apply a selected subset.

Acting on findings is a separate, explicit step the user initiates — it is not part of this flow.
