# Batch-end review & tail subagents

Detail for /implement's batch-end review & tail subagents step. Load when the batch reaches its end.

The batch-end flow runs in this order:

1. **Repo-green check** — full lint + tests, before the tails, so they analyze green code.
2. **Deep-reviewer tail pair** — simplification lens + correctness lens, in parallel, report-only.
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

Full dispatch contract, preamble, failure handling, and overwrite policy: [`code-review-pipeline/references/deep-reviewer-tail-pair.md`](../../code-review-pipeline/references/deep-reviewer-tail-pair.md).

`<BASE_REF>` = `<BATCH_BASE_SHA>` (captured in §1.4); `<SPEC_PLAN_PATHS>` = the resolved `spec_<slug>.md`/`plan_<slug>.md`.

What's specific to `/implement`, not covered by the shared reference:

- Queue **two** batch-level TaskList items (NOT sub-steps of any single task), so they're visible in the batch's own TaskList:
  1. `[Side] Tail — deep-reviewer, simplification lens (report-only)`
  2. `[Side] Tail — deep-reviewer, correctness lens (report-only)`
- When each tail returns, confirm its report file exists at the assigned path, then record into the state file's `tails` object:
  - The report path — `refactor` → `.tails.refactor_report`, `auto-review` → `.tails.auto_review_report` (record the **path**, not the content — a resumed run reads it back to see which reports already exist).
  - Its token count → `.tails.tokens.<name>` (`0` if the Agent result omits it). The metrics script sums these into the subagent total.

## Triage both reports

Follow the shared reference's triage procedure: read both reports, synthesize one prioritized apply-offer summary. This synthesis is **additive** to the two raw report paths — the package carries **both**.

**Never fold a finding in on your own initiative** — see SKILL.md §9.4.
  - When the human names specific findings to apply after seeing the package, follow the shared reference's "Applying a single finding, on explicit request".
    - Dispatch a fresh `general-purpose` subagent on `model=sonnet` per the §4 contract with strict TDD (RED before GREEN).
    - Verify the diff (§5.1) before trusting `done`.

Once a fix lands, annotate its finding in the timestamped report file — `APPLIED` (with the fix commit SHA) or `SKIPPED` (with the reason).

The report is the durable, on-disk ledger of what got fixed versus deferred; this is the **only** report-file write the orchestrator itself makes.

## The review package

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

## PR manifest entry & PR-level status marker (PR-label runs only)

Skip this whole section on a plain `<task-ids>` run (no `PR-N` label, `pr_label` is `""`).

- **Manifest entry** — record this PR's own branch, once, regardless of terminal outcome:
  ```bash
  ~/.claude/skills/implement/scripts/append-branch-pr-entry.sh <worktree-path>/branches_<slug>.md <slug> <this-PR-label> <this-PR-branch>
  ```
  `<this-PR-branch>` is `git branch --show-current` right now. See `references/pr-awareness.md`'s "Manifest writes" for why this write belongs here and not at branch creation.
- **PR-level status marker** — on a fully **`[Done]`** batch only (every task `[Done]`, repo-green gate passed), update this PR's own line in the plan's PR Breakdown.
  This mirrors §6's task-level marker convention one level up:
  ```
  N. **[Done] PR-N** — <theme>. Tasks: <N, N>. Depends on: <none | PR-N>.
  ```
  Write it inline, in the same edit style as a task-level marker — never scripted.
  A halted batch (any task `blocked`/`stuck`, or the gate failed) leaves the PR Breakdown line **unmarked**.
  Resuming re-evaluates it, so a partial PR must never read as `[Done]`.

## Draft PR (opt-in)

Only when the interview opted into a draft PR (§1.2). Skip this section entirely otherwise.

