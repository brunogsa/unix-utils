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
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fences_lib="$script_dir/../../../scripts/parse-fences.awk"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

# The shared fence scanner (parse-fences.awk) sets in_fence.
# The section program uses it only to guard the `## ` boundary,
# and never skips content.
#
# A fenced sample line quoted inside the section must still
# print. The scanner's END exits 2 on a fence left open at EOF.
section=$(awk -f "$fences_lib" -f "$script_dir/parse-pr-breakdown-section.awk" "$plan_file")

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

# Loading parse-fences.awk here brought an exit 2 on an
# unclosed fence that this awk program did not have before.
# The section awk above rejects an unbalanced plan first, which
# masks it; reordering or dropping that step exposes it.
entries=$(printf '%s\n' "$section" | awk -v entry_boundary="$entry_boundary" \
  -f "$fences_lib" -f "$script_dir/parse-pr-breakdown-entries.awk")

if [ -z "$entries" ]; then
  echo "error: PR Breakdown section found but no PR-N entries could be parsed from it" >&2
  exit 2
fi

printf '%s\n' "$entries"
