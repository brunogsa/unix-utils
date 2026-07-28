---
# performance-check budget override, not batch-end content.
# This file merges what used to be two references, plus SKILL.md's own §8 condensed
# bullets, because every section fires on the same run — a split would only re-fragment
# one sequence across files always read together. SKILL.md's §8 now holds only the entry
# condition and a pointer here, so there's no redundancy against it. Doubled from the
# 1024w bundled default.
words-budget: 2048
---
# Batch-end — repo-green, quality gate, PR & package

Detail for /implement's batch-end steps. Load when the batch reaches its end.

SKILL.md's `§8.1 → §8.2 → §8.3` is the running order, and the only place that sequence is written down.
This file expands each of those steps; it never restates their order.

The PR steps — manifest entry and opening the opt-in PR — live in [`batch-end-pr.md`](batch-end-pr.md), reached from **Finalize** below, once the quality-gate tail (§8.2) has landed whatever it's landing.
Skip that file entirely when the run is neither a PR-label run nor an opted-in draft.

## Repo-green GATE, fixed in a loop (§8.1)

**Entry: only when §1.2's repo-green-gate question was answered yes (`repo_green_gate.wanted: true`).**
On no, skip this entire section — go straight to the quality-gate tail (§8.2).
Have the package (§8.3) state the gate was skipped by request, with no repo-green result to show.

Run this first, so every reviewer analyzes green code.
Run the repo's **full lint + full test suite**, repo-wide — never scoped to the batch's own files, since a batch can break a workspace it never edited.

**Decide "pre-existing" from the baseline when one exists, judgment otherwise:**

- **`baseline.wanted: true` (§1.6 ran)** — a failure whose signature also appears in `baseline.failures` is pre-existing by evidence: record it as a `[Scout]`, citing the baseline log path.
  - A failure NOT in `baseline.failures` is batch-caused and must be fixed.

- **`baseline.wanted: false`** — no baseline was captured; fall back to judgment.
  - Reason about whether the batch's diff could plausibly have caused the failure (unrelated module, a test the batch's files never touch) and record it as `[Scout]` on that basis instead.

**Red repo → fix it in a loop, through subagents — the orchestrator never hand-fixes, and never scopes the gate down to make it pass:**

- Dispatch `agent(subAgent=tdd-coder, title=Fix repo-green failure: <short failure name>)` per batch-caused failure.
- Same contract as §4: the same 1-hour Monitor cap, the same per-task attempt caps, each dispatch recorded as an attempt in the state file.
- Re-run the **full** suite and lint after each fix, and read the fresh result — a fix nobody re-ran is a claim, not a green repo.

- Repeat until every failure the batch is responsible for is gone.

A failure classified `[Scout]` above is never fixed here: report it in the package, leave it unfixed, and let the gate pass on it.
Fixing pre-existing red would blur this batch's diff with unrelated work, which is exactly what the Scout channel (§4.3) exists to prevent.

Attempts exhausted with a batch-caused failure still red → [`failure-and-halt.md`](failure-and-halt.md)'s §5.5, halt. The human clears it; this run does not ship around it.

Record the final full-suite result (pass/fail + counts) into the package, so the human sees the gate actually ran over everything.

On a green gate, set `phase: "tails"` before moving on — the resume path then knows the loop and the gate are both behind it.

## The quality-gate tail (§8.2)

**Entry: only when §1.2's quality-gate question was answered yes (`quality_gate.wanted: true`).**
On no, skip this entire section — go straight to the PR branch and then Finalize (§8.3), and state there that the quality gate was skipped by request.
No retroactive re-run; invoke `/quality-gate` manually later.

§8.1's gate toggle and this section's toggle are independent — either can be on while the other is off.
When §8.1 ran, this dispatches only once it came back green; reviewing a diff about to change under a red repo wastes the pass.
When §8.1 was skipped by request, this runs immediately instead, and the package notes that no repo-green pass preceded it.

**Invoke the skill in this session** — `/quality-gate <spec> <plan> --tasks <this unit's task-ids> --auto-solve`, with `<BATCH_BASE_SHA>` handed over as the base ref instead of letting it resolve `origin/HEAD`.

Two reasons it runs here rather than inside a subagent:

- Its auto-solve commits the `refactor` agent's work itself, and a permission prompt only renders in the main session.
- Its three review legs are already fresh-context subagents, so wrapping it would spend the harness's one nesting level on a layer that decides nothing.

`--auto-solve` is always passed: this run already asked its review questions in §1.2's interview, so a second prompt mid-batch would re-ask what the human answered.

