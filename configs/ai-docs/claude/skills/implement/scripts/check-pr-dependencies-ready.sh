#!/usr/bin/env bash
# check-pr-dependencies-ready.sh - PR-level dependency guard: confirms every
# parent PR named in PR-N's "Depends on:" list is safe to build on, before
# /implement creates PR-N's own branch. Extracts the guard's core logic out
# of inline /implement prose, mirroring the existing task-level chain-abort
# pattern one level up (implement/SKILL.md's §5.4), per the spec's explicit
# decision to make this specific check scriptable and unit-tested.
#
# Usage:
#   check-pr-dependencies-ready.sh <plan-file> <PR-N> <worktree-path>
#
# For every PR-M listed in PR-N's "Depends on:" clause (comma-separated -
# there can be more than one, e.g. a diamond dependency), performs two
# checks:
#   (a) every task listed in PR-M's own "Tasks: <N, N>" clause carries a
#       "[Done]" status marker in the plan's Task Breakdown
#       ("### <id>. [<status>] <title>"; a task heading with no bracket at
#       all counts as not-Done, same as the Task Breakdown template's
#       pending/not-started convention).
#   (b) the branch recorded for PR-M in
#       <worktree-path>/branches_<slug>.md (written by
#       append-branch-pr-entry.sh) is a real git ancestor of
#       <worktree-path>'s current HEAD, via `git merge-base --is-ancestor`.
#       A [Done] marker alone only proves the plan file's bookkeeping, not
#       that this worktree's HEAD actually contains PR-M's commits - a
#       dependent PR started from the wrong worktree must fail loudly here
#       instead of silently branching off the wrong base.
#
# PR-N with no parents (Depends on: none) passes immediately - a DAG root
# has nothing to wait for.
#
# Exit codes:
#   0 - PR-N has no parents, or every parent clears both checks.
#   1 - PR-N label not found in the PR Breakdown, or at least one parent is
#       not ready (outstanding task and/or ancestry mismatch); diagnostic
#       naming every offending task id / branch on stderr.
#   2 - usage error (wrong arg count, plan/worktree path missing, PR
#       Breakdown section unparsable).

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

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# parse-pr-breakdown.sh does the section-extraction + entry-parse pipeline
# shared with get-pr-tasks.sh and need-git-checkout.sh; this script consumes
# both the Tasks: field (column 2) and the Depends on: field (column 3) of
# its TSV output, where each sibling only needed one. Its non-zero exit
# codes distinguish a trivial section (1: absent/"Single PR."), which needs
# this script's own $pr_label-specific diagnostic below, from a malformed
# one (2: content present but unparsable), whose diagnostic
# parse-pr-breakdown.sh already printed to stderr itself - re-printing it
# here would duplicate the line, since $(...) only captures stdout, never
# stderr. Assigned inside an if-condition (never a bare assignment) so a
# non-zero exit here doesn't abort the script under `set -e`.
if pr_entries=$("$script_dir/parse-pr-breakdown.sh" "$plan_file"); then
  :
else
  parse_exit=$?
  if [ "$parse_exit" -eq 1 ]; then
    echo "error: PR-N label not found in the plan's PR Breakdown (section absent or Single PR.): $pr_label" >&2
    exit 1
  else
    exit 2
  fi
fi

# find_pr_entry - prints the pr_entries line (label\ttasks\tdeps) for the
# given PR-N label, or nothing if absent. Bare awk, never a non-zero exit,
# for the same set -e/bare-assignment reason noted throughout this script.
# Defined before its first use below (the target PR-N lookup) since the
# dependency-walk loop further down calls it again for each PARENT label -
# two distinct callers sharing the one lookup.
find_pr_entry() {
  local label="$1"
  printf '%s\n' "$pr_entries" | awk -F'\t' -v target="$label" '$1 == target { print; exit }'
}

matched_entry=$(find_pr_entry "$pr_label")

if [ -z "$matched_entry" ]; then
  echo "error: PR-N label not found in the plan's PR Breakdown: $pr_label" >&2
  exit 1
fi

deps=$(printf '%s' "$matched_entry" | cut -f3)

if [ -z "$deps" ]; then
  echo "OK: $pr_label has no parents (DAG root)."
  exit 0
fi

