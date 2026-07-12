#!/usr/bin/env bash
# normalize-list-breadcrumbs - upgrade a plan's coverage/task list titles to Test Design breadcrumbs.
#
# Usage:
#   normalize-list-breadcrumbs.sh <plan-path>
#
# Rewrites, IN PLACE, every `- "<title>"` bullet OUTSIDE fenced code whose quoted title is a
# bare it() title from the `## Test Design` section, replacing it with that test's breadcrumb
# (<describe> [> class] > it). Targets the two lists that cite tests — the AC -> test coverage
# list and each task's `**Tests (planned)**:` list — without needing to know their exact bounds:
# only real Test Design titles match, and Test Design's own `it("...")` lines live inside ```
# fences, so they are never touched.
#
# Why this exists: the breadcrumb is DERIVED from Test Design, so hand-typing it in the lists
# duplicates a source and drifts. Author the lists with bare it() titles (easy to eyeball
# against Test Design), then run this to upgrade them; the two gate scripts then verify.
#
# Idempotent: a bullet already holding a breadcrumb (which contains " > ") is not a bare title,
# so it does not match the map and is left unchanged. Safe to re-run.
#
# Reconstruction lives in ONE place: this reads bare->breadcrumb pairs from
# extract-design-tests.sh --pairs (the same script both gates use), never re-parsing describe/class.
#
# Exit codes:
#   0  - success (in-place rewrite done; count of rewritten bullets on stderr).
#   1  - the plan has no extractable Test Design titles (nothing to map).
#   2  - usage error (wrong arg count, plan file not found, sibling script missing).

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <plan-path>" >&2
  exit 2
fi

plan="$1"

if [ ! -f "$plan" ]; then
  echo "error: plan file not found: $plan" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
design_extract="$script_dir/extract-design-tests.sh"

if [ ! -x "$design_extract" ]; then
  echo "error: sibling script not found or not executable: $design_extract" >&2
  exit 2
fi

# bare<TAB>breadcrumb pairs from the shared reconstruction (single source of the format).
map_file="$(mktemp)"
trap 'rm -f "$map_file"' EXIT

if ! "$design_extract" --pairs "$plan" > "$map_file"; then
  echo "error: could not extract Test Design titles from $plan (see above)" >&2
  exit 1
fi

if [ ! -s "$map_file" ]; then
  echo "error: no Test Design titles found in $plan; nothing to normalize" >&2
  exit 1
fi

tmp_out="$(mktemp)"
trap 'rm -f "$map_file" "$tmp_out"' EXIT

awk -F'\t' '
  # Pass 1: load bare -> breadcrumb map.
  NR == FNR { if (NF >= 2) map[$1] = $2; next }

  # Pass 2: rewrite bullets outside fenced code.
  {
    line = $0

    if (line ~ /^[[:space:]]*```/) { infence = !infence; print line; next }

    # A citation bullet: <indent>- "<title>"<optional trailing tag>. Titles carry no ".
    if (!infence && match(line, /^[[:space:]]*-[[:space:]]+"/)) {
      prefix = substr(line, 1, RLENGTH)      # up to and including the opening quote
      rest   = substr(line, RLENGTH + 1)     # <title>"<trailing>
      q = index(rest, "\"")                  # closing quote position
      if (q > 0) {
        title    = substr(rest, 1, q - 1)
        trailing = substr(rest, q)           # from the closing quote onward
        if (title in map) {
          print prefix map[title] trailing
          changed++
          next
        }
      }
    }
    print line
  }
  END { print "bullets rewritten: " changed + 0 > "/dev/stderr" }
' "$map_file" "$plan" > "$tmp_out"

mv "$tmp_out" "$plan"
echo "map size: $(wc -l < "$map_file" | tr -d ' ') bare->breadcrumb pairs" >&2
