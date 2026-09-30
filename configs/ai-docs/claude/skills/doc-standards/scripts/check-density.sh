#!/usr/bin/env bash
# check-density.sh — flag markdown lines exceeding density caps.
#
# AI-consumed output (compact, parseable):
#   <line>:<chars>:<words>  one per violation
#   == <filename>           header (for each file that has hits)
#
# Two caps, chosen by line shape (override with flags):
#
# - prose line (no bullet marker): 512 chars / 64 words
#   (--max-chars/--max-words).
#
# - bullet/sub-bullet/ordered line: 256 chars / 32 words
#   (--bullet-chars/--bullet-words).
#
# A bullet line is one matching ^\s*([-*+]|\d+\.)\s (same
# shape check-hard-wrap.py uses), so an indented sub-bullet
# or an ordered "1." line both take the bullet cap, never
# the looser prose cap.
#
# Skips: leading YAML frontmatter (--- ... ---), fenced code
# blocks (``` or ~~~), blank lines, table rows,
# HTML-tag-only lines, link-only lines (a single "[text](url)"
# with optional list/quote marker).
#
# Frontmatter is skipped because its keys are router/tooling
# metadata, not prose: a `description:` scalar can't obey the
# "split on a sentence boundary" remedy, and its real cap is the
# skill-router budget (~first 250 chars), not the word count.
#
# Char/word counts are measured AFTER stripping `(https://…)`
# and `(data:…)` URI portions and remaining `[`/`]` brackets
# — so "[label](url)" measures as "label" and a base64 image.
#
# Inline `![alt](data:…)` or reference def `[id]: <data:…>` —
# collapses to its label, giving the rendered density a
# reader actually sees.
#
# Usage:
#   check-density.sh [--max-chars N] [--max-words N]
#     [--bullet-chars N] [--bullet-words N]
#     [--changed-only] <file> [<file>...]
#
# --changed-only scopes violations to lines get-changed-lines.sh
# reports as changed vs git HEAD (see that script's own
# docstring for what counts as changed).
#
# Out-of-scope violations are never printed and never count
# toward the exit code.
#
# Scope is recomputed fresh per file on every run; nothing is
# cached.
#
# When get-changed-lines.sh itself fails for a file (not a git
# repo, missing file), this script exits 2 and names the file,
# rather than treating that file as clean or as fully in scope.
#
# Exit codes:
#   0  clean (no in-scope violations)
#   1  in-scope violations found
#   2  failure, never a clean or findings result
#
# Exit 2 covers:
# - a usage error, or --changed-only failing to scope a file
# - a file that is missing, unreadable or not valid UTF-8
# - iconv being unavailable.
#
# Examples:
# - check-density.sh pr-description.md
# - check-density.sh --max-chars 200 spec_<slug>.md
#   plan_<slug>.md.
#
# - check-density.sh --max-words 24 README.md
# - check-density.sh --changed-only spec_<slug>.md

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MAX_CHARS=512
MAX_WORDS=64
BULLET_CHARS=256
BULLET_WORDS=32
CHANGED_ONLY=0
FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-chars) MAX_CHARS="${2:?}"; shift 2 ;;
    --max-words) MAX_WORDS="${2:?}"; shift 2 ;;
    --bullet-chars) BULLET_CHARS="${2:?}"; shift 2 ;;
    --bullet-words) BULLET_WORDS="${2:?}"; shift 2 ;;
    --changed-only) CHANGED_ONLY=1; shift ;;
    --) shift; FILES+=("$@"); break ;;
    -*) echo "check-density.sh: unknown opt: $1" >&2; exit 2 ;;
    *)  FILES+=("$1"); shift ;;
  esac
done

[[ ${#FILES[@]} -eq 0 ]] && { echo "usage: check-density.sh [--max-chars N] [--max-words N] [--bullet-chars N] [--bullet-words N] [--changed-only] <file>..." >&2; exit 2; }

# check_one_file - runs the density awk program over a single
# file, restricting hits to CHANGED_CSV's line numbers when
# scoped is "1".
#
# Kept per-file (rather than one awk invocation over every FILES
# entry) because --changed-only needs a distinct changed-line
# set per file, and awk has no clean way to key a per-file array
# off ARGV.
check_one_file() {
  local file="$1" scoped="$2" changed_csv="$3"

  # why: LC_ALL=C pins awk to byte semantics in every machine
  # locale; char_len below converts bytes to characters, which
  # is sound because the caller has already validated UTF-8.
  LC_ALL=C awk -v mc="$MAX_CHARS" -v mw="$MAX_WORDS" -v bc="$BULLET_CHARS" -v bw="$BULLET_WORDS" \
      -v scoped="$scoped" -v changed_csv="$changed_csv" '
    BEGIN {
      if (scoped && changed_csv != "") {
        n = split(changed_csv, nums, ",")
        for (i = 1; i <= n; i++) changed[nums[i]] = 1
      }
    }
    # char_len - characters in s under LC_ALL=C: byte length minus
    # the UTF-8 continuation bytes (\200-\277).
    function char_len(s,    byte_len, continuation_bytes) {
      byte_len = length(s)
      continuation_bytes = gsub(/[\200-\277]/, "", s)
      return byte_len - continuation_bytes
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
      is_bullet = ($0 ~ /^[[:space:]]*([-*+]|[0-9]+\.)[[:space:]]/)
      eff_mc = is_bullet ? bc : mc
      eff_mw = is_bullet ? bw : mw
      gsub(/\(https?:\/\/[^)]*\)/, "")
      gsub(/[(<]data:[^)>]*[)>]/, "")
      gsub(/[][]/, "")
      line_chars = char_len($0)
      if (line_chars > eff_mc || NF > eff_mw) {
        if (scoped && !(FNR in changed)) next
        printf "%d:%d:%d\n", FNR, line_chars, NF
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

# why: awk measures invalid UTF-8 as bytes under LC_ALL=C but
# aborts on it under a UTF-8 locale; validating it here gives
# one exit code in every locale.
if ! command -v iconv >/dev/null 2>&1; then
  echo "check-density.sh: iconv is required to check that input is UTF-8" >&2
  exit 2
fi

for f in "${FILES[@]}"; do
  # why: readable check first, because iconv also exits 1 on a
  # missing file and the message would wrongly blame UTF-8.
  if [[ ! -f "$f" || ! -r "$f" ]]; then
    echo "check-density.sh: cannot read $f: not a readable file" >&2
    exit 2
  fi

  # why: stdin, because a "-x.md" argument parses as a flag.
  # why: piped to cat, because macOS iconv fails with stdout on
  # /dev/null for some valid input; pipefail keeps iconv's rc.
  if ! iconv -f UTF-8 -t UTF-8 <"$f" 2>/dev/null | cat >/dev/null; then
    echo "check-density.sh: cannot read $f: not valid UTF-8" >&2
    exit 2
  fi

  changed_csv=""
  if [[ $CHANGED_ONLY -eq 1 ]]; then
    if ! lines=$("$script_dir/get-changed-lines.sh" "$f" 2>"$err_file"); then
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
