#!/usr/bin/env bash
# extract-md-sections - Print selected level-2 (##) sections from a Markdown file.
#
# Pulls each named "## <section>" heading plus its body — everything up to the
# next "## " heading or EOF — and prints the kept sections in file order.
# Built for embedding chosen slices of spec_<slug>.md / plan_<slug>.md into a
# PR description without hand-copying, since the whole file usually blows
# GitHub's 65536-char body cap (see the sibling check-pr-body-size.sh).
#
# Content before the first kept heading (title, preamble) is dropped, as are
# any "## " sections you don't name. Nested "### " sub-headings ride along
# inside their parent section untouched.
#
# Usage:
#   extract-md-sections.sh <file> "<section title>" ["<section title>" ...]
#
#   <file>          Markdown file to read.
#   <section title> Exact heading text WITHOUT the leading "## ".
#                   Whole-line, case-sensitive match.
#
# Output: kept sections on stdout (redirect/pipe as needed).
# Exit codes:
#   0  at least one section matched
#   1  bad usage / file not found (message on stderr)
#   2  no requested section matched (empty stdout; hint on stderr)
#
# A requested title that isn't found prints a non-fatal warning on stderr, so
# typos surface without aborting the run.
#
# Examples:
#   extract-md-sections.sh spec_sge.md "Background / Context" "Testable Acceptance Criteria" > slice.md
#   extract-md-sections.sh plan_sge.md "Test Design" "Technical Decisions"
#
# List the file's sections first:  grep -n '^## ' <file>

set -euo pipefail

usage() { sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'; }

case "${1:-}" in
    -h | --help)
        usage
        exit 0
        ;;
esac

file="${1:-}"
if [[ -z "$file" ]]; then
    echo "error: missing <file> argument" >&2
    usage >&2
    exit 1
fi
if [[ ! -f "$file" ]]; then
    echo "error: file not found: $file" >&2
    exit 1
fi
shift

if [[ $# -eq 0 ]]; then
    echo "error: name at least one section title to extract" >&2
    usage >&2
    exit 1
fi

# Warn (non-fatal) on any title that doesn't exist as a whole-line "## <title>".
for title in "$@"; do
    if ! grep -qxF "## $title" "$file"; then
        echo "warning: section not found: '## $title'" >&2
    fi
done

# Build a newline-separated list of the exact heading lines to keep, passed via
# the environment rather than `awk -v`: some awk implementations (e.g. macOS's
# onetrueawk) fail to parse a -v value containing literal newlines.
wanted=""
for title in "$@"; do
    wanted+="## $title"$'\n'
done

out=$(
    WANTED_SECTIONS="$wanted" awk '
        BEGIN {
            n = split(ENVIRON["WANTED_SECTIONS"], arr, "\n")
            for (i = 1; i <= n; i++) if (arr[i] != "") want[arr[i]] = 1
        }
        /^## / { keep = (($0) in want) ? 1 : 0 }
        keep
    ' "$file"
)

if [[ -z "$out" ]]; then
    echo "warning: no requested section matched in $file" >&2
    echo "hint: list sections with  grep -n '^## ' \"$file\"" >&2
    exit 2
fi

printf '%s\n' "$out"
