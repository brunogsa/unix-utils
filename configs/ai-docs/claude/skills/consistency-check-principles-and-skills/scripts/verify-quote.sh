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
# part of the quoted content and is compared as-is. Join each side
# back into one newline-joined blob rather than comparing per-line:
# `grep -F` semantics (the spec's own words, D5/A4) match a fixed
# string anywhere *inside* a line, not only a whole-line match — and
# doc-standards keeps this repo's own prose one paragraph per physical
# line, so a real quote is routinely a fragment of a longer bullet,
# never the full line.
quote_blob="$(sed 's/[[:space:]]*$//')"
file_blob="$(sed 's/[[:space:]]*$//' "$TARGET_FILE")"

if [ -z "$quote_blob" ]; then
    echo "ERROR: empty quote given on stdin" >&2
    exit 1
fi

# A single literal substring test replaces the old line-array sliding
# window: contiguity still holds because a multi-line quote's internal
# newlines must line up with the file's, so a reordered or
# interleaved quote still can't match. Quoting the expansion inside
# the `case` pattern makes bash compare it byte-for-byte rather than
# interpreting it as a glob, so metacharacters in the quote (., *, [,
# ]) are never treated as a pattern — only the bare `*` either side of
# it is a real wildcard, meaning "anything before/after".
case "$file_blob" in
    *"$quote_blob"*)
        exit 0 ;;
esac

echo "ERROR: quote not found verbatim (as a contiguous block) in $TARGET_FILE" >&2
exit 1