- **Guard first** — if `gh` is absent or the repo has no remote, skip the PR with an explicit notice in the package; everything else in the package is unaffected.
- Otherwise **push the branch** and create a **draft** PR with `gh pr create --draft --body-file <file> --base <base-branch>`, where `<base-branch>` is §1.2's confirmed base branch. Never auto-merge, never force-push.
  - Every PR-label run needs this `--base`, dependent or not.
    Without it, `gh pr create` falls back to `branch.<name>.gh-merge-base` or the repo's default branch — never to a parent's branch by any ancestry heuristic.
    That fallback is implicit, not the plan's explicitly confirmed choice.
  - **This branch already has an open PR** (`gh pr create` errors that a PR already exists) → not a failure.
    Fall back to the same REST-API body-update path below, targeting that existing PR number.
    A resumed batch updates its own already-open PR instead of erroring.
  - **Updating an existing PR's body: use the REST API, never `gh pr edit --body-file`** — `gh api --method PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`.
    - `gh pr edit` eagerly queries Projects-classic `projectCards`; on repos where classic Projects is sunset it errors on that query and the write silently doesn't land.
    - The REST endpoint touches no Projects data.
    - Read the body back afterward to confirm it landed.
- Generate the description with a **separate `general-purpose` subagent dispatch** (`model=sonnet` — composition, not review) from the spec/plan and commit bodies, following the `create-pr` skill's conventions (`~/.claude/skills/create-pr/SKILL.md`) for structure and tone only.
  - Never dispatch `deep-reviewer` for this: its write-guard hook allows only `verdict_*.md` and `/tmp` writes, and denies a `pr-descr_*.md` write in CWD outright.
  - Never invoke `create-pr` itself for this — its own step 3 is an interactive approval gate, incompatible with this fully-async flow.
  - It fills `.github/PULL_REQUEST_TEMPLATE.md`, embeds mermaid blocks, and includes the mandatory Testable-Acceptance-Criteria + Evidences sections a hand-written body silently omits.
  - Carry any manual deploy prerequisites (new secrets, new Parameter-Store values) into the description as `WARNING:`-prefixed items.
  - Pass the resolved `<this-PR-label>` explicitly in the dispatch prompt, so the subagent writes one PR's description, never asks which PR it covers.
    The CWD may hold several spec/plan pairs, and a PR-label run may cover several PRs, so an unstated label binds to the wrong one.
  - Assign its output path explicitly: `./pr-descr_<slug>_<this-PR-label-lowercase>.md` (e.g. `pr-descr_multi-pr-implement_pr2.md`) — the subagent writes that file directly; the orchestrator then reads it for `--body-file`.
  - It must not push or commit — the orchestrator owns the push.
  - Its tokens are **not tracked**: metrics print before this step, and a presented run's state file is deleted right after — so don't add a `tokens` field for it.
- Put completed Scout / repo-green fixes under an **"Unexpected extras"** section in the PR body.

## Finalize

This is the ordering spine. The print comes last of the review steps because the package must carry the metrics, and metrics needs `presented_at` — so stamp, compute, then print.

1. **Write `presented_at`** to the state file (the metrics script derives `duration_seconds` from `started_at`/`presented_at`).
2. **Run the metrics script** now that `presented_at` exists (see "Run metrics") and fold its totals into the package.
3. **Assemble the package** (contents under "The review package") and **print it** to chat — the single async review pass.
4. **Open the diffview pane** (see "Open the diff for review").
5. **PR manifest entry & status marker**, on a PR-label run (see above).
6. **Draft PR** if the interview opted in (see "Draft PR (opt-in)").
7. **Delete or keep the state file by terminal phase.** The phase set here is the Stop hook's release signal.
   - The hook blocks stops while phase is `tasks` / `gates` / `tails`, and allows them once phase is `presented` or `halted`.
   - **Every task `done`** → set `phase: presented` and **delete** the state file (a presented batch never resumes).
   - **Budget hit, or any task `blocked` / `stuck`** → set `phase: halted` and **keep** it for resume; the printed package is the partial one.
