#!/usr/bin/env bash
# resolve-base-ref - print the CWD repo's base ref, as a
# revision callers diff or log against.
#
# Usage:
#   resolve-base-ref.sh
#
# No arguments. Reads the git repo rooted at the current
# working directory.
#
# Exit codes:
#   0  base ref printed on stdout.
#
#   1  none of the three lookups below resolved; nothing
#      printed. The caller decides what to do next (ask the
#      user, abort, fall back to a caller-supplied ref).
#
# Examples:
#   resolve-base-ref.sh
#   base=$(resolve-base-ref.sh) || echo "no base branch found"
#
# Resolution order, first match wins.
#
# 1. origin's default branch, printed as its remote-tracking
#    ref (origin/main), when origin/HEAD points at a branch
#    that exists locally as a remote-tracking ref.
#
# 2. local main, when step 1 does not resolve.
#
# 3. local master, when neither of the above resolves.
#
# Step 1 prints origin/main, not main, because local main
# often lags origin/main.
#
# A main...HEAD diff then also carries every upstream commit
# the branch merged in, not just the branch's own changes.
#
# A caller that needs a branch NAME (gh pr create --base,
# git fetch origin <name>) strips the leading origin/ itself.
#
# Falling back to a local branch name is the reason this
# script exists over the bare `git symbolic-ref
# refs/remotes/origin/HEAD` one-liner it replaces.
#
# That one-liner resolves to nothing after a --single-branch
# clone, or in any repo where `git remote set-head origin -a`
# was never run - both far more common than "no main and no
# master either".

set -euo pipefail

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 1

# A dangling origin/HEAD (its branch pruned or deleted) names
# no commit, so it falls through to the local lookups.
origin_head=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true)
if [ -n "$origin_head" ] \
  && git rev-parse --verify --quiet "$origin_head^{commit}" >/dev/null; then
  printf '%s\n' "$origin_head"
  exit 0
fi

for branch in main master; do
  if git rev-parse --verify "$branch" >/dev/null 2>&1; then
    printf '%s\n' "$branch"
    exit 0
  fi
done

exit 1
