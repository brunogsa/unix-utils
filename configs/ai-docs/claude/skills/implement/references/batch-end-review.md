---
# performance-check budget override, not batch-end content.
# This file merges what used to be two references, plus SKILL.md's own §8 condensed
# bullets, because every section fires on the same run — a split would only re-fragment
# one sequence across files always read together. Doubled from the 1024w bundled default.
words-budget: 2048
---
# Batch-end — push, PR, quality gate, repo-green & package

Detail for /implement's batch-end steps. Load when the batch reaches its end.

SKILL.md's `§8.1 → §8.2 → §8.3 → §8.4` is the running order and the only place it's written down; this file expands each step without restating it.

## Push, branch record & the draft PR (§8.1)

**Entry: unconditional — this is the first thing batch end does, before either gate.**

Delivered work reaches the remote before anything that can stall gets a turn — SKILL.md's §8 records the two audited batches that stranded commits when push sat behind a gate.

1. **Push the branch — always, on every batch end, regardless of `pr.wanted`.**
   Use `git push -u origin HEAD`, which covers both a fresh PR branch with no upstream and a plain run's branch that already has one.
   A pushed branch with no PR is this skill's ordinary outcome, not a half-finished state — what the notification points the human at.
   - **Any push failure is a [`failure-and-halt.md`](failure-and-halt.md) §5.5 halt** — no remote, a rejected non-fast-forward, missing credentials.
     - Name the failure, keep the state file, print nothing further. A notification pointing at an unpushed branch is worse than a halt.

2. **Record the branch, then open the draft PR** — mechanics in [`batch-end-pr-branch-record.md`](batch-end-pr-branch-record.md) and [`batch-end-pr.md`](batch-end-pr.md).
   The `Branch:` clause and the PR-level `[Done]` marker land on a PR-label run; the `pr-creator` dispatch runs only on `pr.wanted: true`.
   - Step 1 already pushed, so that dispatch creates the PR and must never push or force-push.
   - **Any failure there is a §5.5 halt too**, per that file's own closing rule.
   - Not requesting a PR (`pr.wanted: false`) is not a failure — proceed to §8.2 with no PR outcome to report.

`phase` stays `gates` throughout this section: `hooks/claude-implement-stop-hook.sh` blocks on `gates`, so publishing this early never lets the run end early.

## The quality-gate tail (§8.2)

**Entry: only when §1.2's quality-gate question was answered yes (`quality_gate.wanted: true`).**
On no, skip this entire section — go straight to the repo-green gate (§8.3), and have the package state the quality gate was skipped by request.
No retroactive re-run; invoke `/quality-gate` manually later.

This runs before §8.3's repo-green gate so that gate gets the last word — it measures a tree already carrying the `test-sdd` leg's written tests.

The `refactor` and `auto-review` legs are always report-only: their findings land as verdict files for the human to apply manually afterward, via `/address-verdicts`.

**Invoke the skill in this session** — `/quality-gate [<spec>] <plan> --tasks <this unit's task-ids> --base-ref <BATCH_BASE_SHA> --report-only`.

Pass the `<spec>` path only when §1.1 resolved one; `/quality-gate` recognizes each path by its `spec_`/`plan_` filename prefix rather than by position, so the missing argument needs no placeholder.

Its `auto-review` leg then runs without spec-conformance context — its documented plan-only behavior, not a degraded invocation to work around.

That `--base-ref` is what stops it resolving `origin/HEAD` and reviewing a range this batch never touched.

Two reasons it runs here rather than inside a subagent:

- Its `test-sdd` leg writes the plan's missing tests into the tree, and the permission prompt authorizing those writes only renders in the main session.
- Its three review legs are already fresh-context subagents, so wrapping it would spend one of the harness's three nesting levels on a layer that decides nothing.

**`--report-only` is always passed, never omitted.** It skips `/quality-gate`'s own opening interview.

Omit it, and `/quality-gate` asks the human a question this run already answered, stalling the batch on a prompt nobody is watching.

All three legs run regardless — the tail never skips one, it only never applies what they find.

