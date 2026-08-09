#!/usr/bin/env bash
# check-coverage-checklists.sh - self-review validator: every
# AC-category checklist instantiates each canonical taxonomy row.
#
# Usage:
#   check-coverage-checklists.sh <spec-file> [<taxonomy-file>]
#
# <taxonomy-file> defaults to the canonical coverage taxonomy at
# test-standards/references/coverage-taxonomy.md, resolved next to
# this script first (spec-driven-development and test-standards are
# sibling skill dirs in both the repo source and the ~/.claude
# symlink), falling back to the $HOME-anchored path only when that
# relative file is missing.
#
# spec-template.md's "#### Corner cases" and "#### Failure modes"
# each carry a checklist: one row per taxonomy item. Failure modes
# also absorbs the taxonomy's Async delivery rows -- its own
# classification note files those under failure modes, not corner
# cases.
#
# Extraction is two-staged: "## Testable Acceptance Criteria" bounds
# the search first, then "#### Corner cases" / "#### Failure modes"
# is sliced from that bounded text. plan-section.sh only stops at a
# heading of the SAME depth, and Failure modes has no later "#### "
# sibling to stop it -- without the outer bound its slice would run
# past Open Questions to EOF.
#
# Each row must read "covered (<recap>)" or "N/A - <one-word
# reason>". A category with nothing under its heading has no
# checklist to check and passes trivially, same as check-pr-dag.sh
# treats an absent PR Breakdown.
#
# Whole-checklist opt-out: a line starting with "**DECISION:** Skip
# <name> checklist because <reason>" satisfies a category outright,
# but ONLY when zero canonical rows were matched -- real rows found
# are validated regardless, the same discipline check-pr-dag.sh
# applies to its own N/A escape. Anchoring the marker to line-start
# also keeps the template's own instructional example ("Opt-out:
# replace the checklist with `**DECISION:** ...`") from reading as a
# real decision -- that sentence starts with "Opt-out:", not
# "**DECISION:**".
#
# A row quoted inside a fenced code block is sample content, not a
# real entry, and is dropped before scanning (mirrors
# check-open-questions.sh).
#
# Exit codes:
#   0 - every checklist present is complete, or nothing to check.
#   1 - a missing, extra, or malformed row was found (on stderr).
#   2 - usage error (wrong arg count, spec/taxonomy file missing).

set -eo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: $(basename "$0") <spec-file> [<taxonomy-file>]" >&2
  exit 2
fi

spec_file="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "${2:-}" ]; then
  taxonomy_file="$2"
else
  # Sibling-dir path works from both the repo source and the
  # ~/.claude symlink; only fall back when it doesn't resolve.
  default_taxonomy="$script_dir/../../test-standards/references/coverage-taxonomy.md"
  if [ -f "$default_taxonomy" ]; then
    taxonomy_file="$default_taxonomy"
  else
    taxonomy_file="$HOME/.claude/skills/test-standards/references/coverage-taxonomy.md"
  fi
fi

for f in "$spec_file" "$taxonomy_file"; do
  if [ ! -f "$f" ]; then
    echo "error: file not found: $f" >&2
    exit 2
  fi
done

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

# strip_fences - drop ``` regions so a quoted example row is never
# read as a real entry.
strip_fences() {
  awk '/^```/ { f = !f; next } f { next } { print }'
}

# labels_under - flat "- " taxonomy rows filed under a "## "
# heading. Unanchored pattern so a heading with a parenthetical
# suffix (e.g. "Corner cases (data-shape boundaries)") still matches.
labels_under() {
  "$script_dir/plan-section.sh" "$taxonomy_file" "##" "$1" \
    | strip_fences \
    | awk '/^- / { sub(/^- /, ""); print }'
}

labels_under '^Corner cases' > "$work_dir/corner-labels.txt"
labels_under '^Failure modes' > "$work_dir/failure-labels.txt"

# ac_section - written to a file because plan-section.sh needs a
# real path; this is the outer bound described above.
ac_section=$("$script_dir/plan-section.sh" "$spec_file" "##" \
  '^Testable Acceptance Criteria[[:space:]]*$')

violations_found=0

