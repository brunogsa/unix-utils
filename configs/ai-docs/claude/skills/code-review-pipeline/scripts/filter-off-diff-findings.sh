#!/usr/bin/env bash
# filter-off-diff-findings - keep only findings whose whole line range is commentable
#
# Usage:
#   filter-off-diff-findings <findings-json> <commentable-lines-file>
#
# A finding survives when every line from `start_line` through `line` appears in
# the commentable-lines set. Surviving findings go to stdout as a JSON array;
# dropped ones go to stderr as `path:start-end — <first 80 chars of body>`, the
# shape Wave 6's drop log prints.
#
# Examples:
#   filter-off-diff-findings "$work_dir/wave3-findings.json" "$work_dir/commentable-lines.txt" \
#     > "$work_dir/wave4-findings.json"
#   filter-off-diff-findings f.json lines.txt 2> /tmp/dropped.txt

set -euo pipefail

if [[ $# -ne 2 || "$1" == "-h" || "$1" == "--help" ]]; then
  sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

findings_file="$1"
lines_file="$2"

command -v jq >/dev/null || { echo "filter-off-diff-findings: jq not found" >&2; exit 1; }

for f in "$findings_file" "$lines_file"; do
  [[ -r "$f" ]] || { echo "filter-off-diff-findings: cannot read $f" >&2; exit 1; }
done

# An empty commentable set drops every finding. That is a real outcome (a diff of
# pure deletions has no addable lines), but it is indistinguishable from a Wave 1
# extraction failure, so say which one the caller is looking at.
if [[ ! -s "$lines_file" ]]; then
  echo "filter-off-diff-findings: $lines_file is empty — every finding will drop" >&2
fi

partitioned=$(jq -n \
  --slurpfile findings "$findings_file" \
  --rawfile lines "$lines_file" '
  ($lines | split("\n") | map(select(length > 0)) | INDEX(.)) as $ok
  | ($findings[0] // [])
  | map(. as $f
      | .__keep = (
          ($f.start_line != null and $f.line != null)
          and all(range($f.start_line; $f.line + 1); $ok["\($f.path):\(.)"] != null)
        ))
  | { kept:    map(select(.__keep)      | del(.__keep)),
      dropped: map(select(.__keep | not) | del(.__keep)) }
')

jq -r '.dropped[] | "\(.path):\(.start_line)-\(.line) — \((.body // "")[0:80])"' \
  <<<"$partitioned" >&2

jq '.kept' <<<"$partitioned"
