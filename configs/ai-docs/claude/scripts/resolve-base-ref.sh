#!/usr/bin/env bash
# resolve-base-ref - print the CWD repo's base branch name.
#
# Usage:
#   resolve-base-ref.sh
#
# No arguments. Reads the git repo rooted at the current
# working directory.
#
# Exit codes:
#   0  base branch name printed on stdout.
#
#   1  none of the three lookups below resolved; nothing
#      printed. The caller decides what to do next (ask the
#      user, abort, fall back to a caller-supplied ref).
#
# Examples:
#   resolve-base-ref.sh
#   base=$(resolve-base-ref.sh) || echo "no base branch found"
#
# Resolution order: origin's default branch (origin/HEAD),
# then local main, then local master.
#
# Falling back to a local branch name is the reason this
# script exists over the bare `git symbolic-ref
# refs/remotes/origin/HEAD` one-liner it replaces.
#
# That one-liner resolves to nothing after a --single-branch
# clone, or in any repo where `git remote set-head origin -a`
# was never run — both far more common than "no main and no
# master either".
#
# Extracted from resolve_base() in
# open-in-tmux/scripts/diffview-in-tmux.sh, which keeps
# its own copy rather than call out to this script.
#
# That caller needs the ref inline to build one `nvim -c`
# argument, and its own file already documents why.
#
# ~/neovim/init.lua's get_base_branch mirrors the same
# fallback order again, independently, in Lua, for the
# editor's own <leader>tD diff.
#
# Both remaining copies are deliberate, not oversight — a
# caller stuck on tmux/git glue or on pure Lua can't shell
# out to this script.

set -euo pipefail

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 1

origin_head=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true)
if [ -n "$origin_head" ]; then
  printf '%s\n' "${origin_head#origin/}"
  exit 0
fi

for branch in main master; do
  if git rev-parse --verify "$branch" >/dev/null 2>&1; then
    printf '%s\n' "$branch"
    exit 0
  fi
done

exit 1