`--tasks` scopes only the planned-test leg, to the task-ids of **this** unit. On a PR-label run that keeps PR-2's tail from reporting PR-3's unwritten tests as misses.

What `/quality-gate` owns, and this skill does not restate: the three verdict files, the triage call on which findings are addressable, the per-finding apply/commit/`[Done]` loop, and its closing report.

What this skill does with the result:

- Record each verdict file **path** into `.quality_gate.reports`, never its content.
  - The state file is the on-disk pointer the package reads back, not a copy of the report.

- Carry its closing report into the package (§8.4) verbatim enough that the human sees which findings landed, which were skipped, and why.
- Treat any finding it left unapplied as a `[Scout]`, so nothing it declined silently disappears.

With the tail behind it, set `phase: "tails"` — `hooks/claude-implement-stop-hook.sh` keeps blocking while the phase reads `tails`, so the run cannot end before Finalize.

The TaskList already carries this step as a `Batch-end` reminder seeded in §2.2 (only when `quality_gate.wanted`) — flip that one entry. `/quality-gate` seeds its own per-finding entries underneath; don't duplicate them here.

## Repo-green GATE, run by the repo-green-runner agent (§8.3)

**Entry: only when §1.2's repo-green-gate question was answered yes (`repo_green_gate.wanted: true`).**
On no, skip this entire section — go straight to Finalize (§8.4).
Have the package (§8.4) state the gate was skipped by request, with no repo-green result to show.

Dispatch ONE fresh-context `agent(subAgent=repo-green-runner, title=Repo-green gate)`, handing it `mode: gate`, the repo's full lint + full test commands repo-wide, and the state file's `baseline.failures` + `baseline.log_path`.

Same contract as §4 — background, its 1-hour `Monitor` cap, its `TaskStop`-on-expiry timeout path — with model omitted so the agent file's own pin applies.

That dispatch increments `gate_dispatches`, never `attempts[]` — those entries are task-keyed, and a repo-green failure has no task id.

`~/.claude/agents/repo-green-runner.md` owns everything inside the gate — classifying red, the per-failure fix loop and its 3-cycle budget, and the rule that pre-existing red is reported and never fixed.

Never hand-fix a failure the runner handed back.

**A gate run needs §1.6's baseline.** §1.2's single toggle makes a gate-without-baseline unreachable by construction — yes runs both, no runs neither.

This HALT still guards a baseline dispatch that itself halted or timed out, leaving both keys empty despite the toggle saying yes.

**What this section does with the verdict it gets back:**

- `GREEN` — proceed to Finalize (§8.4).
- `GREEN-WITH-EXCEPTIONS` — proceed to §8.4, carrying the runner's Scout list into the package as `[Scout]` notes, so nothing it declined to fix disappears.
- `HALT` — [`failure-and-halt.md`](failure-and-halt.md)'s §5.5, halt, with the runner's surviving red set named. The human clears it, not this run.

Then call `implement-loop-state.py --budget <state-file>`: `exhausted: true` on any verdict but `GREEN`/`GREEN-WITH-EXCEPTIONS` is a §5.5 halt too.

That budget is the outer bound over the whole run; the runner's own 3-cycle-per-signature budget is an inner one and never replaces it.

## The review package (§8.4)

The package is the single async pass the human reviews — the replacement for the per-task handshake. It contains:

A unit only reaches this package with every task `[Done]` — anything that couldn't finish halted at §5.5 instead, so there is exactly one package shape, never a partial one:

- **Per-task outcomes** — every task, all `done`, with its commit SHAs.
- **Dropped full-suite checks**, only when §8.3 was skipped by request.
  - Any plan-declared full-suite/repo-wide verification command §4.1 stripped from a task's dispatch and that the gate would otherwise have re-covered, so the human knows it never ran this batch.

- **Every verdict file path** `/quality-gate` produced (`verdict_refactor_<ts>.md`, `verdict_auto-review_<ts>.md`, `verdict_test-sdd_<ts>.md`).
  - Plus any leg it flagged as failed.

