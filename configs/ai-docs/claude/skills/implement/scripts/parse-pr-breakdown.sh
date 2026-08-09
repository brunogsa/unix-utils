#!/usr/bin/env bash
# parse-pr-breakdown.sh - shared PR Breakdown parser: extracts <plan-file>'s
# "## PR Breakdown" section and emits one TSV line per PR-N entry found in it.
#
# Usage:
#   parse-pr-breakdown.sh <plan-file>
#
# get-pr-tasks.sh, need-git-checkout.sh, and check-pr-dependencies-ready.sh
# all parse this same section and entry grammar, differing only in which
# field(s) each one consumes (Tasks / Depends on / both) - this script is
# their one shared parser, invoked as a piped subprocess exactly like
# dag-check-helper.sh (see check-pr-dag.sh), so each caller just `cut`s the
# field(s) it needs from stdout instead of re-deriving them.
#
# Each PR Breakdown entry line looks like:
#   N. **[<status>] PR-N** — <title>. Tasks: <N, N>. Depends on: <none | PR-N, PR-M>. Branch: `<name>`.
# The label sits in the line's first **...** span; the Tasks: and Depends
# on: clauses each run up to the next period.
#
# The Branch: clause is delimited by backticks rather than by the next
# period, because branch names legitimately contain periods
# (release/1.2), which a period-terminated clause would truncate.
# /implement writes it at push time, so it is absent until the PR's
# batch has actually pushed.
#
# Output: one line per PR-N entry, printed to stdout as
#   <label><TAB><tasks><TAB><deps><TAB><branch>
# - <tasks> is the Tasks: clause verbatim (e.g. "5, 6, 7"), empty if absent.
# - <deps> is a comma-separated list of PR-N tokens pulled from the Depends
#   on: clause (e.g. "PR-1,PR-2"), empty when the clause reads "none" or is
#   absent.
# - <branch> is the backtick-wrapped name from the Branch: clause, empty
#   when the clause is absent (this PR has not pushed yet).
#
# Exit codes:
#   0 - one or more PR-N entries found; printed to stdout.
#   1 - PR Breakdown section is absent, or reads "Single PR." (nothing to
#       parse - the plan's backward-compat single-PR escape hatch).
#   2 - usage error (wrong arg count, plan file missing), or the section has
#       content but no PR-N entries could be parsed from it.

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
  exit 1
fi

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

    deps = ""
    if (match(line, /Depends on:[^.]*/)) {
      clause = substr(line, RSTART + 11, RLENGTH - 11)
      while (match(clause, /PR-[0-9]+/)) {
        tok = substr(clause, RSTART, RLENGTH)
        deps = (deps == "" ? tok : deps "," tok)
        clause = substr(clause, RSTART + RLENGTH)
      }
    }
    branch = ""
    if (match(line, /Branch:[ \t]*`[^`]*`/)) {
      branch_clause = substr(line, RSTART, RLENGTH)
      match(branch_clause, /`[^`]*`/)
      branch = substr(branch_clause, RSTART + 1, RLENGTH - 2)
    }

    print label "\t" tasks "\t" deps "\t" branch
  }
')

if [ -z "$entries" ]; then
  echo "error: PR Breakdown section found but no PR-N entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$entries"
