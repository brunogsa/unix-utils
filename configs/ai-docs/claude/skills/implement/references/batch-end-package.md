# Batch-end — package, diffview, metrics & finalize

The second half of the batch-end flow. Read it once the tails have returned and been triaged — [`batch-end-review.md`](batch-end-review.md) owns the run order and the steps before this point.

The opt-in draft PR runs between "Run metrics" and "Finalize" below; it lives in [`batch-end-pr.md`](batch-end-pr.md).

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
