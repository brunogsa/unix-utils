#!/usr/bin/env bash
# check-tasks-dag.sh - self-review validator: the Task Breakdown's dependency graph is a DAG.
#
# Usage:
#   check-tasks-dag.sh <plan-file>
#
# Extracts the "## Task Breakdown" section from <plan-file> and validates its
# task-dependency graph via dag-check-helper.sh: no cycle, no dangling
# reference to a task id absent from the breakdown, no duplicate task id.
#
# Exit codes:
#   0 - the task-dependency graph is a valid DAG with no duplicate task ids.
#   1 - cycle, dangling reference, or duplicate task id found (diagnostic on stderr).
#   2 - usage error (wrong arg count, plan file missing, section unparsable).

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
# or:
#   ### N. [<status>] Title
#   **Depends on**:
#   - Task X
#   - Task Y
#
# A task's own dependency block ends at the next blank line or heading — the
# section may open with an unrelated mermaid diagram (also containing "Task
# N" text) that this state machine never enters, since it only starts
# collecting once a "### N." heading is seen.
edges=$(printf '%s\n' "$section" | awk '
  function flush() {
    if (label != "") print label "\t" deps
  }
  /^### [0-9]+\./ {
    flush()
    seg = $0
    sub(/^### /, "", seg)
    match(seg, /^[0-9]+/)
    label = "Task " substr(seg, RSTART, RLENGTH)
    deps = ""
    in_deps = 0
    next
  }
  /^\*\*Depends on\*\*:[[:space:]]*none[[:space:]]*$/ { in_deps = 0; next }
  /^\*\*Depends on\*\*:[[:space:]]*$/ { in_deps = 1; next }
  in_deps && /^- Task [0-9]+/ {
    line = $0
    match(line, /Task [0-9]+/)
    tok = substr(line, RSTART, RLENGTH)
    deps = (deps == "" ? tok : deps "," tok)
    next
  }
  in_deps { in_deps = 0 }
  END { flush() }
')

if [ -z "$edges" ]; then
  echo "error: Task Breakdown section found but no task entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$edges" | "$script_dir/dag-check-helper.sh" task