`--tasks` scopes only the planned-test leg, to the task-ids of **this** unit. On a PR-label run that keeps PR-2's tail from reporting PR-3's unwritten tests as misses.

What `/quality-gate` owns, and this skill does not restate: the three verdict files, the triage call on which findings are addressable, the per-finding apply/commit/`[Done]` loop, and its closing report.

What this skill does with the result:

- Record each verdict file **path** into `.quality_gate.reports`, never its content.
  - The state file is the on-disk pointer the package reads back, not a copy of the report.

- Carry its closing report into the package (§8.3) verbatim enough that the human sees which findings landed, which were skipped, and why.
- Treat any finding it left unapplied as a `[Scout]`, so nothing it declined silently disappears.

- **If it applied anything, re-run §8.1's full suite + lint before the PR dispatches** — a fix nobody re-ran is a claim, not a green repo.
  - Nothing applied → skip the re-run and say so in the package.

The TaskList already carries this step as the `Batch-end 2/4` reminder seeded in §2.2 — flip that one entry. `/quality-gate` seeds its own per-finding entries underneath; don't duplicate them here.

## The review package (§8.3)

The package is the single async pass the human reviews — the replacement for the per-task handshake. Finalize prints it (below). It contains:

A unit only ever reaches this package when every task is `[Done]`.
A unit that couldn't finish halted at §5.5 instead — or §8.1's own gate may halt the run before a package is ever assembled.
So there is exactly one package shape, never a partial one:

- **Per-task outcomes** — every task, all `done`, with its commit SHAs.
- **Dropped full-suite checks**, only when §8.1 was skipped by request.
  - Any plan-declared full-suite/repo-wide verification command §4.1 stripped from a task's dispatch and that the gate would otherwise have re-covered, named explicitly so the human knows it never ran this batch.

- **Every verdict file path** `/quality-gate` produced (`verdict_refactor_<ts>.md`, `verdict_auto-review_<ts>.md`, `verdict_test-sdd_<ts>.md`).
  - Plus any leg it flagged as failed.

- **The quality-gate outcome** — one line per finding: applied (with its commit SHA), judged not addressable (with the reason), or failed to apply (with what it needs to retry).
  - State plainly whether §8.1 was re-run because something was applied.

- **Missing planned tests** — the `test-sdd` leg's misses that auto-solve did not write, called out on their own line rather than buried in the finding list.
  - A plan-declared test nobody wrote is the one gap this batch was supposed to close.

- **Every recorded `[Scout]` note**, pre-existing issues surfaced along the way (§4.3, §8.1, §8.2) — reported, never fixed by this run.
- **The literal diff range** — print `git diff BATCH_BASE_SHA..HEAD` with the actual SHA substituted, so the human can reproduce the range.
- **"Unexpected extras"** — the commits §8.1's fix-loop produced to reach green, each with its commit and the failure it fixed.
- **Repo-green result** — the final full-suite pass/fail + counts from §8.1, plus any `[Scout]` failures left unfixed because the batch didn't cause them.
  - When §8.1 was skipped by request, this bullet instead states plainly that no repo-green pass ran this batch.

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

## Finalize — the step order inside §8.3

By the time Finalize starts, the quality-gate tail (§8.2) has already finished — Finalize's first job is to dispatch the PR branch, not to join anything.

1. **Dispatch the PR branch** (`pr.wanted: true` only) — manifest entry + `pr-creator`, mechanics in [`batch-end-pr.md`](batch-end-pr.md).
   By now the quality gate has applied whatever it applied and (if it applied anything) §8.1 has been re-run green, so the PR describes the batch's actual final diff in one pass.
   - **Any failure here is a [`failure-and-halt.md`](failure-and-halt.md) §5.5 halt, not a partial package.**
     - No `gh`, no remote, a rejected push, or a create that errored all route there — name the failure, keep the state file, print nothing.

   - Not requesting a PR (`pr.wanted: false`) is not a failure — proceed to step 2 with no PR outcome to report.

2. **Assemble the package** (contents under "The review package") and **print it** to chat.
   The single async review pass, reached only once the PR branch succeeded (or was never requested).

3. **Open the diffview pane** (see "Open the diff for review").
4. **Finalize the phase.**
   Reaching this point means every task is `[Done]`, the quality gate has run (or was declined), and the PR (if wanted) is open — the only outcome left.
   Set `phase: "presented"` and **delete** the state file. The Stop hook releases on this phase; a presented batch is never resumed.

The package is presented only once the run actually succeeded — on a PR-wanted run, "succeeded" includes the PR being open.
The PR is composed only after the quality-gate tail has finished, never before it.
