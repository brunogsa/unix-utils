#!/usr/bin/env bash
# check-pr-body-size - Check a Markdown file against GitHub's body size limit.
#
# GitHub rejects a pull-request (or issue) body longer than 65536 characters —
# a hard API limit. Run this BEFORE pushing pr-descr_<slug>_pr<N>.md so the
# `gh api PATCH .../pulls/<n>` write never bounces on an oversized body.
#
# Usage:
#   check-pr-body-size.sh <file> [warn-margin]
#
#   <file>        Markdown file to measure (e.g. pr-descr_<slug>_pr<N>.md).
#   warn-margin   Optional. Chars of headroom below the hard limit that still
#                 trigger a "close" warning. Default: 3500 — covers the small
#                 drift between local `wc -m` and GitHub's own counting of
#                 multibyte content (accents, em dashes, arrows).
#
# Output: one human-readable line on stdout.
# Exit codes:
#   0  under the warn threshold (safe to push)
#   1  bad usage / file not found (message on stderr)
#   2  within the warn margin (close — trim soon)
#   3  over the hard limit (GitHub will reject)
#
# Examples:
#   check-pr-body-size.sh pr-descr_<slug>_pr<N>.md
#   check-pr-body-size.sh pr-descr_<slug>_pr<N>.md 5000
#
# Over the limit? Trim embedded docs to selected sections with the sibling
# extract-md-sections.sh, then re-run this check.

set -euo pipefail

HARD_LIMIT=65536

usage() { sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; }

case "${1:-}" in
    -h | --help)
        usage
        exit 0
        ;;
esac

file="${1:-}"
warn_margin="${2:-3500}"

if [[ -z "$file" ]]; then
    echo "error: missing <file> argument" >&2
    usage >&2
    exit 1
fi
if [[ ! -f "$file" ]]; then
    echo "error: file not found: $file" >&2
    exit 1
fi

chars=$(LC_ALL=en_US.UTF-8 wc -m <"$file" | tr -d ' ')
bytes=$(wc -c <"$file" | tr -d ' ')
warn_threshold=$((HARD_LIMIT - warn_margin))

if ((chars > HARD_LIMIT)); then
    echo "OVER LIMIT: $chars chars ($bytes bytes) — GitHub caps bodies at $HARD_LIMIT. Trim $((chars - HARD_LIMIT)) chars."
    exit 3
elif ((chars > warn_threshold)); then
    echo "CLOSE: $chars chars ($bytes bytes) — within $warn_margin of the $HARD_LIMIT cap. Consider trimming."
    exit 2
else
    echo "OK: $chars chars ($bytes bytes) — under the $HARD_LIMIT cap ($((HARD_LIMIT - chars)) to spare)."
    exit 0
fi
