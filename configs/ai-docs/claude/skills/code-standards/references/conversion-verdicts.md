# Conversion verdicts — classify-conversion.py swept across both repos

This is the committed input Tasks 16-20 of `plan_script-overhaul.md` scope
their conversion batches from. Every row is exactly what
`classify-conversion.py` returned; nothing here was hand-adjusted.

## How this was generated

```bash
python3 configs/ai-docs/claude/skills/code-standards/scripts/classify-conversion.py \
  --tree ~/unix-utils --tree ~/oh-my-zsh
```

Exit code 0, no crash, on both trees.

## Snapshot provenance

`unix-utils` HEAD at capture time: `96fd600bef36a06a4f9b5818f79ba1f5ce300618`.

A second Claude Code session commits to this same working tree roughly
once a minute (see `plan_script-overhaul.md`'s concurrency protocol), so
this table is a point-in-time snapshot, not a value the classifier will
reproduce byte-for-byte on a later run. Four of the files below
(`claude-compact-skill-reload.sh`, `claude-tmux-title-compact-reminder.sh`,
`claude-tmux-title-reminder.sh`, `tmux-window-title.sh`, and their four new
paired `test-*.sh` files) were mid-edit or newly-added and uncommitted
in that session at capture time.

## Summary

| Repo | Total `.sh` files | Excluded | `convert` | `stays-sh` |
|---|---|---|---|---|
| `unix-utils` (real tree, excludes the stale `worktrees/stacked-prs-pr2` duplicate) | 99 | 1 (`install.sh`) | 87 | 11 |
| `oh-my-zsh` | 29 | 1 (`install.sh`) | 9 | 19 |

`unix-utils` also has 54 files under the stale `.claude/worktrees/stacked-prs-pr2`
duplicate worktree (53 excluded by the `STALE_WORKTREE_MARKER` rule, plus
that worktree's own `install.sh` excluded by the `install.sh` rule first).
None of those 54 are listed below — they are a byte-for-byte duplicate of
a worktree, not scripts anyone edits, and the classifier already routes
every one of them out at the first check.

Every `convert` verdict below targets `py` — no script in either repo
carries a `Requires-npm` header, so none opted into `js`.

## `unix-utils` — 98 non-excluded scripts

| Path | Verdict | Target | Triggering reason |
|---|---|---|---|
| `configs/ai-docs/claude/hooks/claude-agent-contract-stop-hook.sh` | convert | py | awk+jq; 156 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-comment-format-stop-hook.sh` | convert | py | awk+jq; 270 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-compact-skill-reload.sh` | convert | py | jq+sed -E+here-doc |
| `configs/ai-docs/claude/hooks/claude-explore-mandate-hook.sh` | convert | py | awk+jq+here-doc |
| `configs/ai-docs/claude/hooks/claude-git-guard.sh` | stays-sh | py | per-call hook exemption (fires every tool call) |
| `configs/ai-docs/claude/hooks/claude-implement-compact-reminder.sh` | convert | py | jq+here-doc; 188 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-implement-stop-hook.sh` | convert | py | jq; 159 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-markdown-standards-stop-hook.sh` | convert | py | awk+jq; 282 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-rm-guard.sh` | stays-sh | py | per-call hook exemption (fires every tool call) |
| `configs/ai-docs/claude/hooks/claude-sdd-stop-hook.sh` | convert | py | jq |
| `configs/ai-docs/claude/hooks/claude-stop-orchestrator.sh` | convert | py | jq; 197 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-stopfailure-resume.sh` | convert | py | jq; 193 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-tmux-notification.sh` | convert | py | jq; 174 lines (>128) |
| `configs/ai-docs/claude/hooks/claude-tmux-title-compact-reminder.sh` | convert | py | jq+here-doc |
| `configs/ai-docs/claude/hooks/claude-tmux-title-reminder.sh` | convert | py | jq+here-doc |
| `configs/ai-docs/claude/hooks/claude-tmux-title-restore.sh` | convert | py | jq |
| `configs/ai-docs/claude/hooks/deep-reviewer-write-guard.sh` | stays-sh | py | per-call hook exemption (fires every tool call) |
| `configs/ai-docs/claude/hooks/tests/test-claude-agent-contract-stop-hook.sh` | convert | py | jq; 167 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-comment-format-stop-hook.sh` | convert | py | jq; 255 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-compact-skill-reload.sh` | convert | py | jq |
| `configs/ai-docs/claude/hooks/tests/test-claude-explore-mandate-hook.sh` | convert | py | jq; 177 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-git-guard.sh` | convert | py | jq+here-doc; 142 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-implement-compact-reminder.sh` | convert | py | jq+here-doc; 313 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-implement-stop-hook.sh` | convert | py | jq; 248 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-rm-guard.sh` | convert | py | jq+here-doc; 210 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-stop-orchestrator.sh` | convert | py | jq+here-doc; 217 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-stopfailure-resume.sh` | convert | py | awk+here-doc; 296 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-tmux-compact-bump.sh` | convert | py | here-doc; 153 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-claude-tmux-title-compact-reminder.sh` | convert | py | jq |
| `configs/ai-docs/claude/hooks/tests/test-subagent-disallowed-tools-guard.sh` | convert | py | jq+here-doc; 156 lines (>128) |
| `configs/ai-docs/claude/hooks/tests/test-subagent-model-guard.sh` | convert | py | jq+here-doc |
| `configs/ai-docs/claude/scripts/resolve-base-ref.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/scripts/statusline-tier.sh` | convert | py | awk+jq+here-doc; 827 lines (>128) |
| `configs/ai-docs/claude/scripts/tests/test-resolve-base-ref.sh` | convert | py | 157 lines (>128) |
| `configs/ai-docs/claude/scripts/tests/test-statusline-tier.sh` | convert | py | awk+jq+sed -E+here-doc; 2164 lines (>128) |
| `configs/ai-docs/claude/scripts/tests/test-tmux-window-title.sh` | convert | py | 742 lines (>128) |
| `configs/ai-docs/claude/scripts/tmux-window-title.sh` | convert | py | awk+sed -E; 526 lines (>128) |
| `configs/ai-docs/claude/skills/agent-standards/scripts/check-agent-contract.sh` | convert | py | awk; 252 lines (>128) |
| `configs/ai-docs/claude/skills/agent-standards/scripts/tests/test-check-agent-contract.sh` | convert | py | here-doc; 778 lines (>128) |
| `configs/ai-docs/claude/skills/code-review-pipeline/scripts/extract-commentable-lines.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/code-review-pipeline/scripts/extract-skipped-files.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/code-review-pipeline/scripts/filter-off-diff-findings.sh` | convert | py | jq |
| `configs/ai-docs/claude/skills/consistency-check-principles-and-skills/scripts/check-refs.sh` | convert | py | sed -E; 288 lines (>128) |
| `configs/ai-docs/claude/skills/consistency-check-principles-and-skills/scripts/gen-shard-manifest.sh` | convert | py | awk+here-doc; 323 lines (>128) |
| `configs/ai-docs/claude/skills/consistency-check-principles-and-skills/scripts/tests/test-check-refs.sh` | convert | py | 275 lines (>128) |
| `configs/ai-docs/claude/skills/consistency-check-principles-and-skills/scripts/tests/test-gen-shard-manifest.sh` | convert | py | awk+here-doc; 522 lines (>128) |
| `configs/ai-docs/claude/skills/consistency-check-principles-and-skills/scripts/tests/test-verify-quote.sh` | convert | py | here-doc; 182 lines (>128) |
| `configs/ai-docs/claude/skills/consistency-check-principles-and-skills/scripts/verify-quote.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/skills/create-pr/scripts/check-pr-body-size.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/create-pr/scripts/check-pr-page-fit.sh` | convert | py | awk+sed -E; 245 lines (>128) |
| `configs/ai-docs/claude/skills/create-pr/scripts/extract-md-sections.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/create-pr/scripts/extract-mermaid-blocks.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/doc-standards/scripts/check-density.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/doc-standards/scripts/tests/test-check-bullet-gap-fix.sh` | convert | py | here-doc; 131 lines (>128) |
| `configs/ai-docs/claude/skills/doc-standards/scripts/tests/test-check-comment-format.sh` | convert | py | awk+here-doc; 296 lines (>128) |
| `configs/ai-docs/claude/skills/doc-standards/scripts/tests/test-check-rule-citations.sh` | convert | py | here-doc; 338 lines (>128) |
| `configs/ai-docs/claude/skills/doc-standards/scripts/tests/test-fix-density.sh` | convert | py | here-doc; 589 lines (>128) |
| `configs/ai-docs/claude/skills/english-coach/scripts/extract-user-messages.sh` | convert | py | jq |
| `configs/ai-docs/claude/skills/implement/scripts/check-pr-dependencies-ready.sh` | convert | py | awk; 218 lines (>128) |
| `configs/ai-docs/claude/skills/implement/scripts/get-pr-tasks.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/implement/scripts/implement-loop-state.sh` | convert | py | awk+jq+here-doc; 455 lines (>128) |
| `configs/ai-docs/claude/skills/implement/scripts/need-git-checkout.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/implement/scripts/parse-pr-breakdown.sh` | convert | py | awk; 138 lines (>128) |
| `configs/ai-docs/claude/skills/implement/scripts/tests/test-check-pr-dependencies-ready.sh` | convert | py | 270 lines (>128) |
| `configs/ai-docs/claude/skills/implement/scripts/tests/test-get-pr-tasks.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/skills/implement/scripts/tests/test-implement-loop-state.sh` | convert | py | jq; 773 lines (>128) |
| `configs/ai-docs/claude/skills/implement/scripts/tests/test-need-git-checkout.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/skills/implement/scripts/tests/test-parse-pr-breakdown.sh` | convert | py | awk; 213 lines (>128) |
| `configs/ai-docs/claude/skills/improve-from-user/scripts/tests/test-extract-session-feedback.sh` | convert | py | here-doc; 347 lines (>128) |
| `configs/ai-docs/claude/skills/improve-from-user/scripts/tests/test-resolve-repo-targets.sh` | convert | py | 400 lines (>128) |
| `configs/ai-docs/claude/skills/jira-cli/scripts/fetch-jira-review-context.sh` | convert | py | jq |
| `configs/ai-docs/claude/skills/jira-cli/scripts/jira-utilities.sh` | convert | py | jq; 587 lines (>128) |
| `configs/ai-docs/claude/skills/jira-cli/scripts/jira.sh` | convert | py | jq |
| `configs/ai-docs/claude/skills/open-in-tmux/scripts/diffview-in-tmux.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/skills/open-in-tmux/scripts/open-in-tmux.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/performance-check-principles-and-skills/scripts/check.sh` | convert | py | awk; 685 lines (>128) |
| `configs/ai-docs/claude/skills/performance-check-principles-and-skills/scripts/tests/test-check-missing-why.sh` | convert | py | awk+here-doc; 232 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-ac-coverage.sh` | convert | py | awk; 147 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-coverage-checklists.sh` | convert | py | awk; 224 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-open-questions.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-pr-dag.sh` | convert | py | awk; 141 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-sections.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-tasks-dag.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/check-test-distribution.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/dag-check-helper.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/extract-design-tests.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/extract-planned-tests-for-task.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/normalize-list-breadcrumbs.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/plan-section.sh` | convert | py | awk |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-ac-coverage.sh` | convert | py | 186 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-coverage-checklists.sh` | convert | py | here-doc; 243 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-open-questions.sh` | stays-sh | py | no risky construct, <=128 lines |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-pr-dag.sh` | convert | py | 192 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-sections.sh` | convert | py | 214 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-tasks-dag.sh` | convert | py | 160 lines (>128) |
| `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-plan-section.sh` | convert | py | awk |
| `configs/ai-docs/claude/tests/test-global-config-invariants.sh` | convert | py | awk+jq; 302 lines (>128) |
| `run-tests.sh` | stays-sh | py | no risky construct, <=128 lines |

## `oh-my-zsh` — all 29 scripts

| Path | Verdict | Target | Triggering reason |
|---|---|---|---|
| `commands/ai-changelog.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/ai-request.sh` | convert | py | jq |
| `commands/aiappend.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/aicmd.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/aigitcommit.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/anonymize-txt.sh` | convert | py | sed -E |
| `commands/aws-get-dlq-summary.sh` | convert | py | jq; 235 lines (>128) |
| `commands/compile-gantt-mermaid.sh` | convert | py | awk |
| `commands/compile-mermaid.sh` | convert | py | awk |
| `commands/copy.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/diff-sorted-jsons.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/diff-sorted-txt.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/gen-schema-from-json.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/git-worktree-add.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/git-worktree-clean.sh` | convert | py | awk+jq; 418 lines (>128) |
| `commands/notify.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/render-ascii-mermaid.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/search-replace-vim.sh` | stays-sh | py | no risky construct, <=128 lines |
| `commands/vimreview.sh` | stays-sh | py | no risky construct, <=128 lines |
| `install.sh` | excluded | — | install.sh exemption |
| `lib/aicopy.sh` | stays-sh | py | no risky construct, <=128 lines |
| `lib/aiyank.sh` | stays-sh | py | no risky construct, <=128 lines |
| `lib/command-exists.sh` | stays-sh | py | no risky construct, <=128 lines |
| `lib/detect-os.sh` | stays-sh | py | no risky construct, <=128 lines |
| `lib/estimate_tokens.sh` | stays-sh | py | no risky construct, <=128 lines |
| `lib/list-project-paths.sh` | stays-sh | py | no risky construct, <=128 lines |
| `lib/tmux-pane-words-picker.sh` | convert | py | awk |
| `perf-check.sh` | convert | py | awk; 278 lines (>128) |
| `profiler.sh` | convert | py | awk; 313 lines (>128) |

## Divergence from the 54-convert / 28-stay baseline

The measured split here is **87 convert / 11 stays-sh** (98 non-excluded),
not the plan's 54/28 (82). Every extra file is explained below; none is a
classifier defect.

- **The 54/28 baseline was never generated by this classifier.** It was
  written into `code-standards/SKILL.md` by commit `6ab6ed88`, which
  predates `classify-conversion.py` itself (shipped later by `3e6501fa`,
  Task 3). It was a manual/eyeballed count, not a reproducible run — there
  is no prior script output to diff this table against line-for-line.

- **The repo grew between that baseline and this sweep.** Of the 93
  in-scope files that existed at or before commit `6ab6ed88`, 36 are
  `test-*.sh` / `tests/`-directory harnesses and 57 are the scripts they
  test — together already exceeding 82. One more file,
  `configs/ai-docs/claude/hooks/tests/test-claude-implement-compact-reminder.sh`,
  was added afterward at commit `fbd8480f`.

- **Four more files are in-flight in the concurrent session** at capture
  time and were never committed at all when `6ab6ed88` ran:
  `configs/ai-docs/claude/hooks/tests/test-claude-compact-skill-reload.sh`,
  `configs/ai-docs/claude/hooks/tests/test-claude-tmux-compact-bump.sh`,
  `configs/ai-docs/claude/hooks/tests/test-claude-tmux-title-compact-reminder.sh`,
  `configs/ai-docs/claude/skills/spec-driven-development/scripts/tests/test-check-ac-coverage.sh`.

- **`test-*.sh` harnesses inflate the count on both sides of the split.**
  38 of the 87 `convert` verdicts and 3 of the 11 `stays-sh` verdicts are
  bash test files for other scripts, not production scripts themselves —
  the classifier does not special-case them, since it classifies every
  `.sh` file under the tree by design (see the General Flow diagram in
  the plan: a `test-<stem>.sh` is deleted, not converted, once its
  companion script converts). Whether the manual 82-count included these
  is unrecoverable, since no script produced it.

Going forward, this table (not the prose 54/28 baseline) is the number
Tasks 16-20 should scope against — it is the one that is regeneratable.

## Review-cap check against the five conversion batches (Tasks 16-20)

The cap in this task's acceptance criteria is ~6 scripts / ~600 diff
lines per batch. The counts below use each convert-verdict script's
*current* line count as a footprint proxy — a rewrite typically touches
the whole file, so the real diff (old lines removed + new lines added)
runs higher than this number, not lower.

| Task | Files scope | Convert scripts in scope | Current-line footprint | Vs. cap |
|---|---|---|---|---|
| 16 — unix-utils hooks | `hooks/` (excl. per-call guards) | 14 | 2,172 | over on both axes |
| 17 — gate-owning skills | `doc-standards/`, `spec-driven-development/`, `code-review-pipeline/` scripts | 1 + 11 + 3 = 15 | 76 + 1,208 + 135 = 1,419 | over on both axes |
| 18 — workflow skills | `implement/`, `create-pr/`, `open-in-tmux/`, `jira-cli/` scripts, minus `implement-loop-state.sh` (already converted by Task 12) | 4 + 4 + 1 + 3 = 12 | 523 + 502 + 113 + 809 = 1,947 | over on both axes |
| 19 — remaining unix-utils | `usage-audit/` + `brag/` (0 scripts) + `configs/ai-docs/claude/scripts/` (2) + remaining marked skill trees (5) | 7 | 1,353 + 1,621 = 2,974 | over on script count (marginal), over on lines |
| 20 — oh-my-zsh | `commands/`, `lib/` | 9 | 1,488 | over on both axes; the plan already anticipates this ("may split into peer batches") |

**Every one of the five already-scoped batches exceeds the ~6-script
cap** once measured against the real verdict counts — this is a finding
to report, not something re-partitioned here (re-scoping five committed
plan tasks is outside this task's authority).

One more gap: `configs/ai-docs/claude/tests/test-global-config-invariants.sh`
carries a `convert` verdict (302 lines, `awk`+`jq`) but sits outside every
directory named in Tasks 16-20's Files lists — it is not
`hooks/`, not any named skill's `scripts/`, and not
`configs/ai-docs/claude/scripts/`. No currently-scoped batch would pick
it up.
