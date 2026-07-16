#!/usr/bin/env bash
# diffview-in-tmux - open neovim's Diffview against a commit-ish in a vertical tmux
#                    split of THIS Claude session's pane, for branch/diff review.
#
# Usage:
#   diffview-in-tmux.sh [<ref>]
#
# <ref>  Any git commit-ish to diff the working tree against — branch, tag, SHA,
#        HEAD~5, a `git merge-base` output, etc. Optional.
#        Omitted → the repo's base branch (origin/HEAD → main → master), i.e. the
#        whole-branch diff, matching neovim's <leader>tD.
#
# What it does:
#   Resolves <ref>, finds the repo root, then opens a side-by-side tmux pane running
#     nvim -c "DiffviewOpen <ref>"
#   in that root. Diffview shows the working tree (untracked + unstaged + staged +
#   committed-on-branch) vs <ref> as one combined diff.
#
# Why a wrapper over calling open-in-tmux.sh directly:
#   The fiddly parts are base-branch resolution (origin/HEAD → main → master), repo
#   root, and validating the ref actually resolves. The human says "review since X";
#   the caller (Claude) turns X into a ref (a SHA, a merge-base, a branch), and this
#   script does the rest. The base-branch order mirrors get_base_branch in
#   ~/neovim/init.lua so the pane matches the <leader>tD diff.
#
# Exit codes:
#   0  pane opened (or, outside tmux, open-in-tmux.sh's exit 2 bubbles up with the
#      command printed to stdout for the user to run).
#   1  not a git work tree, ref does not resolve to a commit, or base undetectable.
#
# Env:
#   TMUX_DRY_RUN=1   forwarded to open-in-tmux.sh: print the tmux command, don't run it.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
open_in_tmux="$script_dir/open-in-tmux.sh"

die() {
  echo "Error: $*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || die "git not found."
[ -x "$open_in_tmux" ] || die "sibling script not found or not executable: $open_in_tmux"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree."

# Base branch: origin's default → local main → local master. Mirrors get_base_branch
# in ~/neovim/init.lua so this pane matches the <leader>tD "vs base branch" diff.
resolve_base() {
  local origin_head
  origin_head=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true)
  if [ -n "$origin_head" ]; then
    printf '%s\n' "${origin_head#origin/}"
    return 0
  fi
  local b
  for b in main master; do
    if git rev-parse --verify "$b" >/dev/null 2>&1; then
      printf '%s\n' "$b"
      return 0
    fi
  done
  return 1
}

ref="${1:-}"
if [ -z "$ref" ]; then
  ref=$(resolve_base) || die "could not detect base branch (origin/HEAD, main, or master)."
fi

# Validate the ref peels to a commit, so we never open a pane on a broken DiffviewOpen.
git rev-parse --verify --quiet "${ref}^{commit}" >/dev/null 2>&1 \
  || die "ref does not resolve to a commit: ${ref}"

root=$(git rev-parse --show-toplevel 2>/dev/null) || die "could not find repo root."
[ -n "$root" ] || die "could not find repo root."

# Single-quote the root for cd; ref is validated as a commit-ish (no shell-hostile
# content survives rev-parse) so it is safe inside the DiffviewOpen argument.
exec "$open_in_tmux" vertical "cd '$root' && nvim -c 'DiffviewOpen $ref'"
