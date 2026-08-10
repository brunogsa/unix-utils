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
# backward-compat escape for a single-PR plan), or that yields no PR-N
# entry at all while carrying the general per-section "N/A" escape
# (documented in references/self-review-checks.md), has nothing to
# validate and passes trivially, same as a plan with no PR Breakdown
# section at all.
#
# Exit codes:
#   0 - PR Breakdown is absent, reads "Single PR.", parses to no PR-N
#       entry under the "N/A" escape, or its dependency graph is a valid
#       DAG with no duplicate labels.
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

if [ -z "$trimmed" ]; then
  echo "OK: PR Breakdown has nothing to validate (section absent)."
  exit 0
fi

if [ "$trimmed" = "Single PR." ]; then
  echo "OK: PR Breakdown has nothing to validate (reads 'Single PR.')."
  exit 0
fi

# The entry grammar this parses - PR headings, their "Depends on" field, and
# the older one-line form still found in plans already under execution - is
# documented in assets/plan-template.md's PR Breakdown section.
#
# implement/scripts/parse-pr-breakdown.sh reads the same grammar for a
# different field set; the two stay in step by hand rather than by import,
# so that neither skill's checks depend on the other skill being installed.
if printf '%s\n' "$section" | grep -qE '^###[[:space:]].*PR-[0-9]+'; then
  entry_boundary="heading"
else
  entry_boundary="bold-span"
fi

edges=$(printf '%s\n' "$section" | awk -v entry_boundary="$entry_boundary" '
  # The label opening a new entry, or "" when this line opens none.
  function entry_label(line,   span) {
    if (entry_boundary == "heading") {
      if (line !~ /^###[ \t]/) return ""
      if (!match(line, /PR-[0-9]+/)) return ""
      return substr(line, RSTART, RLENGTH)
    }
    if (!match(line, /\*\*[^*]*PR-[0-9]+[^*]*\*\*/)) return ""
    span = substr(line, RSTART, RLENGTH)
    if (!match(span, /PR-[0-9]+/)) return ""
    return substr(span, RSTART, RLENGTH)
  }

  # The "Depends on" field with or without its bold markers, up to the next
  # period or the end of the line - whichever comes first. Both terminators
  # are needed: the heading grammar ends the field at the line break, while
  # the one-line grammar separates its fields with periods.
  function depends_clause(line,   raw) {
    if (!match(line, /\*?\*?Depends on\*?\*?:[^.]*/)) return ""
    raw = substr(line, RSTART, RLENGTH)
    sub(/^[^:]*:/, "", raw)
    gsub(/^[ \t]+|[ \t]+$/, "", raw)
    return raw
  }

  function flush() {
    if (label != "") print label "\t" deps
  }

  {
    opening_label = entry_label($0)
    if (opening_label != "") {
      flush()
      label = opening_label
      deps = ""
      seen_deps = 0
    }
    if (label == "" || seen_deps) next

    clause = depends_clause($0)
    if (clause == "") next
    seen_deps = 1

    # First occurrence wins: past its fields, an entry runs into free prose
    # that may name a PR without depending on it.
    while (match(clause, /PR-[0-9]+/)) {
      token = substr(clause, RSTART, RLENGTH)
      deps = (deps == "" ? token : deps "," token)
      clause = substr(clause, RSTART + RLENGTH)
    }
  }

  END { flush() }
')

if [ -z "$edges" ]; then
  # General per-section escape: an "N/A" body (case-insensitive,
  # word-boundary so "N/Ax" misses) has nothing to validate. Mirrors
  # extract-planned-tests-for-task.sh's own N/A short-circuit.
  #
  # It is tested HERE, after parsing, rather than against the raw body:
  # plan-template.md puts "N/A — no PR dependencies" in place of the
  # dependency DIAGRAM, which leads a real PR list. Testing the body
  # would let that line wave the whole list through unvalidated.
  if printf '%s' "$trimmed" | grep -qiE '^N/A([^a-zA-Z]|$)'; then
    echo "OK: PR Breakdown has nothing to validate (reads 'N/A — ...')."
    exit 0
  fi

  echo "error: PR Breakdown section found but no PR-N entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$edges" | "$script_dir/dag-check-helper.sh" PR
