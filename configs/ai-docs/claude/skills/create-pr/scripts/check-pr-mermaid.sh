#!/usr/bin/env bash
# check-pr-mermaid - Render every ```mermaid block in a
# Markdown file with mmdc, and fail when any block does not
# render.
#
# GitHub shows a parse error in place of a diagram it cannot
# render, and no other create-pr gate renders mermaid - so a
# broken diagram ships unless this gate runs.
#
# Usage:
#   check-pr-mermaid.sh <file>
#
#   <file>  Markdown file to check, e.g.
#           pr_<slug>_pr<N>.ideal.md or .final.md.
#
# Output: one verdict line on stdout. On a render failure,
# mmdc's error (stack frames stripped) goes to stderr: its
# "Parse error on line N" excerpt quotes the broken line, which
# tells the caller which diagram broke and why.
#
# A file with no mermaid block passes: mmdc itself exits 0
# on it.
#
# Exit codes:
#   0  every mermaid block renders (or there is none).
#   1  bad usage / file missing or unreadable (stderr).
#
#   3  a mermaid block failed to render (mmdc error on stderr).
#   4  mmdc is not on PATH - install it; never skip this gate.
#
# Examples:
#   check-pr-mermaid.sh pr_<slug>_pr<N>.ideal.md
#   check-pr-mermaid.sh pr_<slug>_pr<N>.final.md
#
# On exit 3, dispatch the mermaid-fixer agent with <file>, then
# re-run this check until it exits 0.

set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

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
if [[ ! -f "$file" || ! -r "$file" ]]; then
    echo "error: file not found or unreadable: $file" >&2
    exit 1
fi

# Checked before the file's content, so a body with no
# diagram still fails loudly on a machine that could not have
# checked one.
if ! command -v mmdc >/dev/null 2>&1; then
    echo "error: mmdc not found on PATH - install it with: npm install -g @mermaid-js/mermaid-cli" >&2
    exit 4
fi

out_dir=$(mktemp -d)
trap 'rm -rf "$out_dir"' EXIT
log="$out_dir/mmdc.log"

if mmdc -i "$file" -o "$out_dir/rendered.md" >"$log" 2>&1; then
    echo "OK: every mermaid block in $file renders."
    exit 0
fi

echo "FAIL: a mermaid block in $file does not render - mmdc said:" >&2

# Stack frames name mmdc's internals, never the diagram, so they
# are dropped. The fallback prints the whole log should a future
# mmdc format leave nothing after the filter.
errors=$(grep -vE '^[[:space:]]+at ' "$log" || true)
if [[ -n "$errors" ]]; then
    printf '%s\n' "$errors" >&2
else
    cat "$log" >&2
fi
exit 3
