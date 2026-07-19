#!/usr/bin/env bash
# check-pr-dag.sh - self-review validator: the PR Breakdown's dependency graph is a DAG.
#
# Usage:
#   check-pr-dag.sh <plan-file>
#
# Extracts the "## PR Breakdown" section from <plan-file> and validates its
# PR-N dependency graph via dag-check-helper.sh: no cycle, no dangling
# reference to a PR-N label absent from the breakdown, no duplicate PR-N
# label. A section that literally reads "Single PR." (the plan template's
# backward-compat escape for a single-PR plan) has nothing to validate and
# passes trivially, same as a plan with no PR Breakdown section at all.
#
# Exit codes:
#   0 - PR Breakdown is absent, reads "Single PR.", or its dependency graph
#       is a valid DAG with no duplicate labels.
#   1 - cycle, dangling reference, or duplicate label found (diagnostic on stderr).
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

section=$("$script_dir/plan-section.sh" "$plan_file" "##" '^PR Breakdown[[:space:]]*$')

trimmed=$(printf '%s' "$section" | sed '/^[[:space:]]*$/d')

if [ -z "$trimmed" ] || [ "$trimmed" = "Single PR." ]; then
  echo "OK: PR Breakdown has nothing to validate (absent or Single PR.)."
  exit 0
fi

# Each PR Breakdown entry line looks like:
#   N. **[<status>] PR-N** — <title>. Tasks: <N, N>. Depends on: <none | PR-N, PR-M>.
# The label sits in the line's first **...** span; every PR-N token inside
# the "Depends on:" clause (up to the next period) becomes one dependency.
edges=$(printf '%s\n' "$section" | awk '
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

if [ -z "$edges" ]; then
  echo "error: PR Breakdown section found but no PR-N entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$edges" | "$script_dir/dag-check-helper.sh" PR
