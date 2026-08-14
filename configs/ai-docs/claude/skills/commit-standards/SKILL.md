---
name: commit-standards
description: "USE PROACTIVELY at two moments: planning commit boundaries when a task or sub-step ends, AND drafting a message or running git commit. Conventional format + one-logical-change decomposition, refactor isolation, tests/docs bundled."
user-invocable: false
instructions-budget: 12
---

# Commit Standards

Principles for any git commit. Each rule is an instruction with its nested why; code-fence examples sit at the margin below.

## Commit decomposition

### One logical change per commit

- [Instruction] Never bundle unrelated changes — split into small, single-concern commits rather than one big one.
  - [Why] A commit is the unit of revert and review; bundling or oversizing forces reverting good changes to undo a bad one and makes reviewers judge multiple concerns at once.

- [Instruction] **CRITICAL: Ensure every commit builds and passes its tests on its own.**
  - [Why] A commit that doesn't build breaks `git bisect` and any rollback that lands on it, defeating the per-commit revert it's supposed to enable.
  - [Example] A migration's move + update-refs + delete must land in one commit — split apart, the intermediate commits don't build.

- [Instruction] **Bundle the related tests, code, docs, and IaC for a change into that one commit.**
  - [Why] Splitting them strands a reviewer who can't see the test that proves the code, or the doc that explains it.

### Refactor isolation & hunk-splitting

- [Instruction] Keep a refactor commit to structure only — rename, restructure, extract, with green tests staying green.
  - [Why] Bundling behavior in hides it under mechanical noise, so reviewers can't separate the substantive diff from the cosmetic; isolation makes each reviewable in seconds.

  - [Example] A migration (move + update refs + delete) is structure-only — keep it as one isolated refactor commit.

- [Instruction] **Split entangled commits by staging with `git-hunk`, never by editing code — committed content stays byte-identical to what was authored and reviewed.**
  - [Why] Editing to stage selectively risks altering the code under review and breaks the audit trail; staging touches the index, never the working tree.

- [Example]
```bash
git-hunk list --json           # list hunks with ids
git-hunk show <id>             # inspect a hunk before staging
git-hunk stage <id>            # stage a whole hunk
git-hunk stage <id> -l 3,5-7   # stage only lines 3 and 5-7
```

## Message format

- [Instruction] Make the body carry the why — the spec, business reason, and intent — not the what the diff already records.
  - [Why] Spec and business reasoning rarely survive in the code; the commit body is their durable record for later readers, human and AI alike.

- [Instruction] Format the subject as Conventional Commits (`type(scope): subject`), imperative, max 64 chars.
  - [Why] A uniform machine-parseable subject lets tooling group and changelog commits, and the cap keeps it readable in a one-line log.

- [Instruction] Pass a multi-line commit message via HEREDOC, not a plain `-m "..."`.
  - [Why] HEREDOC preserves line breaks, indentation, and blank lines reliably across shells, where `-m "..."` mangles multi-line text.

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

- [Instruction] Never whole-file-stage a path — `git commit -- <path>`, `git commit -a`, or `git add <path>` alike — while another writer may hold uncommitted edits there.
  - [Why] `git add <path>` re-stages that path's entire working-tree diff exactly like the trailing pathspec does, so either one silently commits a concurrent session's in-progress edits alongside yours.

  - [Example]
```bash
# Before staging, confirm every hunk in the diff is yours to commit:
git diff configs/foo.txt

# A file you just created has no other writer — git add <path> is safe there.
# Otherwise stage only your own hunks:
git-hunk stage <id>; git commit -m "..."                       # good — commits exactly what was staged

git-hunk stage <id>; git commit -m "..." -- configs/foo.txt   # bad — recommits the whole file, discarding the hunk pick
git add configs/foo.txt; git commit -m "..."                   # bad — also re-stages the whole file, sweeping in anyone else's edits
```

- [Instruction] **Never pass `--no-verify` or `--no-gpg-sign` unless the user explicitly asks for it.**
  - [Why] Hooks catch lint and security issues at commit time, so bypassing them just ships those issues.
