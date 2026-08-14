---
# performance-check budget override, not prose a trim could reach.
# This file is the committed, verbatim output of check-script-naming.py that
# plan_script-overhaul.md Tasks 13-15 scope their rename batches from, and
# check-script-naming.test.py asserts its batch scopes against it. Every
# "Reason" cell is the checker's own output, so trimming would falsify the
# reproduction rather than tighten it. Doubled once from the 1024 bundled
# default.
words-budget: 2048
---

# Rename list — check-script-naming.py swept across both repos

This is the committed input Tasks 13-15 of `plan_script-overhaul.md` scope
their rename batches from. Every "Reason" cell below is the checker's own
output, verbatim; every "Proposed name" was hand-derived from the script's
actual behavior.

## How this was generated

```bash
python3 configs/ai-docs/claude/skills/code-standards/scripts/check-script-naming.py \
  --tree ~/unix-utils --tree ~/oh-my-zsh
```

Exit code 1 (failures found), no crash, on both trees.

Every proposed name in this file was independently re-validated with:

```bash
python3 configs/ai-docs/claude/skills/code-standards/scripts/check-script-naming.py \
  <proposed-path-1> <proposed-path-2> ...
```

against the file's target path (not yet created) — file mode resolves the
path but never stats it, so this validates the name alone. Exit 0, 74/74 OK.

## Snapshot provenance

`unix-utils` HEAD at capture time: `8f92ae95ddc33588bb4abc92161fe618d2b10ecc`.

