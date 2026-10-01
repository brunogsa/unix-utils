#!/usr/bin/env bash
# check-tasks-dag.sh - self-review validator: the Task
# Breakdown's dependency graph is a DAG.
#
# Usage:
#   check-tasks-dag.sh <plan-file>
#
# Reads the "## Task Breakdown" section's edges via
# parse-task-dependencies.sh and validates the graph via
# dag-check-helper.sh.
#
# It rejects a cycle, a dangling reference to a task id absent
# from the breakdown, and a duplicate task id.
#
# Exit codes:
#   0 - the task-dependency graph is a valid DAG with no
#       duplicate task ids.
#
#   1 - cycle, dangling reference, duplicate task id, a task's
#       **Depends on** unparsable, or no task entries found
#       (diagnostic on stderr).
#
#   2 - gate could not run: wrong arg count, plan file missing,
#       or a code fence plan-section.sh rejects.

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

# The **Depends on** grammar (and its exit-1 diagnostics for an
# unparsable field or a section with no task entries) lives in
# parse-task-dependencies.sh alone; a failure there ends this
# script with the parser's own exit code and diagnostic.
edges=$("$script_dir/parse-task-dependencies.sh" "$plan_file")

printf '%s\n' "$edges" | "$script_dir/dag-check-helper.sh" task