# check_category - validates one checklist against its taxonomy
# labels; sets violations_found=1 on any defect. $1 name (used in
# both messages and the opt-out phrase), $2 "#### " heading pattern,
# $3 canonical-labels file.
check_category() {
  local name="$1" heading_pattern="$2" labels_file="$3"

  local full_section
  full_section=$("$script_dir/plan-section.sh" "$ac_section_file" \
    "####" "$heading_pattern")
  [ -z "$full_section" ] && return 0

  local fenced_free
  fenced_free=$(printf '%s\n' "$full_section" | strip_fences)

  # Cut before the first AC heading so an AC's own Given/When/Then
  # bullets are never read as checklist rows.
  local narrow_window
  narrow_window=$(printf '%s\n' "$fenced_free" \
    | awk '/^### / { exit } { print }')

  local scan
  scan=$(printf '%s\n' "$narrow_window" | awk -v labels_file="$labels_file" '
    BEGIN {
      while ((getline line < labels_file) > 0) labels[++n] = line
      close(labels_file)
    }
    /^- / {
      bullet = $0
      sub(/^- /, "", bullet)
      matched = 0
      for (i = 1; i <= n; i++) {
        prefix = labels[i] ":"
        if (index(bullet, prefix) == 1) {
          value = substr(bullet, length(prefix) + 1)
          gsub(/^[ \t]+/, "", value)
          gsub(/[ \t]+$/, "", value)
          print "MATCH\t" labels[i] "\t" value
          matched = 1
          break
        }
      }
      if (!matched) print "EXTRA\t" bullet
    }
  ')

  local matched_count
  matched_count=$(printf '%s\n' "$scan" \
    | awk -F'\t' '$1 == "MATCH" { c++ } END { print c + 0 }')

  if [ "$matched_count" -eq 0 ]; then
    # Only reachable when NO real row was found -- see the header
    # comment on why the escape can't disarm rows already present.
    if printf '%s\n' "$fenced_free" | grep -qE \
        "^[[:space:]]*(-[[:space:]]+)?\\*\\*DECISION:\\*\\* Skip ${name} checklist because [^[:space:]]"; then
      echo "OK: $name checklist opted out (DECISION marker)."
      return 0
    fi
    echo "FAIL: $name checklist has no rows and no opt-out:" >&2
    while IFS= read -r label; do
      [ -n "$label" ] && echo "  - missing: $label" >&2
    done < "$labels_file"
    violations_found=1
    return 0
  fi

  local any_bad=0

  while IFS= read -r label; do
    [ -z "$label" ] && continue
    local count value
    count=$(printf '%s\n' "$scan" | awk -F'\t' -v l="$label" \
      '$1 == "MATCH" && $2 == l { c++ } END { print c + 0 }')
    if [ "$count" -eq 0 ]; then
      echo "  - missing: $label" >&2
      any_bad=1
    elif [ "$count" -gt 1 ]; then
      echo "  - extra (instantiated $count times): $label" >&2
      any_bad=1
    else
      value=$(printf '%s\n' "$scan" | awk -F'\t' -v l="$label" \
        '$1 == "MATCH" && $2 == l { print $3 }')
      if ! printf '%s' "$value" \
          | grep -qE '^covered \(.+\)$|^N/A — [^[:space:]]+$'; then
        echo "  - malformed: $label -> \"$value\"" >&2
        any_bad=1
      fi
    fi
  done < "$labels_file"

  while IFS= read -r bullet; do
    [ -z "$bullet" ] && continue
    echo "  - extra (unrecognized row): $bullet" >&2
    any_bad=1
  done < <(printf '%s\n' "$scan" | awk -F'\t' '$1 == "EXTRA" { print $2 }')

  if [ "$any_bad" -eq 1 ]; then
    echo "FAIL: $name checklist has violations (above)." >&2
    violations_found=1
  else
    echo "OK: $name checklist is complete."
  fi
}

if [ -n "$ac_section" ]; then
  ac_section_file="$work_dir/ac-section.md"
  printf '%s\n' "$ac_section" > "$ac_section_file"

  check_category "boundary" '^Corner cases[[:space:]]*$' \
    "$work_dir/corner-labels.txt"
  check_category "failure-category" '^Failure modes[[:space:]]*$' \
    "$work_dir/failure-labels.txt"
fi

exit "$violations_found"
