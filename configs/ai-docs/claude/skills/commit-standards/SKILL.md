---
name: commit-standards
description: "USE PROACTIVELY at two moments: planning commit boundaries when a task or sub-step ends, AND drafting a message or running git commit. Conventional format + one-logical-change decomposition, refactor isolation, tests/docs bundled."
user-invocable: false
instructions-budget: 10
---

# Commit Standards

Principles and rules for any git commit. Each section pairs a principle with its rule or example.

## One logical change per commit, always working

[Instruction] Never bundle unrelated changes.

[Why] A commit is a unit of reverting and a unit of review.

Bundled commits force you to revert good changes to undo a bad one, and force reviewers to context-switch between concerns. Small, single-purpose commits are surgical.

- [Examples] **1 task = 1 commit.**
- [Examples] **A migration (move + update refs + delete) is one commit.**
- [Examples] **Refactors get their own commit, always isolated from behavior change.**
- [Examples] **Related tests, code, docs, IaC all bundled together in their own commit.**
- [Instruction] **Exception**: when two logical changes are entangled in one file, prefer a single combined commit over a temporary revert — name both concerns explicitly in the commit body.
  - [Why] Reverting in-progress code to split commits risks losing work or introducing manual errors. The "preserve user work" rule (`CLAUDE.md`) overrides "one logical change per commit."

## Conventional commits with WHY body that fits on a screen (~32 lines)

[Instruction] The diff already records what changed; the body explains why.

[Why] Future-you reading `git log` six months later doesn't have the PR open. The commit body is the standalone record of intent. If the body just restates the diff, it's wasted lines.

- [Examples] Format: Conventional Commits (`type(scope): subject`), imperative, max 72-char subject.
- [Examples] Body: scannable bullets/sub-bullets by default. Prose only when fragmenting would lose connective tissue.

## Minimize tool calls when committing

[Instruction] One `git status + git diff` + `git add .. && git commit` is generally enough.

[Why] Every tool call slows down the commit and adds context noise. We want FREQUENT and small commits — those need to be cheap.

- [Examples] Don't inspect `git log` or prior commits to learn commit style — Bruno's format is authoritative across all repos. Skip that tool call.
- [Examples] Don't add files with `git add -A` or `git add .` — adds risk of including secrets or unrelated files. Specify paths explicitly.

## Refactors are isolated from behavior changes

[Instruction] A refactor commit changes structure, never behavior. A behavior commit changes behavior, never structure.

[Why] Bundled refactors hide the behavior change in mechanical noise — reviewers can't tell the substantive diff from the cosmetic. Isolation makes each commit reviewable in seconds.

- [Examples] Refactor commit: rename, restructure, extract — green tests stay green.
- [Examples] Behavior commit: small, focused, test-backed.

## Don't skip hooks (--no-verify) or bypass signing (--no-gpg-sign)

[Instruction] Unless the user has explicitly asked for it.

[Why] Hooks catch lint/security issues at commit time — bypassing means they ship. If a hook fails, investigate and fix the underlying issue, not the hook.

## Don't commit changes unless explicitly asked

[Instruction] Wait for the user's explicit "commit this" or equivalent.

[Why] Pre-emptive commits feel intrusive — the user may want to inspect first or batch differently. Default to staging/diffing only; commit on request.

## Use HEREDOC for commit messages

[Instruction] Pass multi-line commit messages via HEREDOC.

[Examples]
```bash
git commit -m "$(cat <<'EOF'
   Commit message here.

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
)"
```

[Why] HEREDOC preserves formatting (line breaks, indentation, blank lines) reliably across shells. Plain `-m "..."` mangles multi-line messages.

## Create new commits rather than amending

[Instruction] Default to NEW commits. Only amend when the user explicitly requests it.

[Why] Amending modifies the PREVIOUS commit. If the previous commit was pushed or used by others, amending destroys their reference point.

Critically, when a pre-commit hook FAILS, the commit didn't happen — so `--amend` would modify a different (earlier) commit. After hook failure, fix the issue, re-stage, and create a NEW commit.

## Never force-push to main/master

[Instruction] Warn the user if they request it.

[Why] Force-pushing main rewrites shared history. Everyone who pulled is now out of sync. The cost is repo-wide; the benefit is rarely worth it.

For non-main branches, force-push only when the user explicitly asks.
