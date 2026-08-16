---
name: personal-format
description: "Manual safety-net that formats the user's own recently-changed files to personal comment and markdown standards, on demand only."
user-invocable: true
disable-model-invocation: true
---

# Personal Format Safety-Net

Run `comment-format-fixer` and `markdown-standards-fixer` over the files the
user has changed in the current working tree, for the case where the normal
per-write Stop hooks didn't cover a file (e.g. it was touched outside this
session, or hand-edited directly).

This skill invents no new checker script and no new scoping logic — it only
orchestrates the two existing fixer agents over files found with existing git
commands.

## Process

### 1. Resolve changed files

Union of:

```bash
git diff --name-only          # tracked, modified vs HEAD
git ls-files --others --exclude-standard   # untracked
```

This mirrors how `get-changed-lines.sh` already treats an untracked file as
whole-file-changed.

### 2. Handle an empty union

If the union is empty, report "nothing to check" and stop. Dispatch no
fixer agent — a clean tree is a no-op.

### 3. Classify by extension

- `.ts` / `.js` / `.sh` / `.py` → the `comment-format-fixer` batch.
- `.md` → the `markdown-standards-fixer` batch.
- Any other extension → skip silently, not reported as an error.

### 4. Drop deleted files from each batch

For each file in either batch, check whether it was deleted in the working
tree — `git diff --name-status` showing a `D` status, or the file missing on
disk while `git ls-files` still lists it. Skip a deleted file: don't pass it
to any fixer, and name it explicitly in the final report as
skipped-because-deleted.

### 5. Dispatch the fixers

When both batches are non-empty, dispatch `comment-format-fixer` and
`markdown-standards-fixer` in parallel — they touch disjoint files, so
nothing about running them concurrently is unsafe. Scope each dispatch to
only its own batch's files, never the whole repo. When only one batch is
non-empty, dispatch just that one.

### 6. Report per-file status

Once both dispatched fixers return, report each file's outcome individually:
fixed, not-reached, or failed. Never merge a failing file's status into a
success summary — if one fixer reports residue or failure while the other
reports clean, state both outcomes distinctly. No automatic retry on a
fixer failure; a failure is reported, not re-attempted.

## Idempotency

Re-running this skill is safe by construction: the fixer agents only act on
files with actual violations, so a re-run on an already-clean tree (or one
where the prior run already fixed everything and no new changes landed)
naturally resolves to "nothing to check" or an all-clean report, with no
further edits. No special-case logic is needed for this.
