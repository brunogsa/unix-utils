#!/usr/bin/env bash
# check-mermaid-renders.sh - self-review validator: every
# mermaid diagram in a document renders.
#
# Usage:
#   check-mermaid-renders.sh <doc-path>
#
# Extracts every ``` / ~~~ fenced block whose info string is
# `mermaid` and renders each one with `mmdc`.
#
# A fence opens on 3+ backticks or 3+ tildes and closes only on
# that same character, the fence rule check-sections.sh and
# check-ac-task-consistency.py already use.
#
# So a ```mermaid line quoted inside an outer ~~~ block is
# sample markup, not a diagram to render.
#
# A document with no mermaid block passes trivially: the check
# is "every diagram renders", and a doc with no diagram
# satisfies it.
#
# Exit codes:
#   0 - every mermaid block rendered (verdict on stdout).
#
#   1 - at least one block failed to render. Each failure
#       prints the source document line its fence opened on,
#       plus the error `mmdc` returned (stderr).
#
#   2 - usage error (wrong arg count, file not found, a
#       ``` / ~~~ fence left open at EOF), or `mmdc` not
#       installed.

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <doc-path>" >&2
  exit 2
fi

doc="$1"

if [ ! -f "$doc" ]; then
  echo "error: file not found: $doc" >&2
  exit 2
fi

# mmdc is a hard dependency, never a skip: install.sh installs
# @mermaid-js/mermaid-cli, and a silent skip is the exact
# failure this check exists to remove.
if ! command -v mmdc >/dev/null 2>&1; then
  echo "error: mmdc not found on PATH; install it by running install.sh (it installs @mermaid-js/mermaid-cli)." >&2
  exit 2
fi

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

# Writes one block-<n>.mmd per mermaid block into work_dir, plus
# a manifest of "<n> <opening-line-number>" rows.
#
# Toggling in_fence on every fence line means an unbalanced
# fence is caught at EOF rather than silently splitting the
# rest of the document into phantom blocks.
awk -v dir="$work_dir" '
  function start_of_fence(   marker) {
    if (!match($0, /^[ \t]*(```+|~~~+)/)) return ""
    marker = substr($0, RSTART, RLENGTH)
    sub(/^[ \t]*/, "", marker)
    return marker
  }

  {
    marker = start_of_fence()

    if (marker != "") {
      ch = substr(marker, 1, 1)
      fence_run = length(marker)
      fence_tail = substr($0, RSTART + RLENGTH)

      if (in_fence) {
        if (ch == fence_char && fence_run >= fence_len && fence_tail ~ /^[ \t]*$/) {
          in_fence = 0
          in_mermaid = 0
        } else if (in_mermaid) {
          print >> block_file
        }
        next
      }

      in_fence = 1
      fence_char = ch
      fence_len = fence_run
      fence_line = NR

      info = fence_tail
      gsub(/[ \t]/, "", info)

      if (info == "mermaid") {
        in_mermaid = 1
        count++
        block_file = dir "/block-" count ".mmd"
        printf "%d %d\n", count, NR >> (dir "/manifest.txt")
      }
      next
    }

    if (in_mermaid) print >> block_file
  }

  END {
    if (in_fence) {
      print "error: unclosed code fence opened at line " fence_line " in " FILENAME > "/dev/stderr"
      exit 2
    }
    print count + 0 > (dir "/count.txt")
  }
' "$doc"

block_count=$(cat "$work_dir/count.txt")

if [ "$block_count" -eq 0 ]; then
  echo "OK: no mermaid diagrams to check in $(basename "$doc")."
  exit 0
fi

failed=0

while read -r index fence_line; do
  render_err="$work_dir/block-$index.err"

  if mmdc -i "$work_dir/block-$index.mmd" -o "$work_dir/block-$index.svg" \
      >/dev/null 2>"$render_err"; then
    continue
  fi

  failed=$((failed + 1))
  echo "FAIL: the mermaid diagram opened at $doc:$fence_line does not render:" >&2

  # Drop puppeteer's stack frames: the parse error above them is
  # the only part naming the offending diagram line.
  grep -vE '^[[:space:]]*at |^Parser\.parseError' "$render_err" \
    | sed '/^[[:space:]]*$/d' \
    | sed 's/^/  /' >&2
done < "$work_dir/manifest.txt"

if [ "$failed" -gt 0 ]; then
  echo "$failed of $block_count mermaid diagrams in $(basename "$doc") failed to render." >&2
  echo "Dispatch the mermaid-fixer agent on $doc to repair them." >&2
  exit 1
fi

echo "OK: all $block_count mermaid diagrams render in $(basename "$doc")."
exit 0
