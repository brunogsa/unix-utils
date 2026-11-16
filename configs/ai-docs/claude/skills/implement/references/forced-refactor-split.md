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

- `--repo` the repo root, `--base` the PR's base branch, `--feature-branch` the unit's branch.

- `--refactor-branch <feature-branch>-forced-refactor`, so the new branch name traces back to its feature branch.

- `--finding-out verdict_metrics-split_<branch>_<ts>.md` in CWD, where a conflict writes its finding.

- `--plan <plan-file> --feature-pr <PR-N>` only on a PR-label run, because only then does the plan have a PR Breakdown for the script to extend.

  - The script then appends the refactor PR's entry and the feature PR's dependency on it.

The script does local git only and never pushes, so this run owns every push - permission prompts render only in the main session.

## Outcomes

Read `outcome` in the JSON.

- **`kept`** - nothing to do, because the forced refactors are under the size limit.

- **`moved`** - the commits now sit on the refactor branch and the feature branch was rebased.

  - Push every branch in `needs_push` with `git push --force-with-lease`, never `--force`, which `configs/ai-docs/claude/hooks/claude-git-guard.sh` blocks and which can overwrite a remote change this run never saw.

  - That push replaces the next step's plain re-push for the feature branch.

  - Open the refactor branch's draft PR through the same `pr-creator` dispatch [`batch-end-pr.md`](batch-end-pr.md) owns.

  - Have the package list the moved commits and the new PR, so the human reviews what left the feature PR.

- **`conflict`** - the script aborted the cherry-pick or rebase (`conflict_operation` names it), so nothing moved and nothing needs a push.

  - List the finding file in the package for the human, because the commits stay in the feature PR until someone resolves it.

Any push failure is a §5.5 halt, on §8.1's terms, as the next step's push failure is.
