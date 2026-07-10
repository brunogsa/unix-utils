# Batch-end review & tail subagents

Detail for §9 in `/implement`. Load when the batch reaches its end.

The batch-end flow runs in this order:

1. **Repo-green check** — full lint + tests, before the tails, so they analyze green code.
2. **Two `deep-reviewer` tails** — `/refactor` then `/auto-review`, sequential, report-only.
3. **Triage both reports** — read both, synthesize one prioritized summary.
4. **Metrics** — write `presented_at`, then run the metrics script (it needs `presented_at`).
5. **Assemble & print the package** — outcomes, diff range, metrics, worktree reminder; then open the diffview pane.
6. **Opt-in draft PR, then finalize** — optional draft PR; then delete-or-keep the state file.

## Repo-green check (before the tails)

Run this first, so the tails analyze green code. Run the repo's **full lint + full test suite** — not just the batch's files.

- **Cheap failures** (lint autofix, a trivial assertion update) → fix each in **its own commit**; list them under "Unexpected extras" in the package.
- **Structural failures** (a real design break, not a one-line fix) → auto-queue a `[Scout]` TaskList item per finding; do **not** fix them.
  - While any structural failure remains, the package explicitly flags **"repo not green"**.

This is the **only** auto-apply path at batch end. Tail findings are never applied here — the orchestrator triages them and you decide (below).

## The two tails

Each tail reviews **only the batch's commit range** `<BATCH_BASE_SHA>..HEAD` (captured in §1.4), not the whole branch.

Queue **two** batch-level TaskList items (NOT sub-steps of any single task):

1. `[Side] Tail — /refactor over batch as deep-reviewer (report-only)`
2. `[Side] Tail — /auto-review over batch as deep-reviewer (report-only)`

Run them **sequentially**, in that order (refactor first so its findings can inform later passes). Both run once per `/implement` invocation regardless of batch size.

## Spawn contract

Spawn each tail via the **Agent tool**, `subagent_type=deep-reviewer`, in the background (the default) — wait for its completion notification before spawning the next, preserving the sequential order above.

`deep-reviewer` pins Opus + max effort by its own definition, so the dispatch site sets no `model` override.

The prompt body is the entire instruction set the subagent receives.

The prompt **must lead with this preamble verbatim**, line-for-line.

The subagent's compliance is what enforces the no-mutations contract — the harness blocks a `deep-reviewer`'s file writes, but its git/Bash mutations have no gate behind them:

```
REPORT-ONLY MODE — STRICT CONTRACT

You are spawned by /implement as an end-of-batch tail subagent. You produce
NO side effects — your complete findings ARE your final message.

YOU MUST NOT:
- Run `git commit`, `git push`, or any state-mutating git command.
- Use the Edit, Write, or MultiEdit tools on any file — including report
  files; the orchestrator persists your findings itself.
- Apply, fix, or suggest-and-then-apply any finding.
- Spawn nested subagents.

YOU MUST:
- Run the underlying skill (/refactor or /auto-review) in its
  analysis/findings phase only.
- Return the complete findings as your final message — every finding with
  file:line evidence, no summarizing or truncation.

Violating any of the MUST NOT items aborts the parent /implement.
```

After the preamble, include the skill-specific body:

- **refactor** tail: "Invoke `/refactor` over `<BATCH_BASE_SHA>..HEAD`. Return the complete findings as your final message."
  - Pass **no** spec/plan paths — refactor judges code shape, not spec conformance (deliberate).
- **auto-review** tail: "Invoke `/auto-review <BATCH_BASE_SHA>` (per its `/auto-review HEAD~N` per-task scoping convention). Return the complete findings as your final message."
  - Also pass the resolved `spec_<slug>.md` and `plan_<slug>.md` paths — auto-review always gets them to check spec conformance.

When each tail returns, the orchestrator persists its findings, then records the results into the state file's `tails` object:

- **The orchestrator writes the report file itself** — the tail's returned findings, verbatim, to `./report_refactor_<YYYY-MM-DD_HH:MM>.md` / `./report_auto-review_<YYYY-MM-DD_HH:MM>.md` in CWD.
  - The subagent can't write it: the harness routes a `deep-reviewer`'s output to text and blocks its file writes, so a subagent-side write silently never lands.
- The report path it wrote — `refactor` → `.tails.refactor_report`, `auto-review` → `.tails.auto_review_report`. The loop-state script emits the `present` verdict only once **both** paths are recorded.
- Its token count → `.tails.tokens.<name>` (`0` if the Agent result omits it). The metrics script sums these into the subagent total.

