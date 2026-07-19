#!/usr/bin/env bash
# append-branch-pr-entry.sh - appends a branch/PR entry to branches_<slug>.md,
# creating the file (with a header) on first use.
#
# Usage:
#   append-branch-pr-entry.sh <branches-file> <slug> <pr-label> <branch-name> \
#     [<backfill-pr-label> <backfill-branch-name>]
#
# Writes one entry line per PR into <branches-file>:
#   - **<pr-label>** — branch: `<branch-name>`
#
# The optional backfill pair records an EARLIER PR's entry (the one that ran
# under /implement's no-checkout path and so never triggered a manifest
# write) the first time this script creates the manifest for a later PR's
# batch-end. Per the spec's decision, the manifest must never silently omit
# the PR that triggered its own creation. When given, the backfill entry is
# written before the primary <pr-label> entry — see "Entry ordering" below.
#
# Examples:
#   append-branch-pr-entry.sh branches_foo.md foo PR-1 feat-foo/pr1
#   append-branch-pr-entry.sh branches_foo.md foo PR-2 feat-foo/pr2 PR-1 feat-foo
#
# Idempotent: re-running with a <pr-label> already present in the file is a
# silent no-op for that entry (matches simple-append semantics with the
# spec's accepted rare-interleaving-under-concurrency trade-off — this
# script defends only against the same caller re-running, not against two
# processes racing on the same file at once).
#
# In-place writes only, by design
#
# worktree-setup.md symlinks branches_<slug>.md into every /implement
# worktree, and that symlink can be dangling (target doesn't exist yet)
# until this script's first write. Every write below uses `>`/`>>` directly
# on the given path, NEVER a temp-file-then-mv/rename. `>`/`>>` on a symlink
# (dangling or not) follows it and creates/appends at the resolved target,
# leaving the symlink itself intact; `mv` would instead replace the symlink
# with a plain file and silently detach that worktree from the shared
# manifest. Same footgun this repo's own CLAUDE.md documents for
# settings.json and .gitconfig.
#
# Entry ordering without mid-file insertion
#
# The backfill entry (if given) is appended-if-missing BEFORE the primary
# entry is appended-if-missing. Since both entries only ever append (never
# rewrite existing lines), and the backfill check always runs first, the
# backfill entry lands ahead of the primary entry in the file without ever
# needing to insert a line into already-written content.
#
# Exit codes:
#   0 - success (entry written, or already present as a no-op).
#   2 - usage error (wrong arg count).

set -eo pipefail

if [ $# -ne 4 ] && [ $# -ne 6 ]; then
  echo "usage: $(basename "$0") <branches-file> <slug> <pr-label> <branch-name> [<backfill-pr-label> <backfill-branch-name>]" >&2
  exit 2
fi

branches_file="$1"
slug="$2"
pr_label="$3"
branch_name="$4"
backfill_pr_label="${5:-}"
backfill_branch_name="${6:-}"

# entry_line - prints the manifest line for a given PR label + branch name.
entry_line() {
  local label="$1" branch="$2"
  printf -- '- **%s** — branch: `%s`\n' "$label" "$branch"
}

# has_entry - true (exit 0) when <branches-file> already has a line for <pr-label>.
has_entry() {
  local label="$1"
  [ -f "$branches_file" ] && grep -qF "**${label}**" "$branches_file"
}

if [ ! -f "$branches_file" ]; then
  {
    printf '# Branches: %s\n' "$slug"
    printf '\n'
  } > "$branches_file"
fi

if [ -n "$backfill_pr_label" ] && ! has_entry "$backfill_pr_label"; then
  entry_line "$backfill_pr_label" "$backfill_branch_name" >> "$branches_file"
fi

if ! has_entry "$pr_label"; then
  entry_line "$pr_label" "$branch_name" >> "$branches_file"
fi
