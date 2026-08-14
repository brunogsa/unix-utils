---
name: commit-standards
description: "USE PROACTIVELY at two moments: planning commit boundaries when a task or sub-step ends, AND drafting a message or running git commit. Conventional format + one-logical-change decomposition, refactor isolation, tests/docs bundled."
user-invocable: false
instructions-budget: 13
---

# Commit Standards

Principles for any git commit. Each rule is an instruction with its nested why; code-fence examples sit at the margin below.

## Commit decomposition

### One logical change per commit

- [Instruction] Never bundle unrelated changes — split into small, single-concern commits rather than one big one.
  - [Why] A commit is the unit of revert and review; bundling forces reverting good changes to undo a bad one.

- [Instruction] **CRITICAL: Ensure every commit builds and passes its tests on its own.**
  - [Why] A commit that doesn't build breaks `git bisect` and any rollback that lands on it.
  - [Example] A migration's move + update-refs + delete must land in one commit — split apart, the intermediate commits don't build.

- [Instruction] **Bundle the related tests, code, docs, and IaC for a change into that one commit.**
  - [Why] Splitting them strands a reviewer who can't see the test that proves the code, or the doc that explains it.

### Refactor isolation & hunk-splitting

- [Instruction] Keep a refactor commit to structure only — rename, restructure, extract, with green tests staying green.
  - [Why] Bundling behavior in hides it under mechanical noise, so reviewers can't separate substantive diff from cosmetic.

  - [Example] A migration (move + update refs + delete) is structure-only — keep it as one isolated refactor commit.

- [Instruction] **Split entangled commits by staging with `git-hunk`, never by editing code — committed content stays byte-identical to what was authored and reviewed.**
  - [Why] Editing to stage selectively risks altering the code under review and breaks the audit trail.

- [Example]
```bash
git-hunk list --json           # list hunks with ids
git-hunk show <id>             # inspect a hunk before staging
git-hunk stage <id>            # stage a whole hunk
git-hunk stage <id> -l 3,5-7   # stage only lines 3 and 5-7
```

## Message format

- [Instruction] Make the body carry the why — the spec, business reason, and intent — not the what the diff already records.
  - [Why] Spec and business reasoning rarely survive in the code; the commit body is their durable record for later readers.

- [Instruction] Format the subject as Conventional Commits (`type(scope): subject`), imperative, max 64 chars.
  - [Why] A uniform machine-parseable subject lets tooling group and changelog commits, readable in a one-line log.

- [Instruction] Pass a multi-line commit message via HEREDOC, not a plain `-m "..."`.
  - [Why] HEREDOC preserves line breaks, indentation, and blank lines across shells; `-m "..."` mangles multi-line text.

- [Example]
```bash
git commit -m "$(cat <<'EOF'
   Commit message here.

   Co-Authored-By: <current Claude model, as the harness instructs> <noreply@anthropic.com>
   EOF
)"
```

## How to commit

- [Instruction] Commit in roughly one `git status + git diff` then `git add <paths> && git commit` — don't pad with extra inspection calls.
  - [Why] We want frequent small commits, and those only stay cheap if each one's tool overhead and context noise stay minimal.
  - [Example] Don't inspect `git log` or prior commits to learn commit style — the format here is authoritative across all repos.

- [Instruction] Don't stage with `git add -A` or `git add .`; specify paths explicitly.
  - [Why] A blanket add risks sweeping in secrets or unrelated files that then ship in the commit.

- [Instruction] The index is a repo-global singleton with no owner — before any operation reads then acts on it, the committer must own its current state or abort.
  - [Why] A repo-global index has no owner, so reading it now and acting later is racy — abort closes that gap.

- [Instruction] The stager must not leave what it owns unowned — stage and commit in one uninterrupted chain, `git-hunk stage <id>` included, never as two separate tool calls.
  - [Why] A staged-but-uncommitted file is unowned — any session's next commit can claim it — one invocation closes the gap.

  - [Example]
```bash
# Assert ownership of everything already staged — empty index, or exactly
# your own paths — then act in the same invocation. The same shape covers
# any other index-touching operation: amend, stash/pop, reset, a
# pre-commit hook that re-stages.
staged=$(git diff --cached --name-only) \
  && { [ -z "$staged" ] || [ "$staged" = "configs/foo.txt" ]; } \
  && git add configs/foo.txt && git commit -m "..."

# git-hunk splits belong inside the same guarded chain, never staged first
# and committed later — a hunk-level commit can't use the pathspec form,
# since `git commit <path>` recommits that path's whole working-tree
# version and silently undoes the split:
staged=$(git diff --cached --name-only) \
  && { [ -z "$staged" ] || [ "$staged" = "configs/foo.txt" ]; } \
  && git-hunk stage <id> && git commit -m "..."
```

- [Instruction] **Never pass `--no-verify` or `--no-gpg-sign` unless the user explicitly asks for it.**
  - [Why] Hooks catch lint and security issues at commit time, so bypassing them just ships those issues.