## Failure handling

- **Subagent violates the report-only contract** (a forbidden mutation per the preamble) → this **aborts the parent `/implement`**.
  - The harness blocks its file writes, but git/Bash mutations have no gate — for those the preamble's behavioral contract is the only enforcement.
- **Subagent errors, or returns no usable findings** → log it to chat with the agent's last message; the **other** tail still runs; the package flags the missing artifact.
  - A refactor failure never blocks the auto-review tail.
  - Do NOT retry inline (unlike the planned-test check): batch-end reports are reviewed asynchronously; a missing report is user-attention, not a retry loop.

## Overwrite policy

Each invocation produces timestamped filenames (`report_refactor_<ts>.md`, `report_auto-review_<ts>.md`), so multiple `/implement` runs in the same CWD accumulate as separate files.

The repo's existing `report_*.md` gitignore pattern covers both.

## Triage both reports

Both tails are report-only — neither applies anything. Once both reports are written, the orchestrator **triages** them before presenting:

- Read both reports in full.
- Synthesize **one** prioritized summary for the package: group findings by theme/severity, and recommend a disposition for each.
- Close with an actionable apply-offer — "tell me which to apply and I'll do it in a follow-up". The human decides asynchronously.

This synthesis is **additive** to the two raw report paths — it never replaces them. The package carries **both** the raw paths and the triaged summary.

## The review package

The package is the single async pass the human reviews — the replacement for the per-task handshake. Finalize prints it (below), after metrics. It contains:

- **Per-task outcomes** — each task labeled `done` / `blocked` / `stuck`, with its commit SHAs.
- **Both raw tail-report paths** (`report_refactor_<ts>.md`, `report_auto-review_<ts>.md`), plus any missing-report flag from failure handling.
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
- The command `cd`s into `<worktree-or-cwd>` first, so `DiffviewOpen` runs against the batch's working tree.
  - The pane inherits the orchestrator's cwd, which differs from the worktree when the interview chose one; without the `cd` the diff would open against the wrong tree.
- **Diff against the bare `<BATCH_BASE_SHA>`, never `<BATCH_BASE_SHA>..HEAD`** — the bare base compares base ⟷ working tree (right pane editable); `..HEAD` diffs two commits (both panes read-only).
- On a clean batch the working tree equals HEAD, so the editable view shows exactly the batch; edits land as uncommitted changes atop the batch commits.
- The skill handles the `$TMUX` guard itself: outside tmux it exits non-zero and prints the full `cd '<worktree-or-cwd>' && nvim -c 'DiffviewOpen <BATCH_BASE_SHA>'` command for the human to run.
- Requires the `diffview.nvim` plugin.

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

## Draft PR (opt-in)

Only when the interview opted into a draft PR (§1.2). Skip this section entirely otherwise.

- **Guard first** — if `gh` is absent or the repo has no remote, skip the PR with an explicit notice in the package; everything else in the package is unaffected.
- Otherwise **push the branch** and create a **draft** PR with `gh pr create --draft`. Never auto-merge, never force-push.
- Generate the description with a **separate `deep-reviewer` dispatch** from the spec/plan and commit bodies, following the `create-pr` skill's conventions (`~/.claude/skills/create-pr/SKILL.md`).
  - That dispatch **returns the description text only** — it must not push or commit; the orchestrator owns the push.
- Put completed Scout / repo-green fixes under an **"Unexpected extras"** section in the PR body.

## Finalize

This is the ordering spine. The print comes last of the review steps because the package must carry the metrics, and metrics needs `presented_at` — so stamp, compute, then print.

1. **Write `presented_at`** to the state file (the metrics script derives `duration_seconds` from `started_at`/`presented_at`).
2. **Run the metrics script** now that `presented_at` exists (see "Run metrics") and fold its totals into the package.
3. **Assemble the package** (contents under "The review package") and **print it** to chat — the single async review pass.
4. **Open the diffview pane** (see "Open the diff for review").
5. **Draft PR** if the interview opted in (see "Draft PR (opt-in)").
6. **Delete or keep the state file by terminal phase.** The phase set here is the Stop hook's release signal.
   - The hook blocks stops while phase is `tasks` / `gates` / `tails`, and allows them once phase is `presented` or `halted`.
   - **Every task `done`** → set `phase: presented` and **delete** the state file (a presented batch never resumes).
   - **Budget hit, or any task `blocked` / `stuck`** → set `phase: halted` and **keep** it for resume; the printed package is the partial one.
