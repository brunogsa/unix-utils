#!/usr/bin/env bash
# check-pr-template-headings - Check that a PR body holds every
# heading of the repo's PR template, in the template's order.
#
# Usage:
#   check-pr-template-headings.sh <body-file> <template-file>
#
#   <body-file>      final PR body, e.g.
#                    pr_<slug>_pr<N>.final.md.
#   <template-file>  the repo's template, e.g.
#                    .github/PULL_REQUEST_TEMPLATE.md.
#
# A heading is a line starting with 1-6 `#` and a space,
# compared whole (level and text). Lines inside fenced code
# blocks are ignored in both files. The body may carry extra
# headings between the template's.
#
# stdout: one verdict line.
# stderr: one line per missing heading, and the first heading
#         found out of order.
#
# exit:   0 every template heading present, in order.
#         1 a heading is missing or out of order (stderr).
#         2 bad usage / file missing or unreadable (stderr).

set -euo pipefail

# Prints the header block above as help. Walks until the
# first non-comment line rather than a fixed range, so
# editing the header can never desync the help.
usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

case "${1:-}" in
    -h | --help)
        usage
        exit 0
        ;;
esac

if [ "$#" -ne 2 ]; then
    echo "error: expected <body-file> <template-file>, got $# argument(s)" >&2
    exit 2
fi

body_file="$1"
template_file="$2"

for file in "$body_file" "$template_file"; do
    if [ ! -r "$file" ]; then
        echo "error: file not found or unreadable: $file" >&2
        exit 2
    fi
done

fence_pattern='^ {0,3}(```|~~~)'
heading_pattern='^#{1,6}[[:space:]]'

# Prints every heading of a markdown file outside fenced code
# blocks, one per line, with trailing whitespace stripped.
print_headings() {
    local file="$1" line is_in_fence=false
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        if [[ "$line" =~ $fence_pattern ]]; then
            if [ "$is_in_fence" = true ]; then is_in_fence=false; else is_in_fence=true; fi
            continue
        fi
        if [ "$is_in_fence" = false ] && [[ "$line" =~ $heading_pattern ]]; then
            printf '%s\n' "${line%"${line##*[![:space:]]}"}"
        fi
    done < "$file"
}

template_headings=()
while IFS= read -r heading; do template_headings+=("$heading"); done < <(print_headings "$template_file")

body_headings=()
while IFS= read -r heading; do body_headings+=("$heading"); done < <(print_headings "$body_file")

# Returns the 0-based index of the first body heading equal to
# $1 at or after index $2, or -1 when there is none.
find_body_heading() {
    local wanted="$1" start="$2" index
    for ((index = start; index < ${#body_headings[@]}; index++)); do
        if [ "${body_headings[index]}" = "$wanted" ]; then
            echo "$index"
            return
        fi
    done
    echo -1
}

problem_count=0
is_order_reported=false
next_index=0
previous_heading=""

for heading in ${template_headings[@]+"${template_headings[@]}"}; do
    found_index=$(find_body_heading "$heading" "$next_index")
    if [ "$found_index" -ge 0 ]; then
        next_index=$((found_index + 1))
        previous_heading="$heading"
        continue
    fi

    problem_count=$((problem_count + 1))
    if [ "$(find_body_heading "$heading" 0)" -lt 0 ]; then
        echo "missing: \"$heading\"" >&2
    elif [ "$is_order_reported" = false ]; then
        echo "out of order: \"$heading\" must come after \"$previous_heading\", as in the template" >&2
        is_order_reported=true
    fi
done

if [ "$problem_count" -gt 0 ]; then
    echo "FAIL: the body does not hold the ${#template_headings[@]} template headings in order"
    exit 1
fi

echo "PASS: all ${#template_headings[@]} template headings present, in template order"
