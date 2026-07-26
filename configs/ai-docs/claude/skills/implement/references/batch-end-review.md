---
# performance-check budget override, not batch-end content.
# This file merges what used to be two references, because every section fires on the same
# run — a split would only re-fragment one sequence across two files always read together.
# The redundancy against SKILL.md's batch-end steps was already trimmed out (1418 -> 1345
# words); what remains is the per-step detail those steps point at. Doubled from the 1024w
# bundled default.
words-budget: 2048
---
# Batch-end — repo-green, tails, triage, package, metrics & finalize

Detail for /implement's batch-end steps. Load when the batch reaches its end.

SKILL.md's `§9.1 → (§9.2 ∥ §9.3) → §9.4 → §9.5` is the running order, and the only place that sequence is written down.
This file expands each of those steps; it never restates their order.

The PR steps — manifest entry and the opt-in draft PR — live in [`batch-end-pr.md`](batch-end-pr.md), reached from Finalize below.
Skip that file entirely when the run is neither a PR-label run nor an opted-in draft.

## Repo-green check (§9.1)

Run this first, so the tails analyze green code. Run the repo's **full lint + full test suite** — not just the batch's files.

- **Cheap failures** (lint autofix, a trivial assertion update) → fix each in **its own commit**; list them under "Unexpected extras" in the package.
- **Structural failures** (a real design break, not a one-line fix) → auto-queue a `[Scout]` TaskList item per finding; do **not** fix them.
  - While any structural failure remains, the package explicitly flags **"repo not green"**.

This is the **only** auto-apply path at batch end. Tail findings are never applied here — the orchestrator triages them and you decide (below).

## The two tails (§9.2–§9.3)

Full dispatch contract, preamble, failure handling, and overwrite policy: [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../../code-review-pipeline/references/deep-reviewer-tail-pair.md).

`<BASE_REF>` = `<BATCH_BASE_SHA>` (captured in §1.4); `<SPEC_PLAN_PATHS>` = the resolved `spec_<slug>.md`/`plan_<slug>.md`.

What's specific to `/implement`:

- The TaskList already carries this step as the `Batch-end 3/5` reminder seeded in §2.2 — flip that one entry, and don't queue a separate item per tail.
- When a tail returns, confirm its report file exists at the assigned path, then record that **path** into `.tails.refactor_report` / `.tails.auto_review_report`.
  - Record the path, never the content: a resumed run reads it back to see which reports already exist.
- Record each tail's token count into `.tails.tokens.<name>` (`0` when the Agent result omits it), which the metrics script sums into the subagent total.

## Triage both reports (§9.4)

Follow the shared reference's triage procedure: read both reports, synthesize one prioritized apply-offer summary.
This synthesis is **additive** to the two raw report paths — the package carries **both**.

When the human names specific findings to apply after seeing the package, follow the shared reference's "Applying a single finding, on explicit request" — with one implement-specific routing choice:

- This deliberately overrides the shared reference's generic routing (a single `general-purpose` subagent for every finding); the reference's own note cross-links back here.
- **A refactor-lens finding** (from `verdict_refactor_*.md`) → dispatch the **`refactor` agent** (Agent tool, `subagent_type=refactor` — its frontmatter pins model/effort, no override needed).
  Pass it the finding's scope and the caller's test command; it applies the change itself and confirms tests stay green before and after.
- **An auto-review-lens finding** (from `verdict_auto-review_*.md`) → dispatch a fresh `tdd-coder` subagent (model omitted — its frontmatter pins sonnet) per the §4 contract with strict TDD (RED before GREEN), unchanged.
  The refactor agent refuses behavior changes, so a correctness fix can't route through it.
- Verify the diff (§5.1) before trusting `done`, either way.

Once a fix lands, annotate its finding in the timestamped report file — `APPLIED` (with the fix commit SHA) or `SKIPPED` (with the reason).

The report is the durable, on-disk ledger of what got fixed versus deferred; this is the **only** report-file write the orchestrator itself makes.

## The review package (§9.5)

The package is the single async pass the human reviews — the replacement for the per-task handshake. Finalize prints it (below), after metrics. It contains:

