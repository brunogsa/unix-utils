---
# performance-check budget override, not batch-end content.
# This file merges what used to be two references, plus SKILL.md's own §8 condensed
# bullets, because every section fires on the same run — a split would only re-fragment
# one sequence across files always read together. SKILL.md's §8 now holds only the entry
# condition and a pointer here, so there's no redundancy against it. Doubled from the
# 1024w bundled default.
words-budget: 2048
---
# Batch-end — quality gate, repo-green, push, PR & package

Detail for /implement's batch-end steps. Load when the batch reaches its end.

SKILL.md's `§8.1 → §8.2 → §8.3` is the running order, and the only place that sequence is written down.
This file expands each of those steps; it never restates their order.

The branch record lives in [`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md) and the opt-in PR in [`batch-end-pr.md`](batch-end-pr.md), both reached from **Finalize** below, right after the push that Finalize always runs.
Skip whichever file doesn't match the run: the branch-record file only fires on a PR-label run, the PR file only on an opted-in draft.

## The quality-gate tail (§8.1)

**Entry: only when §1.2's quality-gate question was answered yes (`quality_gate.wanted: true`).**
On no, skip this entire section — go straight to the repo-green gate (§8.2), and have the package state that the quality gate was skipped by request.
No retroactive re-run; invoke `/quality-gate` manually later.

This runs before §8.2's repo-green gate so that gate gets the last word — it measures a tree that already contains whatever `--auto-solve` applied.
That ordering is what removes any "the gate applied something, so re-run the suite" rule: an applied fix is verified by construction, not by a conditional the run has to remember.

This section's toggle and §8.2's are independent — either can be on while the other is off.
When §8.2 is off, nothing re-runs the suite after this tail, and the package says so plainly.

**Invoke the skill in this session** — `/quality-gate [<spec>] <plan> --tasks <this unit's task-ids> --auto-solve`.

Pass the `<spec>` path only when §1.1 resolved one; a plan-only run passes just the plan and nothing else changes.
`/quality-gate` recognizes each path by its `spec_`/`plan_` filename prefix rather than by position, so the missing argument needs no placeholder.
Its `auto-review` leg then runs without spec-conformance context — that is its documented plan-only behavior, not a degraded invocation to work around.

Hand `<BATCH_BASE_SHA>` over as the base ref, instead of letting it resolve `origin/HEAD`.

Two reasons it runs here rather than inside a subagent:

- Its auto-solve commits the `refactor` agent's work itself, and a permission prompt only renders in the main session.
- Its three review legs are already fresh-context subagents, so wrapping it would spend one of the harness's three nesting levels on a layer that decides nothing.

`--auto-solve` is always passed: this run already asked its review questions in §1.2's interview, so a second prompt mid-batch would re-ask what the human answered.

`--tasks` scopes only the planned-test leg, to the task-ids of **this** unit. On a PR-label run that keeps PR-2's tail from reporting PR-3's unwritten tests as misses.

What `/quality-gate` owns, and this skill does not restate: the three verdict files, the triage call on which findings are addressable, the per-finding apply/commit/`[Done]` loop, and its closing report.

What this skill does with the result:

- Record each verdict file **path** into `.quality_gate.reports`, never its content.
  - The state file is the on-disk pointer the package reads back, not a copy of the report.

- Carry its closing report into the package (§8.3) verbatim enough that the human sees which findings landed, which were skipped, and why.
- Treat any finding it left unapplied as a `[Scout]`, so nothing it declined silently disappears.

With the tail behind it, set `phase: "tails"` — the resume path then knows the quality-gate tail already ran and must not run a second time.

The TaskList already carries this step as the `Batch-end 1/4` reminder seeded in §2.2 — flip that one entry. `/quality-gate` seeds its own per-finding entries underneath; don't duplicate them here.

## Repo-green GATE, fixed in a loop (§8.2)

**Entry: only when §1.2's repo-green-gate question was answered yes (`repo_green_gate.wanted: true`).**
On no, skip this entire section — go straight to Finalize (§8.3).
Have the package (§8.3) state the gate was skipped by request, with no repo-green result to show.

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

## The review package (§8.3)

The package is the single async pass the human reviews — the replacement for the per-task handshake. Finalize prints it (below). It contains:

A unit only ever reaches this package when every task is `[Done]`.
A unit that couldn't finish halted at §5.5 instead — or §8.2's own gate may halt the run before a package is ever assembled.
So there is exactly one package shape, never a partial one:

- **Per-task outcomes** — every task, all `done`, with its commit SHAs.
- **Dropped full-suite checks**, only when §8.2 was skipped by request.
  - Any plan-declared full-suite/repo-wide verification command §4.1 stripped from a task's dispatch and that the gate would otherwise have re-covered, named explicitly so the human knows it never ran this batch.

- **Every verdict file path** `/quality-gate` produced (`verdict_refactor_<ts>.md`, `verdict_auto-review_<ts>.md`, `verdict_test-sdd_<ts>.md`).
  - Plus any leg it flagged as failed.

- **The quality-gate outcome** — one line per finding, never a bare id or count, in the form `<lens>#N (<file>:<lines>) — <one-line recap>`, plus its outcome.
  - Outcome is applied (with its commit SHA), judged not addressable (with the reason), or failed to apply (with what it needs to retry).
  - The recap is what lets the human skip opening the verdict file.

- **Missing planned tests** — the `test-sdd` leg's misses that auto-solve did not write, called out on their own line rather than buried in the finding list.
  - A plan-declared test nobody wrote is the one gap this batch was supposed to close.

- **Every recorded `[Scout]` note**, pre-existing issues surfaced along the way (§4.3, §8.1, §8.2) — reported, never fixed by this run.
- **The literal diff range** — print `git diff BATCH_BASE_SHA..HEAD` with the actual SHA substituted, so the human can reproduce the range.
- **"Unexpected extras"** — the commits §8.2's fix-loop produced to reach green, each with its commit and the failure it fixed.
- **Repo-green result** — the final full-suite pass/fail + counts from §8.2, plus any `[Scout]` failures left unfixed because the batch didn't cause them.
  - When §8.2 was skipped by request, this bullet instead states plainly that no repo-green pass ran this batch.

- **Worktree merge-back reminder** — only when a worktree exists (read its path + branch from the state file); omit entirely when the interview declined it.
  - Its path, its branch, and "nothing was merged or deleted — merge back and remove it yourself".

## The review notification — the package's closing block

Printed last, after every other package section, so the human's eye lands on where to go review.
It is the pointer to the work, not a second summary of it — no findings, no counts beyond the commit count.

Print, in this order:

- **Review starts at `<BATCH_BASE_SHA>`** — its short SHA plus that commit's subject line, so the human recognizes it without a lookup.
  - On a single-unit run this is the commit the whole `/implement` invocation started from.
  - On a multi-PR run each unit prints its own base, which is the previous unit's tip — each notification covers only its own unit.

- **One line for the unit just finished**, carrying its label, its pushed branch, its commit count, and the PR URL when there is one:

```
PR-2 — branch `feat/parser/pr2` — 4 commits to review — https://github.com/<owner>/<repo>/pull/17
```

- The label is this unit's `<this-PR-label>`, or `this batch` on a plain `<task-ids>` run that has none.
- The count comes from `git rev-list --count <BATCH_BASE_SHA>..HEAD` — run it, never estimate it from the per-task outcomes.
- The URL appears only when Finalize's opt-in PR-creation step opened or updated a draft PR.
  - A push-only run ends the line at the commit count: the branch is on the remote, and reviewing means reading it there or locally.

## Finalize — the step order inside §8.3

By the time Finalize starts, both opt-in stages are behind it — whichever ran, ran, and the tree is final.

1. **Push the branch — always, on every batch end, regardless of `pr.wanted`.**
   Use `git push -u origin HEAD`, which covers both a fresh PR branch with no upstream and a plain run's branch that already has one.
   A pushed branch with no PR is this skill's ordinary outcome, not a half-finished state — it is what the notification points the human at.
   - **Any push failure is a [`failure-and-halt.md`](failure-and-halt.md) §5.5 halt** — no remote, a rejected non-fast-forward, missing credentials.
     - Name the failure, keep the state file, print nothing further. A notification pointing at a branch that never reached the remote is worse than a halt.

2. **Record the branch, then open the PR** — mechanics in [`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md) (branch record) and [`batch-end-pr.md`](batch-end-pr.md) (opt-in PR).
   The `Branch:` clause and the PR-level `[Done]` marker land on a PR-label run; the `pr-creator` dispatch runs only on `pr.wanted: true`.
   - Step 1 already pushed, so that dispatch creates the PR and must never push or force-push.
   - **Any failure there is a §5.5 halt too**, per that file's own closing rule.
   - Not requesting a PR (`pr.wanted: false`) is not a failure — proceed to step 3 with no PR outcome to report.

3. **Assemble the package** (contents under "The review package") and **print it** to chat, closing with the review notification.
   The single async review pass, reached only once the push — and the PR, when one was requested — succeeded.

4. **Finalize the phase.**
   Reaching this point means every task is `[Done]`, both opt-in stages ran or were declined, the branch is pushed, and the PR (if wanted) is open.
   Set `phase: "presented"` and **delete** the state file. The Stop hook releases on this phase; a presented batch is never resumed.

The PR is composed only after the quality-gate tail and the repo-green gate have both finished.
Its body describes the batch's actual final diff in one pass — never a pre-fix draft needing a second one.
