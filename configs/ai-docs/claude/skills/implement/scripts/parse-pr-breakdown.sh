#!/usr/bin/env bash
# parse-pr-breakdown.sh - shared PR Breakdown parser: extracts
# <plan-file>'s "## PR Breakdown" section and emits one TSV line
# per PR-N entry found in it.
#
# Usage:
#   parse-pr-breakdown.sh <plan-file>
#
# stdin is not used.
#
# stdout: one line per PR-N entry, as
#   <label><TAB><tasks><TAB><deps><TAB><branch>
#
# exit: 0 entries printed; 1 section absent or "Single PR."; 2
# usage error, the section has content but no PR-N entry could
# be parsed, or a ``` / ~~~ fence is left open at EOF.
#
# The entry grammar is authored by the spec-driven-development
# skill's assets/plan-template.md; how each caller uses these
# fields is in implement/references/pr-awareness.md.
#
# Both the section boundary and the entry-heading match are
# fence-aware: a `## `/`### PR-N` line shown as sample markup
# inside a ``` or ~~~ fence never ends the section early or
# opens a phantom entry.

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

# The fence toggle guards only the `## ` boundary check below —
# it never skips content — since a fenced sample line quoted
# inside the section must still print as part of it. Closes
# only on the same marker (``` or ~~~) that opened it.
section=$(awk '
  /^```/ || /^~~~/ {
    m = substr($0, 1, 1)
    if (in_fence) { if (m == fence_char) in_fence = 0 }
    else { in_fence = 1; fence_char = m; fence_line = NR }
    if (in_section && !done) print
    next
  }
  !in_fence && !done && /^## / {
    if (in_section) { done = 1; next }
    if ($0 ~ /^## PR Breakdown[[:space:]]*$/) { in_section = 1; next }
    next
  }
  in_section && !done { print }
  END {
    if (in_fence) {
      print "error: unclosed code fence opened at line " fence_line " in " FILENAME > "/dev/stderr"
      exit 2
    }
  }
' "$plan_file")

trimmed=$(printf '%s' "$section" | sed '/^[[:space:]]*$/d')

if [ -z "$trimmed" ] || [ "$trimmed" = "Single PR." ]; then
  exit 1
fi

# A plan authored before the heading grammar labels its PRs in a
# bold span on a list line instead.
#
# Picking the boundary from what the section actually contains
# keeps those plans parsable through their own execution, and
# stops a bolded PR-N inside a heading-grammar plan's prose from
# opening a phantom entry.
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

  # A fenced sample entry (e.g. a ### PR-N heading shown as
  # doc-writing markup) is skipped entirely here, not just
  # boundary-guarded: its heading must never open a phantom
  # entry, and its field lines must never leak into a real
  # entry above it. Closes only on the same marker that opened it.
  /^```/ || /^~~~/ {
    m = substr($0, 1, 1)
    if (in_fence) { if (m == fence_char) in_fence = 0 }
    else { in_fence = 1; fence_char = m }
    next
  }
  in_fence { next }

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
