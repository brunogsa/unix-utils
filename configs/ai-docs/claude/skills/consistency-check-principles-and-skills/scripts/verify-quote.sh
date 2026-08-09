#!/usr/bin/env bash
# verify-quote.sh - Verify a claimed quote is verbatim in a file (D5, A4)
#
# Reads the claimed quote from stdin and checks whether it is present
# in <file> as a literal substring — no regex interpretation — with
# trailing whitespace normalized per line. A multi-line quote must
# match a contiguous block of lines in the file, in that order.
#
# <file> is read fresh at verify time, never a cached snapshot from
# earlier in the run — this is the gate every BLOCKING #1-contradiction
# finding's two quoted sides pass through before the finding ships
# (D5): an edit between read and verify correctly fails the quote and
# drops a now-stale finding, and a hallucinated quote fails
# deterministically, with no vote, no judgment, no state file.
#
# Usage:
#   verify-quote.sh <file>
#   <quote text piped in via stdin>
#
# Examples:
#   printf 'exact line from the file' | verify-quote.sh notes.md
#   printf 'line one\nline two' | verify-quote.sh notes.md
#
# Exit codes:
#   0 - quote found verbatim, as a contiguous block
#   1 - quote not found, empty quote, or <file> does not exist
#       (diagnostic printed to stderr)

set -eo pipefail

usage() {
    sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

if [ $# -ne 1 ]; then
    echo "ERROR: usage: verify-quote.sh <file> (quote piped via stdin)" >&2
    exit 1
fi

TARGET_FILE=$1

if [ ! -f "$TARGET_FILE" ]; then
    echo "ERROR: target file not found: $TARGET_FILE" >&2
    exit 1
fi

# Strip trailing whitespace per line only — leading whitespace is
# part of the quoted content and is compared as-is.
#
# No `mapfile`/`readarray` (bash 4+, absent from macOS's stock bash
# 3.2) — a plain `read` loop instead, matching gen-shard-manifest.sh.
#
# `|| [ -n "$line" ]` keeps the loop running one more iteration when
# `read` hits EOF without a trailing newline, so a final line still
# gets appended instead of silently dropped — e.g. a single-line
# quote piped in via `printf '%s'` has no trailing newline.
quote_lines=()
while IFS= read -r line || [ -n "$line" ]; do
    quote_lines+=("$line")
done < <(sed 's/[[:space:]]*$//')

file_lines=()
while IFS= read -r line || [ -n "$line" ]; do
    file_lines+=("$line")
done < <(sed 's/[[:space:]]*$//' "$TARGET_FILE")

quote_len=${#quote_lines[@]}
file_len=${#file_lines[@]}

if [ "$quote_len" -eq 0 ]; then
    echo "ERROR: empty quote given on stdin" >&2
    exit 1
fi

# Slide a window of quote_len lines across the file's lines and
# compare each window to the quote line-by-line with plain string
# equality — never a regex match — so a contiguous block match is the
# only way to succeed, and metacharacters in the quote (., *, [, ])
# are compared literally rather than interpreted as a pattern.
match_found=0
max_start=$((file_len - quote_len))
start=0
while [ "$start" -le "$max_start" ]; do
    window_matches=1
    i=0
    while [ "$i" -lt "$quote_len" ]; do
        if [ "${file_lines[$((start + i))]}" != "${quote_lines[$i]}" ]; then
            window_matches=0
            break
        fi
        i=$((i + 1))
    done
    if [ "$window_matches" -eq 1 ]; then
        match_found=1
        break
    fi
    start=$((start + 1))
done

if [ "$match_found" -eq 1 ]; then
    exit 0
fi

echo "ERROR: quote not found verbatim (as a contiguous block) in $TARGET_FILE" >&2
exit 1