task_section=$(awk '
  /^## / {
    if (in_section) exit
    if ($0 ~ /^## Task Breakdown[[:space:]]*$/) { in_section = 1; next }
    next
  }
  in_section { print }
' "$plan_file")

# Each Task Breakdown heading looks like: ### <N>. [<status>] <title>
# A task not yet started carries no bracket at all (matches the PR-level
# marker's own "absent for pending" convention), so its status here is "".
task_statuses=$(printf '%s\n' "$task_section" | awk '
  /^### [0-9]+\./ {
    line = $0
    match(line, /^### [0-9]+/)
    id = substr(line, RSTART + 4, RLENGTH - 4)
    status = ""
    if (match(line, /\[[^]]+\]/)) {
      status = substr(line, RSTART + 1, RLENGTH - 2)
    }
    print id "\t" status
  }
')

# task_status_for - prints "found\t<status>" for the given task id, or
# "missing\t" when the id has no heading in the Task Breakdown at all.
task_status_for() {
  local id="$1"
  local hit
  hit=$(printf '%s\n' "$task_statuses" | awk -F'\t' -v want="$id" '$1 == want { print "found\t" $2; exit }')
  if [ -z "$hit" ]; then
    printf 'missing\t'
  else
    printf '%s' "$hit"
  fi
}

slug=$(basename "$plan_file" .md)
slug="${slug#plan_}"
branches_file="$worktree_path/branches_${slug}.md"

# branch_for_pr - prints the branch name recorded for <label> in
# branches_<slug>.md, or nothing if the file or the entry is absent. Bare
# awk, never a non-zero exit, guarded by the file-exists check so awk is
# never invoked against a missing path (which WOULD exit non-zero and abort
# under set -e in this bare-assignment call site).
branch_for_pr() {
  local label="$1"
  if [ ! -f "$branches_file" ]; then
    return 0
  fi
  awk -v label="$label" '
    index($0, "**" label "**") > 0 {
      if (match($0, /branch: `[^`]*`/)) {
        print substr($0, RSTART + 9, RLENGTH - 10)
        exit
      }
    }
  ' "$branches_file"
}

diagnostics=""

# add_diagnostic - appends a diagnostic line, newline-separated.
add_diagnostic() {
  local line="$1"
  if [ -z "$diagnostics" ]; then
    diagnostics="$line"
  else
    diagnostics="$diagnostics
$line"
  fi
}

IFS=',' read -ra dep_labels <<< "$deps"
for raw_parent_label in "${dep_labels[@]}"; do
  parent_label="$(printf '%s' "$raw_parent_label" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"

  parent_entry=$(find_pr_entry "$parent_label")
  if [ -z "$parent_entry" ]; then
    add_diagnostic "error: $pr_label depends on $parent_label, which was not found in the PR Breakdown (dangling dependency)"
    continue
  fi

  parent_tasks=$(printf '%s' "$parent_entry" | cut -f2)
  IFS=',' read -ra task_ids <<< "$parent_tasks"
  for raw_task_id in "${task_ids[@]}"; do
    task_id="$(printf '%s' "$raw_task_id" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [ -z "$task_id" ] && continue

    status_result=$(task_status_for "$task_id")
    status_found=$(printf '%s' "$status_result" | cut -f1)
    task_status=$(printf '%s' "$status_result" | cut -f2)

    if [ "$status_found" = "missing" ]; then
      add_diagnostic "error: $parent_label's Task $task_id was not found in the Task Breakdown"
    elif [ "$task_status" != "Done" ]; then
      add_diagnostic "error: $parent_label has an outstanding task: Task $task_id (status: ${task_status:-none})"
    fi
  done

  parent_branch=$(branch_for_pr "$parent_label")
  if [ -z "$parent_branch" ]; then
    add_diagnostic "error: $parent_label has no recorded branch in branches_${slug}.md (cannot verify ancestry)"
    continue
  fi

  if ! git -C "$worktree_path" merge-base --is-ancestor "$parent_branch" HEAD 2>/dev/null; then
    add_diagnostic "error: worktree HEAD does not descend from $parent_label's recorded branch: $parent_branch"
  fi
done

if [ -n "$diagnostics" ]; then
  printf '%s\n' "$diagnostics" >&2
  exit 1
fi

echo "OK: every parent of $pr_label is Done and an ancestor of HEAD."
exit 0
