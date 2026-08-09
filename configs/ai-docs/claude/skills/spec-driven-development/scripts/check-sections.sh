#!/usr/bin/env bash
# check-sections - verify a spec or plan carries every `## ` section its template defines.
#
# Usage:
#   check-sections.sh <doc-path> <template-path>
#
# SKILL.md's "Every template section always gets written": both templates are one fixed
# section set, there is no reduced variant, and a caller never picks which sections to write.
# A section the change doesn't need still gets its heading, with an `N/A — <reason>` line as
# its body — so this script checks HEADING PRESENCE only and never reads a section's contents.
#
# Why a heading and not an absence: a dropped section is invisible to the reader, where an
# `N/A` line states that the author considered it and ruled it out. Only the heading makes
# that distinction reviewable, which is exactly what a `grep` can settle for free.
#
# Missing-only, never extra: a template heading absent from the doc is the defect the rule
# names. An author-added heading is not addressed by that rule, so flagging one would invent
# a constraint the library never states.
#
# Both files are scanned fence-aware — a `## ` line inside a ``` block is sample content, not
# a section, and a plan's fenced shell snippets would otherwise satisfy a heading it lacks.
#
# Exit codes:
#   0  - every template section is present in the doc.
#   1  - at least one template section is missing (each printed to stderr).
#   2  - usage error (wrong arg count, file not found, or template defines no sections).

set -eo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $(basename "$0") <doc-path> <template-path>" >&2
  exit 2
fi

doc="$1"
template="$2"

for f in "$doc" "$template"; do
  if [ ! -f "$f" ]; then
    echo "error: file not found: $f" >&2
    exit 2
  fi
done

# headings - print every `## ` heading in a markdown file, skipping fenced regions.
# Toggling on every ``` line means an unbalanced fence swallows the tail rather than
# reporting phantom headings from inside it — failing toward "missing", which blocks.
headings() {
  awk '/^```/ { in_fence = !in_fence; next } !in_fence && /^## / { print }' "$1"
}

template_sections=$(headings "$template")

if [ -z "$template_sections" ]; then
  echo "error: template defines no '## ' sections: $template" >&2
  exit 2
fi

doc_sections=$(headings "$doc")

missing=$(comm -23 \
  <(printf '%s\n' "$template_sections" | sort -u) \
  <(printf '%s\n' "$doc_sections" | sort -u))

if [ -z "$missing" ]; then
  count=$(printf '%s\n' "$template_sections" | sort -u | wc -l | tr -d ' ')
  echo "OK: all $count template sections present in $(basename "$doc")."
  exit 0
fi

echo "FAIL: sections defined by $(basename "$template") but missing from $(basename "$doc"):" >&2
printf '%s\n' "$missing" | sed 's/^/  - /' >&2
echo "Write the heading with an 'N/A — <reason>' body rather than dropping it." >&2

exit 1
