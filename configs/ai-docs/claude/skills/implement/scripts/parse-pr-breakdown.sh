#!/usr/bin/env bash
# parse-pr-breakdown.sh - shared PR Breakdown parser: extracts <plan-file>'s
# "## PR Breakdown" section and emits one TSV line per PR-N entry found in it.
#
# Usage:
#   parse-pr-breakdown.sh <plan-file>
#
# stdin: unused
# stdout: one line per PR-N entry, as
#   <label><TAB><tasks><TAB><deps><TAB><branch>
# exit: 0 entries printed; 1 section absent or "Single PR."; 2 usage error,
#       or the section has content but no PR-N entry could be parsed.
#
# The entry grammar is authored by the spec-driven-development skill's
# assets/plan-template.md; how each caller uses these fields is in
# implement/references/pr-awareness.md.

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

# A plan authored before the heading grammar labels its PRs in a bold span on
# a list line instead. Picking the boundary from what the section actually
# contains keeps those plans parsable through their own execution, and stops a
# bolded PR-N inside a heading-grammar plan's prose from opening a phantom entry.
if printf '%s\n' "$section" | grep -qE '^###[[:space:]].*PR-[0-9]+'; then
  entry_boundary="heading"
else
  entry_boundary="bold-span"
fi

entries=$(printf '%s\n' "$section" | awk -v entry_boundary="$entry_boundary" '
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

  # A named field with or without its bold markers, up to the next period or
  # the end of the line - whichever comes first. Both terminators are needed:
  # the heading grammar ends a field at the line break, while the older
  # one-line grammar packs every field onto one line, separated by periods.
  function field(line, name,   raw) {
    if (!match(line, "\\*?\\*?" name "\\*?\\*?:[^.]*")) return ""
    raw = substr(line, RSTART, RLENGTH)
    sub(/^[^:]*:/, "", raw)
    gsub(/^[ \t]+|[ \t]+$/, "", raw)
    return raw
  }

  function pr_tokens(clause,   tokens, token) {
    tokens = ""
    while (match(clause, /PR-[0-9]+/)) {
      token = substr(clause, RSTART, RLENGTH)
      tokens = (tokens == "" ? token : tokens "," token)
      clause = substr(clause, RSTART + RLENGTH)
    }
    return tokens
  }

  function branch_name(line,   clause) {
    if (!match(line, /\*?\*?Branch\*?\*?:[ \t]*`[^`]*`/)) return ""
    clause = substr(line, RSTART, RLENGTH)
    match(clause, /`[^`]*`/)
    return substr(clause, RSTART + 1, RLENGTH - 2)
  }

  function flush() {
    if (label != "") print label "\t" tasks "\t" deps "\t" branch
  }

  {
    opening_label = entry_label($0)
    if (opening_label != "") {
      flush()
      label = opening_label
      tasks = ""; deps = ""; branch = ""
      seen_tasks = 0; seen_deps = 0
    }
    if (label == "") next

    # First occurrence wins: past the fields, an entry runs into free prose
    # that may name a task or a PR without redefining either.
    if (!seen_tasks) {
      tasks = field($0, "Tasks")
      if (tasks != "") seen_tasks = 1
    }
    if (!seen_deps) {
      deps_clause = field($0, "Depends on")
      if (deps_clause != "") {
        deps = pr_tokens(deps_clause)
        seen_deps = 1
      }
    }
    if (branch == "") branch = branch_name($0)
  }

  END { flush() }
')

if [ -z "$entries" ]; then
  echo "error: PR Breakdown section found but no PR-N entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$entries"
