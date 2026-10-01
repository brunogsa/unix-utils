#!/usr/bin/env bash
# parse-task-dependencies.sh - the one parser of the Task
# Breakdown's **Depends on** grammar.
#
# Usage:
#   parse-task-dependencies.sh <plan-file>
#
# stdout: one "Task N<TAB>Task A,Task B" line per task (empty
#         second field when the task has no dependencies)
#
# exit: 0 parsed; 1 plan defect: an unparsable field, or no
#       task entries; 2 usage error: wrong arg count, plan file
#       missing, or a fence plan-section.sh rejects (diagnostic
#       on stderr)

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
# or a bare field over bullets, "- Task X" per dependency or
# a lone "- none" (read exactly like the inline "none").
#
# Mixing "- none" with "- Task N" bullets is ungrammatical:
# "none" and "some" contradict, so accepting the mix would
# silently pick one.
#
# A task's own dependency block ends at the next blank line or
# heading, so a blank line between the bare field and its
# bullets leaves the field unparsable.
#
# The section may open with an unrelated mermaid diagram (also
# containing "Task N" text) that this state machine never
# enters, since it only starts collecting once a "### N."
# heading is seen.
#
# Any other shape gets an UNGRAMMATICAL marker instead of an
# edge list: the inline "**Depends on**: Task 1", or a bare
# colon with no bullet under it.
#
# Reading either as dependency-free fails open — the graph
# then passes as a no-edge DAG over dependencies nobody
# checked.
edges=$(printf '%s\n' "$section" | awk '
  function flush() {
    if (label == "") return
    if (none_bullets > 1 || (none_bullets == 1 && dep_count > 0)) is_ungrammatical = 1
    if (none_bullets == 1 && dep_count == 0) is_none = 1
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
    none_bullets = 0
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
  in_deps && /^- none[[:space:]]*$/ {
    none_bullets++
    next
  }
  in_deps { in_deps = 0 }
  END { flush() }
')

ungrammatical=$(printf '%s\n' "$edges" |
  awk -F'\t' '$1 == "UNGRAMMATICAL" { printf "%s%s", separator, $2; separator = ", " }')

if [ -n "$ungrammatical" ]; then
  echo "error: unparsable **Depends on** field in: $ungrammatical" >&2
  echo "  canonical grammar: '**Depends on**: none', or a bare '**Depends on**:' line followed by either a lone '- none' bullet or one '- Task N' bullet per dependency (never both)" >&2
  exit 1
fi

if [ -z "$edges" ]; then
  echo "error: Task Breakdown section found but no task entries could be parsed from it" >&2
  exit 1
fi

printf '%s\n' "$edges"
