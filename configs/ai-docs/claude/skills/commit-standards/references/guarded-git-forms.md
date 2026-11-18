# Guarded git forms

The git guard (`configs/ai-docs/claude/hooks/claude-git-guard.py`, a PreToolUse hook on Bash) lets `commit`, `push`, `reset`, `clean`, `checkout`, `restore`, `branch` and `worktree` run only in the forms below.

Anything else exits 2 and prints the rule it broke.

Read the guard's `FORMS` table and `block(...)` messages for the exact rules; this file is the working summary.

## Why the guard is strict

It protects against lost work, a peer session's staged files, and pushes to protected branches.

It cannot inspect a command built at runtime, so it refuses any `$`, backtick or `$( )` in a command that runs a guarded subcommand.

A guarded subcommand therefore runs as a lone command starting with `git`, with at most `-C <dir>` before the subcommand, or as the one fixed commit chain.

## Allowed forms

One example per subcommand, each verified against the guard.

```bash
# commit: -m flags, Co-Authored-By as the last -m, subject at most 64 characters
git commit -q -m "fix(sync): skip schools without a CNPJ" -m "Why the change exists." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"

# commit from a message file: write it first with the Write tool, since the guard reads it and refuses a missing file; the attribution is its last paragraph
git commit -q -F /path/to/msg.txt

# commit chain: the only form that may use &&
git diff --cached --quiet && git add configs/foo.txt && git commit -q -m "fix(sync): skip schools without a CNPJ" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"

# commit chain staging only some lines of one hunk: one hunk id, then one of -l <lines>, --include-matching <pat> or --exclude-matching <pat>
git diff --cached --quiet && git-hunk stage 2a70dfa0 -l 4-11 && git commit -q -m "fix(sync): skip schools without a CNPJ" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"

# push: origin plus one plain branch name, never main, master or HEAD
git push -u origin feat/cdpi-805-blank-business-model
git push --force-with-lease origin feat/cdpi-805-blank-business-model

# reset: --soft or --mixed only
git reset --soft HEAD~1
git reset -q -- configs/foo.txt

# clean: dry run only
git clean -nd

# checkout: a branch, a new branch, or named paths
git checkout feat/new-branch
git checkout -b feat/new-branch origin/master
git checkout HEAD -- configs/foo.txt

# restore: named paths
git restore --staged configs/foo.txt

# branch: list, create, or delete a merged branch
git branch --show-current
git branch feat/new-branch origin/master
git branch -d feat/new-branch

# worktree: add, list, remove, unlock, prune
git worktree add -b feat/new-branch /path/to/worktree origin/master
git worktree list
git worktree remove /path/to/worktree
git worktree unlock /path/to/worktree   # a finished agent's stale lock; then remove it
git worktree prune -n

# another directory: -C is the only global option, and it takes a literal path
git -C /path/to/repo push origin feat/new-branch
```

## Blocked, and what to run instead

Each row's reason is the guard's own: it keeps lost work, a peer's staged files and protected branches safe.

| Blocked form | Run instead |
| --- | --- |
| `git commit -m "$(cat <<'EOF' ... EOF)"`, or a `$` or backtick anywhere | Separate `-m` flags, with real line breaks inside one `-m` for a multi-line body |
| `git commit -F - <<'EOF' ...` | `-m` flags, or `-F <file>` written with the Write tool |
| `cd /repo && git commit ...`, `W=/repo; git -C $W ...` | `git -C /repo commit ...` with the literal path |
| `git add f && git commit ...` | The chain, starting with `git diff --cached --quiet` |
| `git add .`, `git add -A` in the chain | Named paths |
| `git commit -a`, `--amend`, `--no-edit`, a pathspec | A new commit on named paths through the chain |
| `git commit --no-verify`, `--no-gpg-sign` | Never run through the guard; when the user asks for one, tell them to run it themselves |
| `git commit --trailer "Gate: metrics"` | A `Gate: metrics` line directly above the `Co-Authored-By` line, inside the last `-m` |
| Subject over 64 characters | A shorter subject, with the detail in the body |
| No `Co-Authored-By: Claude ...` as the last `-m` | Add it |
| `git ... 2>&1 \| tail`, `> file`, `; git ...`, `git status && git push ...` | The guarded command alone; filter its output in the next call |
| `X=$(git branch --show-current)`, `date "+$(git branch ...)"` | Run `git branch --show-current` alone, then write its output literally into the next command |
| `git push`, `git push -u origin HEAD`, `git push origin main` | `git push -u origin <branch name>`, the name from `git branch --show-current` |
| `git push --force`, `--force-if-includes`, `+branch`, `src:dst` | `--force-with-lease` plus a plain branch name |
| `git push origin feat/a feat/b` | One push per branch |
| `git reset --hard`, any other reset option | `--soft` or `--mixed`; `git restore <path>` to drop one path's changes |
| `git clean -f`, `-fd` | `git clean -nd` to list, then `rm` the named files |
| `git checkout .`, `git checkout -- .`, `-B`, `--no-track` | Named paths, or `-b <branch> [<start>]`; `git push -u origin <branch>` then sets the upstream |
| `git checkout <name>` when `<name>` is also a file here | `git switch <branch>` or `git restore <file>` |
| `git checkout a && git merge b` | Two separate calls |
| `git restore .`, `--source=` | Named paths |
| `git branch -D`, `-m` | `git branch -d`; ask the user before dropping an unmerged branch |
| `git worktree remove --force` | Plain `git worktree remove`; ask the user when the worktree is dirty |
| `git -c key=value ...`, `GIT_CONFIG` overrides | Plain `git` with no config override |
| `bash -c "git ..."`, `eval`, `aigitcommit` | `git` run directly |

## Unguarded by design

`git switch -f`, `git stash drop`, `git stash clear`, `git rm -f` and the aliases in `~/.gitconfig` pass the guard.

Passing it does not make one safe: each can lose the same work the guard exists to protect, so never use one as a way around a block.
