#!/usr/bin/env bash
# dag-check-helper - shared cycle / dangling-reference / duplicate-label detector.
#
# Usage:
#   <label>\t<dep1,dep2,...> lines on stdin | dag-check-helper.sh <kind>
#
# Input: one TSV line per node — `<label><TAB><comma-separated deps, empty when none>`.
# `<kind>` is a short noun (e.g. "PR", "task") used only in diagnostics, so
# check-pr-dag.sh and check-tasks-dag.sh can share this ONE detection algorithm
# without this script knowing which breakdown section it's validating.
#
# Detects, over the input graph:
#   DUPLICATE  - the same label appears on more than one input line.
#   DANGLING   - a dependency names a label absent from the input's own labels.
#   CYCLE      - a dependency chain returns to a label already on its own path
#                (a standard white/gray/black DFS over the whole graph).
#
# All three checks run independently and every failure is reported together —
# not fail-fast on the first one found — so one bad edit doesn't hide a second.
#
# Exit codes:
#   0 - no duplicate, dangling reference, or cycle found.
#   1 - at least one of the three found (diagnostics printed to stderr).
#   2 - usage error (wrong arg count, empty stdin).

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <kind>" >&2
  echo "  reads TSV lines <label><TAB><deps> from stdin (deps comma-separated, empty when none)" >&2
  exit 2
fi

kind="$1"
input=$(cat)

if [ -z "$input" ]; then
  echo "error: no input lines on stdin (expected <label><TAB><deps> pairs)" >&2
  exit 2
fi

fail=0

# DUPLICATE: a label appearing on more than one input line.
duplicates=$(printf '%s\n' "$input" | cut -f1 | sort | uniq -d)

if [ -n "$duplicates" ]; then
  fail=1
  echo "FAIL (duplicate $kind label): appears on more than one entry:" >&2
  printf '%s\n' "$duplicates" | sed 's/^/  - /' >&2
fi

# DANGLING: a dependency naming a label absent from the input's own label set.
labels=$(printf '%s\n' "$input" | cut -f1 | sort -u)

dangling=$(printf '%s\n' "$input" | awk -F'\t' '
  {
    label = $1
    n = split($2, arr, ",")
    for (i = 1; i <= n; i++) {
      d = arr[i]
      gsub(/^[ \t]+|[ \t]+$/, "", d)
      if (d != "") print label "\t" d
    }
  }
' | while IFS=$'\t' read -r label dep; do
  if ! printf '%s\n' "$labels" | grep -qxF "$dep"; then
    echo "$label -> $dep"
  fi
done)

if [ -n "$dangling" ]; then
  fail=1
  echo "FAIL (dangling $kind reference): dependency names a label absent from the breakdown:" >&2
  printf '%s\n' "$dangling" | sed 's/^/  - /' >&2
fi

# CYCLE: white/gray/black DFS over the whole graph. A dangling dependency (not
# a key in `deps`) is skipped here — it's already reported above, and walking
# into it would need a fabricated node the diagnostic would misname.
cycle=$(printf '%s\n' "$input" | awk -F'\t' '
  function dfs(node,   n, arr, i, d, res) {
    color[node] = 1
    n = split(deps[node], arr, ",")
    for (i = 1; i <= n; i++) {
      d = arr[i]
      gsub(/^[ \t]+|[ \t]+$/, "", d)
      if (d == "" || !(d in deps)) continue
      if (color[d] == 1) { return node " -> " d }
      if (color[d] != 2) {
        res = dfs(d)
        if (res != "") return node " -> " res
      }
    }
    color[node] = 2
    return ""
  }
  { deps[$1] = $2 }
  END {
    for (l in deps) {
      if (!(l in color)) {
        res = dfs(l)
        if (res != "") { print res; exit }
      }
    }
  }
')

if [ -n "$cycle" ]; then
  fail=1
  echo "FAIL (cyclic $kind dependency): a dependency chain returns to its own start:" >&2
  echo "  - $cycle" >&2
fi

if [ "$fail" -eq 0 ]; then
  count=$(printf '%s\n' "$labels" | grep -c . || true)
  echo "OK: $count $kind label(s), no cycle, dangling reference, or duplicate label."
  exit 0
fi

exit 1
