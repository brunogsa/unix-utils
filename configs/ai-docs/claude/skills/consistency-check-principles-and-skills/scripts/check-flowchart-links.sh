#!/usr/bin/env bash
# check-flowchart-links.sh - Verify every skill's flowchart
# and its SKILL.md pointer reference each other.
#
# Usage:
#   check-flowchart-links.sh <skills-dir>
#
# stdout: one line per skill whose link is one-directional
# exit: 0 all bidirectional, 1 one or more broken, 2 bad input

set -uo pipefail

# The literal markdown link the convention puts in SKILL.md,
# matched fixed-string so no path character reads as a regex.
readonly POINTER='](assets/flowchart.md)'

usage() {
    printf '%s\n' \
        'check-flowchart-links.sh - Verify every skill flowchart' \
        'and its SKILL.md pointer reference each other.' \
        '' \
        'Usage:' \
        '  check-flowchart-links.sh <skills-dir>' \
        '' \
        'stdout: one line per skill whose link is one-directional' \
        'exit: 0 all bidirectional, 1 broken, 2 bad input'
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

if [ "$#" -ne 1 ]; then
    echo "ERROR: expected exactly one skills directory" >&2
    usage >&2
    exit 2
fi

root=$1

if [ ! -d "$root" ]; then
    echo "ERROR: not a directory: $root" >&2
    exit 2
fi

broken=0

# Direction 1, no orphan file: a flowchart nothing links to is
# undiscoverable, which is the orphan artifact rule.
for flowchart in "$root"/*/assets/flowchart.md; do
    [ -f "$flowchart" ] || continue
    skill_dir=${flowchart%/assets/flowchart.md}
    skill=${skill_dir##*/}

    if ! grep -qF -- "$POINTER" "$skill_dir/SKILL.md" 2>/dev/null; then
        echo "$skill: assets/flowchart.md exists, SKILL.md does not link it"
        broken=$((broken + 1))
    fi
done

# Direction 2, no dangling pointer: a link to a file that is
# not there sends the human reader nowhere.
for skill_md in "$root"/*/SKILL.md; do
    [ -f "$skill_md" ] || continue
    grep -qF -- "$POINTER" "$skill_md" || continue
    skill_dir=${skill_md%/SKILL.md}
    skill=${skill_dir##*/}

    if [ ! -f "$skill_dir/assets/flowchart.md" ]; then
        echo "$skill: SKILL.md links assets/flowchart.md, file is missing"
        broken=$((broken + 1))
    fi
done

[ "$broken" -eq 0 ]
