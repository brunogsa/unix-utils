# Batch-end review & tail subagents

Detail for /implement's batch-end review & tail subagents step. Load when the batch reaches its end.

This file owns the run order, plus the repo-green check, the two tails, and their triage. The package and the PR steps live in two sibling files, reached from here.

1. **Repo-green check** — full lint + tests, before the tails, so they analyze green code. *(below)*
2. **Deep-reviewer tail pair** — simplification lens + correctness lens, in parallel, report-only. *(below)*
3. **Triage both reports** — read both, synthesize one prioritized summary. *(below)*
4. **Metrics** — write `presented_at`, then run the metrics script (it needs `presented_at`). *(`batch-end-package.md`)*
5. **Assemble & print the package** — outcomes, diff range, metrics, worktree reminder; then open the diffview pane. *(`batch-end-package.md`)*
6. **Opt-in draft PR** — PR manifest entry and draft-PR dispatch. *(`batch-end-pr.md`; skipped entirely when neither a PR-label run nor an opted-in draft)*
7. **Finalize** — delete-or-keep the state file. *(`batch-end-package.md`)*

Read [`batch-end-package.md`](batch-end-package.md) as soon as triage is done — metrics, the package, and Finalize are not optional, and the batch is not over until Finalize sets the terminal phase.

## Repo-green check (before the tails)

Run this first, so the tails analyze green code. Run the repo's **full lint + full test suite** — not just the batch's files.

- **Cheap failures** (lint autofix, a trivial assertion update) → fix each in **its own commit**; list them under "Unexpected extras" in the package.
- **Structural failures** (a real design break, not a one-line fix) → auto-queue a `[Scout]` TaskList item per finding; do **not** fix them.
  - While any structural failure remains, the package explicitly flags **"repo not green"**.

This is the **only** auto-apply path at batch end. Tail findings are never applied here — the orchestrator triages them and you decide (below).

## The two tails

Full dispatch contract, preamble, failure handling, and overwrite policy: [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../../code-review-pipeline/references/deep-reviewer-tail-pair.md).

`<BASE_REF>` = `<BATCH_BASE_SHA>` (captured in §1.4); `<SPEC_PLAN_PATHS>` = the resolved `spec_<slug>.md`/`plan_<slug>.md`.

What's specific to `/implement`, not covered by the shared reference:

- Queue **two** batch-level TaskList items (NOT sub-steps of any single task), so they're visible in the batch's own TaskList:
  1. `[Side] Tail — deep-reviewer, simplification lens (report-only)`
  2. `[Side] Tail — deep-reviewer, correctness lens (report-only)`
- When each tail returns, confirm its report file exists at the assigned path, then record into the state file's `tails` object:
  - The report path — `refactor` → `.tails.refactor_report`, `auto-review` → `.tails.auto_review_report` (record the **path**, not the content — a resumed run reads it back to see which reports already exist).
  - Its token count → `.tails.tokens.<name>` (`0` if the Agent result omits it). The metrics script sums these into the subagent total.
- Mirror the same two fields into that tail's own TaskList `metadata` — `report_path` and `tokens` — via `TaskUpdate`, then flip its status to `completed`.
  The state file stays the resume source of truth; this metadata just lets a `TaskGet` on the tail task show its outcome without opening the state file.

## Triage both reports

Follow the shared reference's triage procedure: read both reports, synthesize one prioritized apply-offer summary. This synthesis is **additive** to the two raw report paths — the package carries **both**.

**Never fold a finding in on your own initiative** — see SKILL.md §9.4.
  - When the human names specific findings to apply after seeing the package, follow the shared reference's "Applying a single finding, on explicit request" — with one implement-specific routing choice:
    - This deliberately overrides the shared reference's generic routing (a single `general-purpose` subagent for every finding) — the reference's own note cross-links back here.
    - **A refactor-lens finding** (from `verdict_refactor_*.md`) → dispatch the **`refactor` agent** (Agent tool, `subagent_type=refactor` — its frontmatter pins model/effort, no override needed).
      Pass it the finding's scope and the caller's test command; it applies the change itself and confirms tests stay green before and after.
    - **An auto-review-lens finding** (from `verdict_auto-review_*.md`) → dispatch a fresh `tdd-coder` subagent (model omitted — its frontmatter pins sonnet) per the §4 contract with strict TDD (RED before GREEN), unchanged.
      The refactor agent refuses behavior changes, so a correctness fix can't route through it.
    - Verify the diff (§5.1) before trusting `done`, either way.

Once a fix lands, annotate its finding in the timestamped report file — `APPLIED` (with the fix commit SHA) or `SKIPPED` (with the reason).

The report is the durable, on-disk ledger of what got fixed versus deferred; this is the **only** report-file write the orchestrator itself makes.