- **Per-task outcomes** — each task labeled `done` / `blocked` / `stuck`, with its commit SHAs.
- **Both raw tail-report paths** (`verdict_refactor_<ts>.md`, `verdict_auto-review_<ts>.md`), plus any missing-report flag from failure handling.
- **The triaged synthesis** (above), with its apply-offer.
- **Every recorded `[Scout]` note and every block**, with what each needs to clear.
- **The literal diff range** — print `git diff BATCH_BASE_SHA..HEAD` with the actual SHA substituted, so the human can reproduce the range.
- **"Unexpected extras"** — the repo-green cheap fixes committed above (and any completed Scout fixes), each with its commit.
- **Run metrics** — total wall-clock time and summed tokens from the metrics script (below).
- **Repo-green status** — flag "repo not green" when any structural failure remains as a Scout.
- **TDD opt-out note** — when §8's gate passed as all-N/A, state the explicit opt-out.
- **Worktree merge-back reminder** — only when a worktree exists (read its path + branch from the state file); omit entirely when the interview declined it.
  - The reminder ends the package: its path, its branch, and "nothing was merged or deleted — merge back and remove it yourself".

On a **halted** batch — budget hit, or any task left `blocked` / `stuck` — present this as a **partial** package, still labeling each task `done` / `blocked` / `stuck`.

## Open the diff for review (neovim diffview)

After printing the summary, open the batch diff in a **side-by-side tmux pane** running neovim diffview, via the `open-in-tmux` skill, so the human reviews — and can directly edit — the changes:

```bash
~/.claude/skills/open-in-tmux/scripts/open-in-tmux.sh vertical "cd '<worktree-or-cwd>' && nvim -c 'DiffviewOpen <BATCH_BASE_SHA>'"
```

- Mode `vertical` splits the current pane side-by-side (the user chose a pane, not a window).
- The `cd` is mandatory: the pane inherits the orchestrator's cwd, which differs from the worktree when the interview chose one, so without it the diff opens against the wrong tree.
- **Diff against the bare `<BATCH_BASE_SHA>`, never `<BATCH_BASE_SHA>..HEAD`** — the bare base compares base ⟷ working tree (right pane editable); `..HEAD` diffs two commits (both panes read-only).
- On a clean batch the working tree equals HEAD, so the editable view shows exactly the batch; edits land as uncommitted changes atop the batch commits.
- Outside tmux the skill exits non-zero and prints the full command for the human to run. Requires the `diffview.nvim` plugin.

## Run metrics

Compute run totals with the pure metrics script:

```bash
~/.claude/skills/implement/scripts/implement-loop-metrics.sh <state-file> <transcript-jsonl>
```

It prints JSON: `{duration_seconds, tokens:{per_task, subagent_total, orchestrator_total, total}, over_budget_tasks}`. Fold these totals into the package.

- **Always pass the transcript path as the 2nd arg** — without it, `orchestrator_total` is silently `0`.
  - The orchestrator can't observe its own token use in-session, so the transcript is the only source; omitting the arg undercounts the total.
- Derive the transcript path as `~/.claude/projects/<cwd-slug>/<session_id>.jsonl`.
  - `<cwd-slug>` is the absolute CWD path with every `/` replaced by `-` (e.g. `/Users/x/repo` → `-Users-x-repo`).
  - `<session_id>` comes from the state file.
- `over_budget_tasks` lists any task above the 200000-token budget.
  - Surface each as a plan-granularity smell — the task was too big for one context window.

## Finalize — the step order inside §9.5

The print comes last of the review steps because the package must carry the metrics, and metrics needs `presented_at` — so stamp, compute, then print.

1. **Write `presented_at`** to the state file (the metrics script derives `duration_seconds` from `started_at`/`presented_at`).
2. **Run the metrics script** now that `presented_at` exists (see "Run metrics") and fold its totals into the package.
3. **Assemble the package** (contents under "The review package") and **print it** to chat — the single async review pass.
4. **Open the diffview pane** (see "Open the diff for review").
5. **PR manifest entry & status marker**, on a PR-label run (see [`batch-end-pr.md`](batch-end-pr.md)).
6. **Draft PR** if the interview opted in (see [`batch-end-pr.md`](batch-end-pr.md)'s "Draft PR (opt-in)").
7. **Delete or keep the state file by terminal phase.** The phase set here is the Stop hook's release signal.
   - The hook blocks stops while phase is `tasks` / `gates` / `tails`, and allows them once phase is `presented` or `halted`.
   - **Every task `done`** → set `phase: presented` and **delete** the state file (a presented batch never resumes).
   - **Budget hit, or any task `blocked` / `stuck`** → set `phase: halted` and **keep** it for resume; the printed package is the partial one.

The PR lands after the diffview pane on purpose: that pane is editable, so a PR opened before it would ship a body the human never got to amend.
