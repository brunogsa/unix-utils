#!/usr/bin/env bash
# get-pr-tasks.sh - resolves a PR Breakdown's PR-N label to its listed task-id list.
#
# Usage:
#   get-pr-tasks.sh <plan-file> <PR-N>
#
# Extracts the "## PR Breakdown" section from <plan-file>, finds the entry
# labeled <PR-N> (e.g. "PR-2"), and prints its "Tasks: <N, N>" clause verbatim.
# The printed format is the same comma-space "N, N" list /implement's own
# <task-ids> argument already expects (see implement/SKILL.md's Usage
# section), so /implement's pre-flight can pipe this straight through.
#
# Exit codes:
#   0 - PR-N found; its task-id list printed to stdout.
#   1 - PR-N not found in the plan's PR Breakdown (diagnostic on stderr).
#   2 - usage error (wrong arg count, plan file missing, section unparsable).

set -eo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $(basename "$0") <plan-file> <PR-N>" >&2
  exit 2
fi

plan_file="$1"
pr_label="$2"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
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
# The label sits in the line's first **...** span; the Tasks: clause runs up
# to the next period, mirroring check-pr-dag.sh's Depends on: clause parsing.
entries=$(printf '%s\n' "$section" | awk '
  {
    line = $0
    if (!match(line, /\*\*[^*]*PR-[0-9]+[^*]*\*\*/)) next
    seg = substr(line, RSTART, RLENGTH)
    if (!match(seg, /PR-[0-9]+/)) next
    label = substr(seg, RSTART, RLENGTH)

    tasks = ""
    if (match(line, /Tasks:[^.]*/)) {
      tasks = substr(line, RSTART + 6, RLENGTH - 6)
      gsub(/^[ \t]+|[ \t]+$/, "", tasks)
    }
    print label "\t" tasks
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

tasks=$(printf '%s' "$matched_entry" | cut -f2)

if [ -z "$tasks" ]; then
  echo "error: PR-N entry found but its Tasks: clause could not be parsed: $pr_label" >&2
  exit 2
fi

printf '%s\n' "$tasks"
