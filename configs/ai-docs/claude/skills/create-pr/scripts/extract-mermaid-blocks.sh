#!/usr/bin/env bash
# extract-mermaid-blocks - Print every ```mermaid fenced block from Markdown files.
#
# Emits each block with its fences intact, in file order, blocks separated by a
# blank line, so the output pastes straight into a PR description's Architecture
# section. Built so diagrams reach the PR by copy, never by an AI re-drawing
# them from the source file — a re-drawn diagram silently diverges from the one
# the spec/plan was reviewed against.
#
# Sibling of extract-md-sections.sh, which cherry-picks "## " sections instead;
# together they cover both halves of a spec/plan (headings and diagrams).
#
# Usage:
#   extract-mermaid-blocks.sh <file> [<file> ...]
#
#   <file>  Markdown file to read. Several files are read in argument order.
#
# Output: the fenced blocks on stdout (redirect/pipe as needed).
# Exit codes:
#   0  at least one block was found
#   1  bad usage / file not found (message on stderr)
#   2  no block found in any file (empty stdout; hint on stderr)
#
# An unterminated block (opening fence with no closing fence) is printed up to
# EOF and warned about on stderr, since dropping it silently would lose a
# diagram the author did write.
#
# Examples:
#   extract-mermaid-blocks.sh spec_sge.md plan_sge.md > diagrams.md
#   extract-mermaid-blocks.sh plan_sge.md | wc -l
#
# Count the blocks first:  grep -c '^ *```mermaid' <file>

set -euo pipefail

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

case "${1:-}" in
    -h | --help)
        usage
        exit 0
        ;;
esac

if [[ $# -eq 0 ]]; then
    echo "error: missing <file> argument" >&2
    usage >&2
    exit 1
fi

for file in "$@"; do
    if [[ ! -f "$file" ]]; then
        echo "error: file not found: $file" >&2
        exit 1
    fi
done

out=$(
    awk '
        # Reset the open-fence state per file, so an unterminated block in one
        # file cannot swallow the next file'"'"'s prose.
        FNR == 1 { if (inblock) unterminated = 1; inblock = 0 }

        !inblock && /^[ \t]*```mermaid[ \t]*$/ {
            inblock = 1
            if (printed++) print ""
            print
            next
        }

        inblock {
            print
            if ($0 ~ /^[ \t]*```[ \t]*$/) inblock = 0
            next
        }

        END {
            if (inblock || unterminated)
                print "warning: unterminated ```mermaid block, printed up to EOF" > "/dev/stderr"
        }
    ' "$@"
)

if [[ -z "$out" ]]; then
    echo "warning: no \`\`\`mermaid block found in: $*" >&2
    echo "hint: count them with  grep -c '^ *\`\`\`mermaid' <file>" >&2
    exit 2
fi

printf '%s\n' "$out"
