---
name: commit-standards
description: "USE PROACTIVELY when planning commit boundaries, drafting a message, running git commit/push/checkout, or after the git guard blocks a git command. Conventional format, one logical change per commit."
user-invocable: false
instructions-budget: 15
---

# Commit Standards

Principles for any git commit. Each rule is an instruction with its nested why; code-fence examples sit at the margin below.

## Commit decomposition

### One logical change per commit

- [Instruction] Never bundle unrelated changes - split into small, single-concern commits rather than one big one.
  - [Why] A commit is the unit of revert and review; bundling forces reverting good changes to undo a bad one.

- [Instruction] **CRITICAL: Ensure every commit builds and passes its tests on its own.**
  - [Why] A commit that doesn't build breaks `git bisect` and any rollback that lands on it.
  - [Example] A migration's move + update-refs + delete must land in one commit - split apart, the intermediate commits don't build.

- [Instruction] In a stacked PR series, never land an interim shape that a later PR in the series removes - move that later change down the stack instead.
  - [Why] Each PR can merge alone, so an interim shape runs in production until the later PR lands, which can take weeks.
  - [Example] Bad: PR 3 adds an optional `routing?` param that PR 6 makes required, deleting its guard. Good: PR 3 makes it required; non-using consumers skip the base class.

- [Instruction] **Bundle the related tests, code, docs, and IaC for a change into that one commit.**
  - [Why] Splitting them strands a reviewer who can't see the test that proves the code, or the doc that explains it.

### Refactor isolation & hunk-splitting

- [Instruction] Keep a refactor commit to structure only - rename, restructure, extract, with green tests staying green.
  - [Why] Bundling behavior in hides it under mechanical noise, so reviewers can't separate substantive diff from cosmetic.

  - [Example] A migration (move + update refs + delete) is structure-only - keep it as one isolated refactor commit.

- [Instruction] Land an over-limit metric fix as its own structure-only commit, before the behavior change.
  - [Why] The fix then reviews as pure structure, and the behavior change lands on code already under the limit.

  - [Example] `buildReport` at CRAP 42 against a limit of 16: split it in its own structure-only commit first, then commit the behavior change on top.

- [Instruction] **Split entangled commits by staging with `git-hunk`, never by editing code - committed content stays byte-identical to what was authored and reviewed.**
  - [Why] Editing to stage selectively risks altering the code under review and breaks the audit trail.

- [Example]
```bash
git-hunk list --json           # list hunks with ids
git-hunk show <id>             # inspect a hunk before staging
git-hunk stage <id>            # stage a whole hunk
git-hunk stage <id> -l 3,5-7   # stage only lines 3 and 5-7
```

## Message format

- [Instruction] Make the body carry the why - the spec, business reason, and intent - not the what the diff already records.
  - [Why] Spec and business reasoning rarely survive in the code; the commit body is their durable record for later readers.

- [Instruction] Format the subject as Conventional Commits (`type(scope): subject`), imperative, max 64 chars.
  - [Why] A uniform machine-parseable subject lets tooling group and changelog commits, readable in a one-line log.

- [Instruction] Pass the message as `-m` flags - subject, optional body, attribution - with a multi-line body as one `-m` holding real line breaks, never a HEREDOC or `$( )`.
  - [Why] The git guard cannot inspect a command built at runtime, so it refuses any `$` or backtick and any `<<`.

- [Instruction] End every commit with `Co-Authored-By: <current Claude model, as the harness instructs> <noreply@anthropic.com>` as its own last `-m`.
  - [Why] The git guard rejects a commit without it, since the attribution is how a reader tells agent commits from human ones.

- [Example]
```bash
git commit -q -m "fix(sync): skip schools without a CNPJ" -m "A school with no CNPJ failed the whole batch, so one bad record blocked every other school.

A second paragraph goes inside the same quotes." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

## How to commit

- [Instruction] Commit in roughly one `git status + git diff` then the stage-and-commit chain below - don't pad with extra inspection calls.
  - [Why] We want frequent small commits, and those only stay cheap if each one's tool overhead and context noise stay minimal.
  - [Example] Don't inspect `git log` or prior commits to learn commit style - the format here is authoritative across all repos.

- [Instruction] The index is a repo-global singleton with no owner - before any operation reads then acts on it, the committer must own its current state or abort.
  - [Why] A repo-global index has no owner, so reading it now and acting later is racy - abort closes that gap.

- [Instruction] The stager must not leave what it owns unowned - stage and commit in one uninterrupted chain, `git-hunk stage <id>` included, never as two separate tool calls.
  - [Why] A staged-but-uncommitted file is unowned - any session's next commit can claim it - one invocation closes the gap.

- [Example]
```bash
# The git guard allows exactly this chain. git diff --cached --quiet exits 1 when
# anyone's files are already staged, so the chain stops before it stages anything:
# leave their files alone, wait or report, never unstage them.
git diff --cached --quiet && git add configs/foo.txt && git commit -q -m "fix(sync): skip schools without a CNPJ" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"

# A hunk-level commit puts git-hunk in place of git add, inside the same chain -
# `git commit <path>` would recommit the path's whole working-tree version and
# silently undo the split:
git diff --cached --quiet && git-hunk stage a1b2c3 && git commit -q -m "fix(sync): skip schools without a CNPJ" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

## Guarded git commands

- [Instruction] Run each guarded git command alone, as `git -C <literal dir> <subcommand> <literal paths>`, never after `cd` or a variable, nor before a pipe or redirect.
  - [Why] It guards lost work, peers' staged files, protected branches; it refuses `$` as it can't read a runtime-built command.

- [Example]
```bash
# Bad: cd, a variable and a pipe each get refused
cd $W && git push origin feat/x 2>&1 | tail -3
# Good: one literal command; read its output, filter in a separate call
git -C /path/to/repo push origin feat/x
```

The guarded subcommands are `commit`, `push`, `reset`, `clean`, `checkout`, `restore`, `branch` and `worktree`.

Open [`references/guarded-git-forms.md`](references/guarded-git-forms.md) before the first guarded command other than `commit` in a task, and whenever the guard blocks one: it lists each subcommand's allowed form and what to run in place of every blocked one.
