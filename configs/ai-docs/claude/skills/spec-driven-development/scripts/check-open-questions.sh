#!/usr/bin/env bash
# check-open-questions.sh - self-review validator: no Open
# Question is still unsettled.
#
# Usage:
#   check-open-questions.sh <plan-file> [<spec-file>]
#
# Extracts the "## Open Questions" section from each given
# document and fails while any "**QUESTION:**" entry survives in
# it.
#
# The spec argument is optional, so a plan-only run
# (brainstorm's `light` mode) passes the plan alone
# rather than inventing a spec path.
#
# Markers inside a ``` or ~~~ fenced code block are ignored: a
# doc quoting the template's own "- **QUESTION:** ... ?" line as
# an example is showing the syntax, not holding an unanswered
# question. scripts/parse-fences.awk decides what closes one.
#
# A document with no Open Questions section has nothing to
# settle and passes trivially, same as check-pr-dag.sh treats an
# absent PR Breakdown -- the section's presence is
# check-sections.sh's job, not this one's.
#
# Exit codes:
#   0 - every given document's Open Questions section is
#       settled.
#
#   1 - at least one "**QUESTION:**" entry survives
#       (diagnostic on stderr).
#
#   2 - usage error (wrong arg count, a named file
#       missing, or a ``` / ~~~ fence left open at EOF
#       in a given document, inherited from
#       plan-section.sh's whole-file fence check).
#
# The awk below loads parse-fences.awk with fence_indent=1,
# which exits 2 on an unclosed fence, new to this filter.
# plan-section.sh only checks column-0 fences, so an unclosed
# indented one (in a list item) still reaches it here.

set -eo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: $(basename "$0") <plan-file> [<spec-file>]" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for doc in "$@"; do
  if [ ! -f "$doc" ]; then
    echo "error: file not found: $doc" >&2
    exit 2
  fi
done

found=0

for doc in "$@"; do
  section=$("$script_dir/plan-section.sh" "$doc" "##" '^Open Questions[[:space:]]*$')

  # Drop fenced blocks before matching, so a quoted example
  # never counts.
  open=$(printf '%s\n' "$section" | awk -v fence_indent=1 \
    -f "$script_dir/../../../scripts/parse-fences.awk" \
    -f "$script_dir/check-open-questions.awk")

  if [ -n "$open" ]; then
    found=1
    echo "unsettled Open Questions in $doc:" >&2
    printf '%s\n' "$open" >&2
  fi
done

exit "$found"
