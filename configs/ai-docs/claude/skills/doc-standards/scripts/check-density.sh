#!/usr/bin/env bash
# check-density.sh — flag markdown lines exceeding density caps.
#
# AI-consumed output (compact, parseable):
#   <line>:<chars>:<words>      one per violation
#   == <filename>               header (only when multiple files have hits)
#
# Caps default to 256 chars / 32 words per line (override with flags).
#
# Skips: fenced code blocks (``` … ```), blank lines, table rows, HTML-tag-only
# lines, link-only lines (a single "[text](url)" with optional list/quote marker).
#
# Char/word counts are measured AFTER stripping `(https://…)` URL portions and
# remaining `[`/`]` brackets — so "[label](url)" measures as "label", giving the
# rendered density a reader actually sees.
#
# Usage:
#   check-density.sh [--max-chars N] [--max-words N] <file> [<file>...]
#
# Exit codes:
#   0  clean
#   1  violations found
#   2  usage error
#
# Examples:
#   check-density.sh pr-description.md
#   check-density.sh --max-chars 200 spec.md plan.md
#   check-density.sh --max-words 24 README.md

set -euo pipefail

MAX_CHARS=256
MAX_WORDS=32
FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-chars) MAX_CHARS="${2:?}"; shift 2 ;;
    --max-words) MAX_WORDS="${2:?}"; shift 2 ;;
    --) shift; FILES+=("$@"); break ;;
    -*) echo "unknown opt: $1" >&2; exit 2 ;;
    *)  FILES+=("$1"); shift ;;
  esac
done

[[ ${#FILES[@]} -eq 0 ]] && { echo "usage: check-density.sh [--max-chars N] [--max-words N] <file>..." >&2; exit 2; }

awk -v mc="$MAX_CHARS" -v mw="$MAX_WORDS" '
  FNR == 1 { in_code = 0 }
  /^[[:space:]]*```/                                            { in_code = !in_code; next }
  in_code                                                       { next }
  /^[[:space:]]*$/                                              { next }
  /^[[:space:]]*\|/                                             { next }
  /^[[:space:]]*<\/?[a-zA-Z][^>]*>[[:space:]]*$/                { next }
  /^[[:space:]]*([>*+-]|[0-9]+\.)?[[:space:]]*\[[^]]+\]\([^)]+\)[[:space:]]*\.?[[:space:]]*$/ { next }
  {
    gsub(/\(https?:\/\/[^)]*\)/, "")
    gsub(/[][]/, "")
    if (length($0) > mc || NF > mw) {
      if (FILENAME != prev) { if (prev != "") print ""; print "== " FILENAME; prev = FILENAME }
      printf "%d:%d:%d\n", FNR, length($0), NF
      hit = 1
    }
  }
  END { exit hit ? 1 : 0 }
' "${FILES[@]}"