- **The quality-gate outcome** — one line per finding, never a bare id or count, in the form `<lens>#N (<file>:<lines>) — <one-line recap>`, plus its outcome.
  - Outcome is applied (with its commit SHA), judged not addressable (with the reason), or failed to apply (with what it needs to retry).
  - The recap is what lets the human skip opening the verdict file.

- **Missing planned tests** — the `test-sdd` leg's misses the tail did not manage to write, called out on their own line rather than buried in the finding list.
  - A plan-declared test nobody wrote is the one gap this batch was supposed to close, and the tail attempts every one of them on every run.

- **Every recorded `[Scout]` note**, pre-existing issues surfaced along the way (§4.3, §8.2, §8.3) — reported, never fixed by this run.
- **The literal diff range** — print `git diff BATCH_BASE_SHA..HEAD` with the SHA substituted, so the human can reproduce the range.
- **"Unexpected extras"** — §8.3's runner's Fixed list: each commit it produced to reach green, with the failure that commit closed.
- **Repo-green result** — §8.3's verdict, the runner's log path and final pass/fail + counts, and its Scout list of failures left unfixed because the batch didn't cause them.
  - When §8.3 was skipped by request, this bullet instead states plainly that no repo-green pass ran this batch.

- **Worktree merge-back reminder** — only when a worktree exists (read its path + branch from the state file); omit when the interview declined it.
  - Its path, its branch, and "nothing was merged or deleted — merge back and remove it yourself".

## The review notification — the package's closing block

Printed last, after every other package section, so the human knows where to review.
It is the pointer to the work, not a second summary of it — no findings, no counts beyond the commit count.

Print, in this order:

- **Review starts at `<BATCH_BASE_SHA>`** — its short SHA plus that commit's subject line, so the human recognizes it without a lookup.
  - On a multi-PR run each unit prints its own base, the previous unit's tip, so each notification covers only its own unit;
    - on a single-unit run it is where the invocation started.

- **One line for the unit just finished**, carrying its label, its pushed branch, its commit count, and the PR URL when there is one:

```
PR-2 — branch `feat/parser/pr2` — 4 commits to review — https://github.com/<owner>/<repo>/pull/17
```

- The label is this unit's `<this-PR-label>`, or `this batch` on a plain `<task-ids>` run that has none.
- The count comes from `git rev-list --count <BATCH_BASE_SHA>..HEAD` — run it, never estimate it from the per-task outcomes.
- The URL appears only when §8.1's opt-in PR-creation step opened or updated a draft PR.
  - A push-only run ends the line at the commit count: the branch is on the remote, and reviewing means reading it there or locally.

## Finalize — the step order inside §8.4

1. **Re-push and refresh the PR description — only when §8.2 or §8.3 landed commits.**
   Decide from the tree, not from memory: `git rev-list --count @{u}..HEAD` above zero is the trigger.
   - **Nothing landed → skip both halves outright.** Never re-push an unmoved branch, and never rewrite a description whose diff is unchanged.
     - Either no-op costs the reviewer a diff to discover it said nothing.

   - **Something landed → `git push` first**, so the remote carries the gate fixes before anything describes them.
     - Any push failure here is a §5.5 halt, on §8.1's terms.

   - **Then update the PR body**, only when `pr.wanted: true` and §8.1 opened one — via the `pr-creator` dispatch and REST-API path [`batch-end-pr.md`](batch-end-pr.md) owns.
     - The gate commits belong under its **"Unexpected extras"** section.

2. **Assemble the package** (contents under "The review package") and **print it** to chat, closing with the review notification.

3. **Finalize the phase.**
   Reaching this point means every task is `[Done]`, both opt-in gates ran or were declined, the branch is pushed, and the PR (if wanted) is open and described against the final diff.
   Set `phase: "presented"`, then dispose of the state file with `trash <state-file>`, never `rm` — it lives in `/tmp`, outside any git repo, the unrecoverable case `claude-rm-guard.sh` blocks `rm` on.
   The Stop hook releases on this phase; a presented batch is never resumed.
   - **`presented` is written here and nowhere earlier.**
     - Written before the gates, it would let a run stop with its gates unrun and its PR already open — the state §8.1's early push otherwise makes reachable.
