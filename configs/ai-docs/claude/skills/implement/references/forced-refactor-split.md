# Batch-end - split forced refactors out of the feature PR

Read this only from the first step of `batch-end-review.md`'s Finalize section (§8.4).

## When it runs

Only when `pr.wanted: true`, because the split needs an open PR to move commits out of.

- **Every run with no PR skips it**, which includes a default-branch run such as `unix-utils`, where forced refactors stay as commits in the batch and get no extra PR.

- **Say the skip in the package**, as the other skips do, so the human sees the split was not attempted.

## Why it runs first in §8.4

- §8.2's metrics fixes can add `Gate: metrics` commits too, so the split must see the final tree.

- It rewrites the feature branch, so it must come before the re-push that follows.

## Invocation

Run `scripts/split-forced-refactors.py` (next to this skill's `SKILL.md`) with these flags.

- `--repo` the repo root, `--base` `origin/<base>` (the PR's base branch) after `git fetch`, since a stale local base recounts already-merged `Gate: metrics` commits, `--feature-branch` the unit's branch.

  - `<base>` is the bare branch name, so a confirmed base of `origin/main` passes `origin/main`, never `origin/origin/main`.

- `--refactor-branch <feature-branch>-forced-refactor`, so the new branch name traces back to its feature branch.

- `--finding-out verdict_metrics-split_<branch>_<ts>.md` in CWD, with every `/` in `<branch>` replaced by `-` because a slash would name a missing subdirectory and crash the write, where a conflict writes its finding.

- `--plan <plan-file> --feature-pr <PR-N>` only on a PR-label run, because only then does the plan have a PR Breakdown for the script to extend.

  - The script then appends the refactor PR's entry and the feature PR's dependency on it.

The script does local git only and never pushes, so this run owns every push - permission prompts render only in the main session.

## Outcomes

Read `outcome` in the JSON.

- **`kept`** - nothing to do, because the forced refactors are under the size limit.

- **`moved`** - the commits now sit on the refactor branch and the feature branch was rebased.

  - Push every branch in `needs_push` with its own call, `git push origin <branch>`, adding `--force-with-lease` before `origin` where its `force_with_lease` is true.

  - One branch per call, because the git guard accepts `origin` plus a single branch name and refuses a bare `git push`.

  - Never use `--force`, which `configs/ai-docs/claude/hooks/claude-git-guard.sh` blocks and which can overwrite a remote change this run never saw.

  - That push replaces the next step's plain re-push for the feature branch.

  - A `moved` outcome always refreshes the feature PR description, whatever that step's `@{u}..HEAD` count says, because the force push leaves it at 0 while the moved commits left the PR.

  - Open the refactor branch's draft PR through the same `pr-creator` dispatch [`batch-end-pr.md`](batch-end-pr.md) owns.

  - Retarget the feature PR's base to the refactor branch, so its diff drops the moved commits: base rule in [`batch-end-pr.md`](batch-end-pr.md), REST retarget in [`stacked-prs.md`](stacked-prs.md).

  - Have the package list the moved commits and the new PR, so the human reviews what left the feature PR.

- **`conflict`** - the script aborted the cherry-pick or rebase (`conflict_operation` names it), so nothing moved and nothing needs a push.

  - List the finding file in the package for the human, because the commits stay in the feature PR until someone resolves it.

Any push failure is a §5.5 halt, on §8.1's terms, as the next step's push failure is.
