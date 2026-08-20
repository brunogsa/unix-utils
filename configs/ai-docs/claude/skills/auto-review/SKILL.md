---
name: auto-review
description: "USE for code review on a local branch (no PR URL — use /pr-review). Triggers: 'review this branch' / 'audit my changes' / /auto-review."
disable-model-invocation: false
---

# Auto Review

Orchestrate a local code review by running the `code-review-pipeline` pipeline
end-to-end, always inside an isolated subagent. Every wave but Wave 2 runs in
that one session; Wave 2 fans its eight specialists out concurrently, one
rubric each, so each rubric reasons in its own context instead of a shared one.

auto-review always dispatches isolated, never in-session. The invoking
session usually authored the code under review, and a same-session author
reviewing its own output carries "already convinced myself" bias — isolation
gives the review fresh context instead. Keeping the pipeline's read load out
of main context is a secondary benefit.

See "How callers dispatch" → "Isolated" in
`~/.claude/skills/code-review-pipeline/SKILL.md` for the subagent mechanics
that dispatch reuses (prompt body, reading this SKILL.md, orchestrating from
there). auto-review spawns the purpose-built `code-reviewer` agent instead of
the pipeline's default `general-purpose` isolated wrapper — review judgment
is the product here, so it forces `effort: high` and the write-guard hook
regardless of caller settings, unlike the mechanical `general-purpose` spawn,
whose effort inherits from the caller.

## Usage

`/auto-review [base-ref]`

- `base-ref` defaults to the repo's default branch (auto-detected; works
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

Resolve `<BASE_REF>`:

- If the user passed an argument, use it as-is.
- Else run `~/.claude/scripts/resolve-base-ref.sh` and use that. It falls
  back from origin/HEAD to local main to local master.
- If detection fails (none of the three resolve), ask the user which branch
  to diff against rather than guessing.

### Resolve `<SPEC_PLAN_PATHS>` (local-mode `{pr_context}` source)

The code-review-pipeline's local-mode `{pr_context}` is "spec + plan" content
(see `code-review-pipeline/references/common-preamble.md`). In CWDs that hold
multiple session-scoped specs/plans, the orchestrator must pick which
files feed the review — guessing would silently drop intent.

Discover candidates in CWD (top-level only, not recursive):

```bash
ls -1 spec_*.md plan_*.md 2>/dev/null
```

Apply this decision tree **per kind** — the spec and the plan resolve independently of each other:

- **Exactly one of a kind** → use it. Print the resolved paths; no prompt needed.

- **Zero of a kind** → proceed without it and say so plainly. No spec means no spec-conformance context; no plan means no planned-behavior context.
  - Zero of both kinds sets `<SPEC_PLAN_PATHS>=<none>`, and the review runs on commit messages plus the diff.

- **More than one of a kind** → prompt with a numbered list and these options; never guess which spec or plan was meant.
  - `all` — use every discovered file
  - one or more numbers (comma-separated, e.g. `1,3,5`) — use just those
  - `none` — skip spec/plan context entirely
  - `cancel` — abort the review

A prompt is only worth its friction when the human has something to choose between. One candidate or none leaves nothing to pick, so the run proceeds and reports what it used.

`/quality-gate` §2 resolves the same two files itself, then pushes the resolved paths into its `auto-review` leg — so a leg never reaches this step.

That tree splits the same zero/one/many way but answers a multi-match differently — a single pick, and under either `--auto-solve` or `--report-only` neither file rather than a prompt.

So one CWD can yield different spec/plan context depending on the entry point. Read `/quality-gate` §2 before assuming an edit here covers both.

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
- **Base ref:** `<BASE_REF>` (resolved above)
- **Language:** English
- **Spec/plan files for `{pr_context}`:** `<SPEC_PLAN_PATHS>` (resolved above)
  - If `<none>`, no spec/plan is available — proceed with commit messages +
    diff only.
  - Otherwise, the listed absolute paths must be read verbatim and their
    concatenated content used as `{pr_context}` for every specialist
    (replacing the default lookup of the spec and the plan).

With the inputs above resolved, always dispatch isolated: spawn
`agent(subAgent=code-reviewer, title=Review branch changes)`.
Put the resolved inputs in its prompt body, and tell it to read
`~/.claude/skills/code-review-pipeline/SKILL.md` and orchestrate from there
— per that file's "Isolated" dispatch mode under "How callers dispatch",
substituting the code-reviewer agent for the pipeline's default
`general-purpose` wrapper.

After the pipeline finishes, the review is at
`./verdict_auto-review_<branch>_<timestamp>.md` (Wave 6 summary contains the
exact resolved path). It is always Markdown — `address-verdicts` re-reads and
annotates it, which is exactly what the html-artifacts router's Gate 1 excludes
from an interactive page.
Print the file path, per-severity counts, skipped files, and the
Wave 6 summary. Multiple runs accumulate as separate files — the branch
segment keeps runs from different branches distinguishable, and the timestamp
preserves order when the user runs several reviews on the same branch in one
CWD.

File one `[Scout]` TaskList entry per file listed in that summary's
doc-standards-flags block, naming the file and what is off standard.

The pipeline always runs isolated here, so its own TaskList write never
reaches the user — this session is the first that can raise those flags, and
repairing a flagged line stays the user's call.

### Severity in the verdict headings

Each finding heading stamps an ordinal severity right after the number: `### N. [HIGH] path:lines`.

That is the same shape `/test-sdd` and `/refactor` emit, so `/address-verdicts` parses all three lenses identically.

The reviewer still reasons in the five priority tags: `MANDATORY`, `RECOMMENDED`, `NITPICK`, `OPTIONAL`, `QUESTION`.

The heading carries the ordinal each of those maps to, per the "Priority tags" section of `~/.claude/skills/code-review-pipeline/references/review-principles.md`, which owns that mapping.

A `QUESTION` finding heads `### N. [QUESTION] …` instead, carrying no ordinal at all.

`/address-verdicts`' severity floor therefore never filters it out, so a question that must be answered can't vanish under a `high` floor.

Emitting a priority tag where the ordinal belongs is what silently drops this lens out of every floored selection, since a floor has nothing to compare it against.

**Report only — the skill stops here.** `/auto-review` produces the report and applies nothing.

Applying is `/address-verdicts`' job: it globs `verdict_auto-review_*.md` and routes each finding to the `tdd-coder` agent, which applies it RED-before-GREEN and commits under `commit-standards`.

That is a test gate a reader sent to a generic "ask the AI to apply a subset" flow would have to reproduce by hand.

Acting on findings is a separate, explicit step the user initiates — it is not part of this flow.
