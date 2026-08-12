#!/usr/bin/env bash
# check-density.sh — flag markdown lines exceeding density caps.
#
# AI-consumed output (compact, parseable):
#   <line>:<chars>:<words>      one per violation
#   == <filename>               header (for each file that has hits)
#
# Caps default to 256 chars / 32 words per line (override with flags).
#
# Skips: leading YAML frontmatter (--- ... ---), fenced code blocks (``` or ~~~),
# blank lines, table rows, HTML-tag-only lines, link-only lines (a single
# "[text](url)" with optional list/quote marker).
#
# Frontmatter is skipped because its keys are router/tooling metadata, not prose:
# a `description:` scalar can't obey the "split on a sentence boundary" remedy, and
# its real cap is the skill-router budget (~first 250 chars), not the word count.
#
# Char/word counts are measured AFTER stripping `(https://…)` and `(data:…)` URI
# portions and remaining `[`/`]` brackets — so "[label](url)" measures as "label"
# and a base64 image — inline `![alt](data:…)` or reference def `[id]: <data:…>` —
# collapses to its label, giving the rendered density a reader actually sees.
#
# Usage:
#   check-density.sh [--max-chars N] [--max-words N] [--changed-only] <file> [<file>...]
#
# --changed-only scopes violations to lines changed-lines.sh reports as
# changed vs git HEAD (see that script's own docstring for what counts
# as changed) — an out-of-scope violation is never printed and never
# counts toward the exit code. Scope is recomputed fresh per file on
# every run; nothing is cached. When changed-lines.sh itself fails for
# a file (not a git repo, missing file), this script exits 2 and names
# the file, rather than treating that file as clean or as fully in
# scope.
#
# Exit codes:
#   0  clean (no in-scope violations)
#   1  in-scope violations found
#   2  usage error, or --changed-only failed to scope a file
#
# Examples:
#   check-density.sh pr-description.md
#   check-density.sh --max-chars 200 spec_<slug>.md plan_<slug>.md
#   check-density.sh --max-words 24 README.md
#   check-density.sh --changed-only spec_<slug>.md

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MAX_CHARS=256
MAX_WORDS=32
CHANGED_ONLY=0
FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-chars) MAX_CHARS="${2:?}"; shift 2 ;;
    --max-words) MAX_WORDS="${2:?}"; shift 2 ;;
    --changed-only) CHANGED_ONLY=1; shift ;;
    --) shift; FILES+=("$@"); break ;;
    -*) echo "unknown opt: $1" >&2; exit 2 ;;
    *)  FILES+=("$1"); shift ;;
  esac
done

[[ ${#FILES[@]} -eq 0 ]] && { echo "usage: check-density.sh [--max-chars N] [--max-words N] [--changed-only] <file>..." >&2; exit 2; }

# check_one_file - runs the density awk program over a single file,
# restricting hits to CHANGED_CSV's line numbers when scoped is "1".
# Kept per-file (rather than one awk invocation over every FILES
# entry) because --changed-only needs a distinct changed-line set per
# file, and awk has no clean way to key a per-file array off ARGV.
check_one_file() {
  local file="$1" scoped="$2" changed_csv="$3"
  awk -v mc="$MAX_CHARS" -v mw="$MAX_WORDS" -v scoped="$scoped" -v changed_csv="$changed_csv" '
    BEGIN {
      if (scoped && changed_csv != "") {
        n = split(changed_csv, nums, ",")
        for (i = 1; i <= n; i++) changed[nums[i]] = 1
      }
    }
    FNR == 1 { in_code = 0; in_fm = 0 }
    FNR == 1 && /^---[[:space:]]*$/                               { in_fm = 1; next }
    in_fm && /^---[[:space:]]*$/                                  { in_fm = 0; next }
    in_fm                                                         { next }
    /^[[:space:]]*(```|~~~)/                                      { in_code = !in_code; next }
    in_code                                                       { next }
    /^[[:space:]]*$/                                              { next }
    /^[[:space:]]*\|/                                             { next }
    /^[[:space:]]*<\/?[a-zA-Z][^>]*>[[:space:]]*$/                { next }
    /^[[:space:]]*([>*+-]|[0-9]+\.)?[[:space:]]*\[[^]]+\]\([^)]+\)[[:space:]]*\.?[[:space:]]*$/ { next }
    {
      gsub(/\(https?:\/\/[^)]*\)/, "")
      gsub(/[(<]data:[^)>]*[)>]/, "")
      gsub(/[][]/, "")
      if (length($0) > mc || NF > mw) {
        if (scoped && !(FNR in changed)) next
        printf "%d:%d:%d\n", FNR, length($0), NF
        hit = 1
      }
    }
    END { exit hit ? 1 : 0 }
  ' "$file"
}

err_file=$(mktemp)
trap 'rm -f "$err_file"' EXIT

overall_hit=0
prev_had_hit=0

for f in "${FILES[@]}"; do
  changed_csv=""
  if [[ $CHANGED_ONLY -eq 1 ]]; then
    if ! lines=$("$script_dir/changed-lines.sh" "$f" 2>"$err_file"); then
      echo "check-density.sh: cannot scope $f: $(cat "$err_file")" >&2
      exit 2
    fi
    changed_csv="${lines//$'\n'/,}"
  fi

  if out=$(check_one_file "$f" "$CHANGED_ONLY" "$changed_csv"); then
    rc=0
  else
    rc=$?
  fi

  if [[ $rc -eq 1 ]]; then
    overall_hit=1
    [[ $prev_had_hit -eq 1 ]] && echo
    echo "== $f"
    printf '%s\n' "$out"
    prev_had_hit=1
  elif [[ $rc -ne 0 ]]; then
    printf '%s\n' "$out" >&2
    exit "$rc"
  fi
done

exit "$overall_hit"
