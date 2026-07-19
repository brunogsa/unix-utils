#!/usr/bin/env bash
# plan-section.sh - extract one heading's section body from a plan_<slug>.md file.
#
# Usage:
#   plan-section.sh <plan-file> <marker> <heading-pattern>
#
# <marker> is the heading prefix delimiting sections at the level being sliced
# ("##" for a plan's top-level sections, "###" for per-task sub-headings).
# <heading-pattern> is an ERE tested against the heading line with "<marker> "
# already stripped from its start — anchor it yourself (^...$) for an exact
# match (a fixed section name), or leave it unanchored at the end for a
# prefix match (a dynamic heading like a task number).
#
# Pass a literal dot in <heading-pattern> as a bracket expression ([.]), never
# a backslash escape (\.) — awk's -v assignment runs C-style escape
# processing on the value, so "\\." silently degrades to "match any char" on
# several awk implementations, including the default awk on macOS. "[.]"
# survives -v intact on every awk and means the same thing.
#
# Extracts from the first line at <marker> depth whose stripped text matches
# <heading-pattern>, through the line before the next <marker>-depth heading
# (or EOF). A deeper subheading (e.g. a "### " line inside a "##" section)
# does not end the section — only another heading at the SAME <marker> depth
# does, matching the per-script awk state machines this helper replaces.
#
# Exit codes:
#   0 - always, including "no heading matched" (empty stdout, same as before
#       this extraction). The awk itself can't fail on well-formed input;
#       callers keep owning their own "empty means error" vs "empty means
#       N/A" interpretation.
#   2 - usage error (wrong arg count, plan file missing).

set -eo pipefail

if [ $# -ne 3 ]; then
  echo "usage: $(basename "$0") <plan-file> <marker> <heading-pattern>" >&2
  exit 2
fi

plan_file="$1"
marker="$2"
heading_pattern="$3"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

awk -v marker="$marker" -v pat="$heading_pattern" '
  index($0, marker " ") == 1 {
    if (in_section) exit
    stripped = $0
    sub("^" marker " ", "", stripped)
    if (stripped ~ pat) { in_section = 1; next }
    next
  }
  in_section { print }
' "$plan_file"
