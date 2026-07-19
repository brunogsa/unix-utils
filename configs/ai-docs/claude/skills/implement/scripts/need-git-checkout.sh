#!/usr/bin/env bash
# need-git-checkout.sh - decides whether /implement needs to create a branch
# for the PR about to run, extracting the "skip checkout" rule that would
# otherwise live as inline /implement prose.
#
# Usage:
#   need-git-checkout.sh <plan-file> <PR-N> <worktree-path>
#
# Prints "no" only when BOTH hold:
#   - PR-N is a DAG root: its PR Breakdown entry reads "Depends on: none".
#   - branches_<slug>.md doesn't exist yet in <worktree-path>, or exists but
#     has no entries yet (an empty/header-only manifest counts as "not
#     created yet" for this rule). <slug> is derived from <plan-file>'s own
#     name (plan_<slug>.md -> <slug>), the same convention
#     append-branch-pr-entry.sh and worktree-setup.md already use for
#     branches_<slug>.md.
# Prints "yes" otherwise: PR-N has any parent, or the manifest already has
# at least one entry (this worktree already ran an earlier PR's batch).
#
# Per the spec's narrowing decision, only the FIRST /implement invocation in
# a worktree, targeting a DAG-root PR, skips the checkout - every later PR,
# and any PR with a dependency even if it happens to run first, always gets
# its own branch.
#
# Exit codes:
#   0 - PR-N found; "yes" or "no" printed to stdout.
#   1 - PR-N not found in the plan's PR Breakdown (diagnostic on stderr).
#   2 - usage error (wrong arg count, plan/worktree path missing, section unparsable).

set -eo pipefail

if [ $# -ne 3 ]; then
  echo "usage: $(basename "$0") <plan-file> <PR-N> <worktree-path>" >&2
  exit 2
fi

plan_file="$1"
pr_label="$2"
worktree_path="$3"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

if [ ! -d "$worktree_path" ]; then
  echo "error: worktree path not found: $worktree_path" >&2
  exit 2
fi

section=$(awk '
  /^## / {
    if (in_section) exit
    if ($0 ~ /^## PR Breakdown[[:space:]]*$/) { in_section = 1; next }
    next
  }
  in_section { print }
' "$plan_file")

trimmed=$(printf '%s' "$section" | sed '/^[[:space:]]*$/d')

if [ -z "$trimmed" ] || [ "$trimmed" = "Single PR." ]; then
  echo "error: PR-N label not found in the plan's PR Breakdown (section absent or Single PR.): $pr_label" >&2
  exit 1
fi

# Each PR Breakdown entry line looks like:
#   N. **[<status>] PR-N** — <title>. Tasks: <N, N>. Depends on: <none | PR-N, PR-M>.
# The label sits in the line's first **...** span; the Depends on: clause
# runs up to the next period, mirroring check-pr-dag.sh's own parsing.
entries=$(printf '%s\n' "$section" | awk '
  {
    line = $0
    if (!match(line, /\*\*[^*]*PR-[0-9]+[^*]*\*\*/)) next
    seg = substr(line, RSTART, RLENGTH)
    if (!match(seg, /PR-[0-9]+/)) next
    label = substr(seg, RSTART, RLENGTH)

    deps = ""
    if (match(line, /Depends on:[^.]*/)) {
      clause = substr(line, RSTART + 11, RLENGTH - 11)
      while (match(clause, /PR-[0-9]+/)) {
        tok = substr(clause, RSTART, RLENGTH)
        deps = (deps == "" ? tok : deps "," tok)
        clause = substr(clause, RSTART + RLENGTH)
      }
    }
    print label "\t" deps
  }
')

if [ -z "$entries" ]; then
  echo "error: PR Breakdown section found but no PR-N entries could be parsed from it" >&2
  exit 2
fi

# Looked up via a plain string match (never a failing awk exit code): under
# `set -e`, a command substitution's failure inside a bare assignment (not an
# if/while/&&/|| condition) aborts the script before the diagnostic below can
# print, so "not found" must surface as an empty string, not a non-zero exit.
matched_entry=$(printf '%s\n' "$entries" | awk -F'\t' -v target="$pr_label" '$1 == target { print; exit }')

if [ -z "$matched_entry" ]; then
  echo "error: PR-N label not found in the plan's PR Breakdown: $pr_label" >&2
  exit 1
fi

deps=$(printf '%s' "$matched_entry" | cut -f2)

if [ -n "$deps" ]; then
  echo "yes"
  exit 0
fi

# PR-N is a DAG root. Whether checkout is still needed now depends solely on
# whether this worktree already has a manifest entry from an earlier PR's
# batch-end. append-branch-pr-entry.sh writes each entry as a line starting
# "- **"; a freshly-created header-only manifest has no such line yet.
slug=$(basename "$plan_file" .md)
slug="${slug#plan_}"
branches_file="$worktree_path/branches_${slug}.md"

if [ -f "$branches_file" ] && grep -q '^- \*\*' "$branches_file"; then
  echo "yes"
else
  echo "no"
fi
