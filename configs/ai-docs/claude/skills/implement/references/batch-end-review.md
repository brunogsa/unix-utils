---
# performance-check budget override, not batch-end content.
# This file merges what used to be two references, because every section fires on the same
# run — a split would only re-fragment one sequence across two files always read together.
# It carries no redundancy against SKILL.md's batch-end steps — only the per-step detail
# those steps point at. Doubled from the 1024w bundled default.
words-budget: 2048
---
# Batch-end — repo-green, tails, triage, package & finalize

Detail for /implement's batch-end steps. Load when the batch reaches its end.

SKILL.md's `§9.1 → (§9.2 ∥ §9.3) → §9.4 → §9.5` is the running order, and the only place that sequence is written down.
This file expands each of those steps; it never restates their order.

The PR steps — manifest entry and opening the opt-in PR — live in [`batch-end-pr.md`](batch-end-pr.md), reached from Finalize below.
Skip that file entirely when the run is neither a PR-label run nor an opted-in draft.

## Repo-green GATE, fixed in a loop (§9.1)

Run this first, so the tails analyze green code.
Run the repo's **full lint + full test suite**, repo-wide — never scoped to the batch's own files, since a batch can break a workspace it never edited.

**Red repo → fix it in a loop, through subagents — the orchestrator never hand-fixes, and never scopes the gate down to make it pass:**

- Dispatch `agent(subAgent=tdd-coder, title=Fix repo-green failure: <short failure name>)` per failure.
- Same contract as §4: the same 1-hour Monitor cap, the same per-task attempt caps, each dispatch recorded as an attempt in the state file.
- Re-run the **full** suite and lint after each fix, and read the fresh result — a fix nobody re-ran is a claim, not a green repo.
- Repeat until every failure the batch is responsible for is gone.

**A failure the batch did not cause is a `[Scout]`, not a blocker.** Record it, report it in the package, leave it unfixed, and let the gate pass on it.
Fixing pre-existing red would blur this batch's diff with unrelated work, which is exactly what the Scout channel (§4.3) exists to prevent.

Attempts exhausted with a batch-caused failure still red → §5.5, halt. The human clears it; this run does not ship around it.

Record the final full-suite result (pass/fail + counts) into the package, so the human sees the gate actually ran over everything.

This is the **only** auto-apply path at batch end. Tail findings (§9.2–§9.4) are never applied — not here, not anywhere in this run (see Triage below).

## The two tails (§9.2–§9.3)

Full dispatch contract, preamble, failure handling, and overwrite policy: [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../../code-review-pipeline/references/deep-reviewer-tail-pair.md).

`<BASE_REF>` = `<BATCH_BASE_SHA>` (captured in §3.2); `<SPEC_PLAN_PATHS>` = the resolved spec and plan.

What's specific to `/implement`:

- The TaskList already carries this step as the `Batch-end 3/5` reminder seeded in §2.2 — flip that one entry, and don't queue a separate item per tail.
- When a tail returns, confirm its report file exists at the assigned path, then record that **path** into `.tails.refactor_report` / `.tails.auto_review_report`.
  - Record the path, never the content: the state file is only the on-disk pointer that Triage (§9.4) and the package read back, not a copy of the report.

## Triage both reports (§9.4)

Read both reports and synthesize one prioritized summary into the package: every finding, including the ones that look low-risk, each pointing at the report file that carries its full text.
This synthesis is **additive** to the two raw report paths — the package carries **both**.

**This skill never applies a finding — not one, not a trivial one, not on request.** Triage here is report-only, end to end, with no exceptions and no opt-in.

The apply-a-finding path is removed entirely, not softened into an opt-in: deciding and applying a finding is a separate, human-initiated pass over the verdict files, started after this run ends.

Keeping apply out of the batch means the diff the human is about to review stays exactly the diff the tails reviewed.
Folding fixes in after the fact would silently invalidate both reports and the repo-green result the package just claimed.

## The review package (§9.5)

The package is the single async pass the human reviews — the replacement for the per-task handshake. Finalize prints it (below). It contains:

A unit only ever reaches this package when every task is `[Done]` and §8's gate passed.
A unit that couldn't finish halted at §5.5 instead — or §9.1's own gate may halt the run before a package is ever assembled.
So there is exactly one package shape, never a partial one:

- **Per-task outcomes** — every task, all `done`, with its commit SHAs.
- **Both raw tail-report paths** (`verdict_refactor_<ts>.md`, `verdict_auto-review_<ts>.md`), plus any missing-report flag from failure handling.
- **The triaged synthesis** (above) — findings only, never an apply-offer.
- **Every recorded `[Scout]` note**, pre-existing issues surfaced along the way (§4.3, §9.1) — reported, never fixed by this run.
- **The literal diff range** — print `git diff BATCH_BASE_SHA..HEAD` with the actual SHA substituted, so the human can reproduce the range.
- **"Unexpected extras"** — the commits §9.1's fix-loop produced to reach green, each with its commit and the failure it fixed.
- **Repo-green result** — the final full-suite pass/fail + counts from §9.1, plus any `[Scout]` failures left unfixed because the batch didn't cause them.
- **TDD opt-out note** — when §8's gate passed as all-N/A, state the explicit opt-out.
- **Worktree merge-back reminder** — only when a worktree exists (read its path + branch from the state file); omit entirely when the interview declined it.
  - The reminder ends the package: its path, its branch, and "nothing was merged or deleted — merge back and remove it yourself".

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

## Finalize — the step order inside §9.5

Each step presupposes the one before it succeeded; the package is never printed over a PR that failed to open.

1. **PR manifest entry & PR-level status marker**, on a PR-label run (see [`batch-end-pr.md`](batch-end-pr.md)).
2. **Open the PR**, only when the interview opted in (`pr.wanted: true`) — see [`batch-end-pr.md`](batch-end-pr.md)'s "Open the PR (opt-in)".
   - **Failing here is a §5.5 halt, not a partial package.** No `gh`, no remote, a rejected push, or a create that errored all route to §5.5.
   - Name the failure, keep the state file, print nothing.
   - Not requesting a PR (`pr.wanted: false`) is not a failure — step 3 proceeds normally.
3. **Assemble the package** (contents under "The review package") and **print it** to chat — the single async review pass, reached only once step 2 succeeded or was never requested.
4. **Open the diffview pane** (see "Open the diff for review").
5. **Finalize the phase.** Reaching this point means every task is `[Done]`, the gate passed, and the PR (if wanted) is open — the only outcome left.
   Set `phase: "presented"` and **delete** the state file. The Stop hook releases on this phase; a presented batch is never resumed.

The PR lands **before** the package and the diffview pane on purpose: the package is presented only once the run actually succeeded.
On a PR-wanted run, "succeeded" includes the PR being open — printing the package first would risk showing success for a PR that never got created.
