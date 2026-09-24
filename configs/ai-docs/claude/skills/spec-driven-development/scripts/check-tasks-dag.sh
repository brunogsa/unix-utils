#!/usr/bin/env bash
# check-tasks-dag.sh - self-review validator: the Task
# Breakdown's dependency graph is a DAG.
#
# Usage:
#   check-tasks-dag.sh <plan-file>
#
# Extracts the "## Task Breakdown" section from <plan-file> and
# validates its task-dependency graph via dag-check-helper.sh:
# no cycle, no dangling reference to a task id absent from the
# breakdown, no duplicate task id.
#
# Exit codes:
#   0 - the task-dependency graph is a valid DAG with no
#       duplicate task ids.
#
#   1 - cycle, dangling reference, or duplicate task id found
#       (diagnostic on stderr).
#   2 - usage error (wrong arg count, plan file missing,
#       section or a task's **Depends on** unparsable).

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <plan-file>" >&2
  exit 2
fi

plan_file="$1"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

section=$("$script_dir/plan-section.sh" "$plan_file" "##" '^Task Breakdown[[:space:]]*$')

# Each task entry looks like:
#   ### N. [<status>] Title
#   **Depends on**: none
#
# or:
#   ### N. [<status>] Title
#   **Depends on**:
#
# - Task X
# - Task Y.
#
# A task's own dependency block ends at the next blank line or
# heading.
#
# The section may open with an unrelated mermaid diagram (also
# containing "Task N" text) that this state machine never
# enters, since it only starts collecting once a "### N."
# heading is seen.
#
# Any other shape gets an UNGRAMMATICAL marker instead
# of an edge list: the inline "**Depends on**: Task 1",
# or a bare colon with no bullet under it.
#
# Reading either as dependency-free fails open — the
# graph then passes as a no-edge DAG over dependencies
# nobody checked.
edges=$(printf '%s\n' "$section" | awk '
  function flush() {
    if (label == "") return
    if (is_ungrammatical || (has_field && !is_none && dep_count == 0)) {
      print "UNGRAMMATICAL\t" label
      return
    }
    print label "\t" deps
  }
  /^### [0-9]+\./ {
    flush()
    seg = $0
    sub(/^### /, "", seg)
    match(seg, /^[0-9]+/)
    label = "Task " substr(seg, RSTART, RLENGTH)
    deps = ""
    dep_count = 0
    in_deps = 0
    has_field = 0
    is_none = 0
    is_ungrammatical = 0
    next
  }
  /^\*\*Depends on\*\*:/ {
    has_field = 1
    in_deps = 0
    trailer = $0
    sub(/^\*\*Depends on\*\*:[[:space:]]*/, "", trailer)
    sub(/[[:space:]]*$/, "", trailer)
    if (trailer == "none") { is_none = 1; next }
    if (trailer != "") { is_ungrammatical = 1; next }
    in_deps = 1
    next
  }
  in_deps && /^- Task [0-9]+/ {
    line = $0
    match(line, /Task [0-9]+/)
    tok = substr(line, RSTART, RLENGTH)
    deps = (deps == "" ? tok : deps "," tok)
    dep_count++
    next
  }
  in_deps { in_deps = 0 }
  END { flush() }
')

ungrammatical=$(printf '%s\n' "$edges" |
  awk -F'\t' '$1 == "UNGRAMMATICAL" { printf "%s%s", separator, $2; separator = ", " }')

if [ -n "$ungrammatical" ]; then
  echo "error: unparsable **Depends on** field in: $ungrammatical" >&2
  echo "  canonical grammar: '**Depends on**: none', or a bare '**Depends on**:' line followed by one '- Task N' bullet per dependency" >&2
  exit 2
fi

if [ -z "$edges" ]; then
  echo "error: Task Breakdown section found but no task entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$edges" | "$script_dir/dag-check-helper.sh" task