A second Claude Code session commits to this same working tree roughly once
a minute (see `plan_script-overhaul.md`'s concurrency protocol), so this
table is a point-in-time snapshot of both trees' scripts, not a value either
checker invocation will reproduce byte-for-byte on a later run.

Batch 14 folds in `prep-local-context.sh` (`dc00b576`) and `prep-refactor-context.sh` (`45d62ffe`), which landed after that capture and fail the same rule the batch retires, so its counts run two above the sweep.

## Summary

| Batch | Scope (Task) | Repo | Files | Failing |
|---|---|---|---|---|
| 13 | `hooks/` + `scripts/` (Task 13) | `unix-utils` | 23 | 22 |
| 14 | `skills/*/scripts/`, excludes vendored `skill-standards/scripts/` + `eval-viewer/` (Task 14) | `unix-utils` | 57 | 21 |
| 15 | `commands/` + `lib/` + root (Task 15) | `oh-my-zsh` | 31 | 31 |

No failing script in either tree-mode/file-mode sweep falls outside these
three scopes — every FAIL line is assigned to exactly one batch.
Excluded and vendored paths never appear below.

## Batch 13 — `unix-utils` `hooks/` + `scripts/`

Paths relative to `configs/ai-docs/claude/`.

| Current path | Reason | Proposed name |
|---|---|---|
| `hooks/claude-agent-contract-stop-hook.sh` | 'claude' is not a recognized verb | `check-agent-contract-stop.sh` |
| `hooks/claude-comment-format-stop-hook.sh` | 'claude' is not a recognized verb | `check-comment-format-stop.sh` |
| `hooks/claude-compact-skill-reload.sh` | 'claude' is not a recognized verb | `build-skill-reload-reminder.sh` |
| `hooks/claude-explore-mandate-hook.sh` | 'claude' is not a recognized verb | `check-explore-mandate.sh` |
| `hooks/claude-git-guard.sh` | 'claude' is not a recognized verb | `check-git-safety.sh` |
| `hooks/claude-implement-compact-reminder.sh` | 'claude' is not a recognized verb | `build-implement-resume-reminder.sh` |
| `hooks/claude-implement-stop-hook.sh` | 'claude' is not a recognized verb | `check-implement-progress.sh` |
| `hooks/claude-markdown-standards-stop-hook.sh` | 'claude' is not a recognized verb | `check-markdown-standards-stop.sh` |
| `hooks/claude-rename-guard-stop-hook.sh` | 'claude' is not a recognized verb | `check-rename-guard-stop.sh` |
| `hooks/claude-rm-guard.sh` | 'claude' is not a recognized verb; 'rm' is an abbreviation outside the allowlist | `check-delete-safety.sh` |
| `hooks/claude-sdd-stop-hook.sh` | 'claude' is not a recognized verb; 'sdd' is an abbreviation outside the allowlist | `check-spec-coverage-drift.sh` |
| `hooks/claude-stop-orchestrator.sh` | 'claude' is not a recognized verb | `resolve-stop-sequence.sh` |
| `hooks/claude-stopfailure-resume.sh` | 'claude' is not a recognized verb | `resolve-stop-failure.sh` |
| `hooks/claude-tmux-notification.sh` | 'claude' is not a recognized verb | `resolve-tmux-attention-state.sh` |
| `hooks/claude-tmux-title-compact-reminder.sh` | 'claude' is not a recognized verb | `build-tmux-retitle-reminder.sh` |
| `hooks/claude-tmux-title-reminder.sh` | 'claude' is not a recognized verb | `build-tmux-title-reminder.sh` |
| `hooks/claude-tmux-title-restore.sh` | 'claude' is not a recognized verb | `resolve-tmux-title-restore.sh` |
| `hooks/deep-reviewer-write-guard.sh` | 'deep' is not a recognized verb | `check-deep-reviewer-writes.sh` |
| `hooks/subagent-disallowed-tools-guard.py` | 'subagent' is not a recognized verb | `check-subagent-tool-permission.py` |
| `hooks/subagent-model-guard.py` | 'subagent' is not a recognized verb | `check-subagent-model-tier.py` |
| `scripts/statusline-tier.sh` | 'statusline' is not a recognized verb | `build-statusline-tier.sh` |
| `scripts/tmux-window-title.sh` | 'tmux' is not a recognized verb | `resolve-tmux-window-title.sh` |

## Batch 14 — `unix-utils` `skills/*/scripts/`

Paths relative to `configs/ai-docs/claude/skills/`. Excludes vendored
`skill-standards/scripts/` and `eval-viewer/` per Task 14's scope — neither
produced a FAIL in the tree-mode sweep, so there was nothing to drop.

| Current path | Reason | Proposed name |
|---|---|---|
| `brag/scripts/parse_gcal_mcp.py` | name is not kebab-case | `extract-gcal-events.py` |
| `brag/scripts/parse_ics.py` | name is not kebab-case | `extract-ical-events.py` |
| `brag/scripts/shared.py` | 'shared' is not a recognized verb; verb carries no object; 'shared' names a category, not a specific object | `resolve-calendar-overlaps.py` |
| `code-review-pipeline/scripts/prep-local-context.sh` | 'prep' is not a recognized verb | `build-local-review-context.sh` |
| `code-standards/scripts/classify-conversion.py` | 'classify' is not a recognized verb | `resolve-conversion-verdict.py` |
| `consistency-check-principles-and-skills/scripts/gen-shard-manifest.sh` | 'gen' is not a recognized verb | `build-shard-manifest.sh` |
| `implement/scripts/implement-loop-state.sh` | repeats its own skill directory 'implement' | `resolve-task-loop-verdict.sh` |
| `jira-cli/scripts/jira-utilities.sh` | 'jira' is not a recognized verb; 'utilities' names a category, not a specific object | `implement-jira-issue-commands.sh` |
| `jira-cli/scripts/jira.sh` | 'jira' is not a recognized verb; verb carries no object | `build-jira-connection.sh` |
| `jira-cli/scripts/md-to-adf.py` | 'md' is not a recognized verb; 'to' and 'adf' are abbreviations outside the allowlist | `parse-markdown-atlassian-format.py` |
| `markdown-to-google-docs/scripts/gdoc_upload.py` | name is not kebab-case | `implement-google-document-commands.py` |
| `markdown-to-google-docs/scripts/render_and_build.py` | name is not kebab-case | `build-markdown-docx.py` |
| `open-in-tmux/scripts/diffview-in-tmux.sh` | 'diffview' is not a recognized verb | `open-diffview-pane.sh` |
| `open-in-tmux/scripts/open-in-tmux.sh` | repeats its own skill directory 'open-in-tmux' | `open-command-in-pane.sh` |
| `performance-check-principles-and-skills/scripts/check.sh` | verb carries no object | `check-budget-compliance.sh` |
| `refactor/scripts/prep-refactor-context.sh` | 'prep' is not a recognized verb; repeats its own skill directory 'refactor' | `build-uncommitted-change-context.sh` |
| `spec-driven-development/scripts/dag-check-helper.sh` | 'dag' is not a recognized verb; 'helper' names a category, not a specific object | `check-dag-integrity.sh` |
| `spec-driven-development/scripts/plan-section.sh` | 'plan' is not a recognized verb | `extract-plan-section.sh` |
| `usage-audit/scripts/claude-usage-report.py` | 'claude' is not a recognized verb | `build-usage-report.py` |
| `usage-audit/scripts/config-change-ledger.py` | 'config' is not a recognized verb | `build-config-change-ledger.py` |
| `usage-audit/scripts/delivered-work-ledger.py` | 'delivered' is not a recognized verb | `build-delivered-work-ledger.py` |

## Batch 15 — `oh-my-zsh` `commands/` + `lib/` + root

Paths relative to the `oh-my-zsh` repo root. Includes three scripts sitting
directly at that root: the checker skips only the named
`install.sh`/`run-tests.sh` entrypoints, and `install.sh` is present here,
so it stays exempt and does not appear below.

| Current path | Reason | Proposed name |
|---|---|---|
| `commands/ai-changelog.sh` | 'ai' is not a recognized verb | `build-changelog-summary.sh` |
| `commands/ai-request.sh` | 'ai' is not a recognized verb | `fetch-model-completion.sh` |
| `commands/aiappend.sh` | 'aiappend' is not a recognized verb; verb carries no object | `build-context-notes.sh` |
| `commands/aicmd.sh` | 'aicmd' is not a recognized verb; verb carries no object | `build-shell-command.sh` |
| `commands/aigitcommit.sh` | 'aigitcommit' is not a recognized verb; verb carries no object | `build-commit-message.sh` |
| `commands/anonymize-txt.sh` | 'anonymize' is not a recognized verb; 'txt' is an abbreviation outside the allowlist | `normalize-sensitive-text.sh` |
| `commands/aws-get-dlq-summary.sh` | 'aws' is not a recognized verb; 'get' and 'dlq' are abbreviations outside the allowlist | `fetch-dead-letter-queue-summary.sh` |
| `commands/compile-gantt-mermaid.sh` | 'compile' is not a recognized verb | `build-mermaid-gantt-chart.sh` |
| `commands/compile-mermaid.sh` | 'compile' is not a recognized verb | `build-mermaid-diagram.sh` |
| `commands/copy.sh` | 'copy' is not a recognized verb; verb carries no object | `resolve-clipboard-copy.sh` |
| `commands/diff-sorted-jsons.sh` | 'diff' is not a recognized verb | `extract-json-diff.sh` |
| `commands/diff-sorted-txt.sh` | 'diff' is not a recognized verb; 'txt' is an abbreviation outside the allowlist | `extract-text-diff.sh` |
| `commands/gen-schema-from-json.sh` | 'gen' is not a recognized verb | `build-json-schema.sh` |
| `commands/git-worktree-add.sh` | 'git' is not a recognized verb; 'add' is an abbreviation outside the allowlist | `build-git-worktree.sh` |
| `commands/git-worktree-clean.sh` | 'git' is not a recognized verb | `fix-stale-git-worktrees.sh` |
| `commands/notify.sh` | 'notify' is not a recognized verb; verb carries no object | `resolve-desktop-notification.sh` |
| `commands/render-ascii-mermaid.sh` | 'render' is not a recognized verb | `build-mermaid-ascii-canvas.sh` |
| `commands/search-replace-vim.sh` | 'search' is not a recognized verb; 'vim' is an abbreviation outside the allowlist | `fix-project-text-editor.sh` |
| `commands/vimreview.sh` | 'vimreview' is not a recognized verb; verb carries no object | `open-diff-review.sh` |
| `commands/jsonl-distribution-table.js` | 'jsonl' is not a recognized verb | `build-jsonl-distribution-table.js` |
| `commands/jsonl-merge-and-sort-by-field.js` | 'jsonl' is not a recognized verb; 'and' and 'by' are abbreviations outside the allowlist | `build-sorted-jsonl-merge.js` |
| `lib/aicopy.sh` | 'aicopy' is not a recognized verb; verb carries no object | `build-clipboard-bundle.sh` |
| `lib/aiyank.sh` | 'aiyank' is not a recognized verb; verb carries no object | `resolve-repo-relative-paths.sh` |
| `lib/command-exists.sh` | 'command' is not a recognized verb | `check-command-exists.sh` |
| `lib/detect-os.sh` | 'detect' is not a recognized verb; 'os' is an abbreviation outside the allowlist | `resolve-host-platform.sh` |
| `lib/estimate_tokens.sh` | name is not kebab-case | `get-token-estimate.sh` |
| `lib/list-project-paths.sh` | 'list' is not a recognized verb | `extract-project-paths.sh` |
| `lib/tmux-pane-words-picker.sh` | 'tmux' is not a recognized verb | `extract-tmux-pane-selection.sh` |
| `json-deep-sort.js` | 'json' is not a recognized verb | `normalize-json-deep-sort.js` |
| `perf-check.sh` | 'perf' is not a recognized verb | `check-shell-startup-latency.sh` |
| `profiler.sh` | 'profiler' is not a recognized verb; verb carries no object | `extract-startup-time-breakdown.sh` |

## Collision check

All 74 proposed basenames are pairwise distinct, and none matches an
existing file at its proposed target path — checked mechanically alongside
the checker re-validation above.
