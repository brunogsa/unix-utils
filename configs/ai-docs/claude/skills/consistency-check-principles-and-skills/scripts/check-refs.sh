#!/usr/bin/env bash
# check-refs.sh - Verify cross-references in one or more files
# resolve (the scripted, BLOCKING half of consistency-check's
# heuristic #6, D7).
#
# Scans each given file for markdown links `[text](path#anchor)`
# and backtick paths like `references/foo.md`, resolves each
# target relative to the referencing file's own directory, confirms
# the target exists (file or directory), and — when the ref carries
# a `#anchor` — that a heading in the target slugifies (GitHub-style)
# to it.
#
# Usage:
#   check-refs.sh <file> [file...]
#
# Examples:
#   check-refs.sh SKILL.md
#   check-refs.sh skills/*/SKILL.md skills/*/references/*.md
#
# Output format (stdout, only for broken refs):
#   <file>:<line> -> <target>
#
# Exit codes:
#   0 - every ref resolves (or no refs found)
#   1 - one or more refs broken, or a usage error (no files given,
#       or a given file does not exist) — every broken ref gets
#       listed, never just the first

set -eo pipefail

usage() {
    sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

if [ "$#" -eq 0 ]; then
    echo "ERROR: no files given" >&2
    usage >&2
    exit 1
fi

for f in "$@"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: file not found: $f" >&2
        exit 1
    fi
done

found_broken=0

# GitHub-style heading-to-slug: drop the leading `#` marker,
# lowercase, strip anything but letters/digits/spaces/hyphens/
# underscores, then replace each space with a hyphen individually.
#
# GitHub replaces spaces one at a time, not as a collapsed run: a
# stripped em-dash between two spaces leaves them adjacent, and each
# becomes its own hyphen — producing a double hyphen, not one.
slugify_heading() {
    local heading=$1
    heading="$(printf '%s' "$heading" | sed -E 's/^#{1,6}[[:space:]]+//')"
    printf '%s' "$heading" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/[^a-z0-9 _-]//g' \
        | sed -E 's/ /-/g'
}

# True (0) when $target_file has a heading whose GitHub-style anchor is
# $anchor. GitHub disambiguates repeated headings by appending -1, -2,
# ... to the second and later occurrences of an identical slug, so a
# raw slug match alone would miss those suffixed anchors.
#
# Tracks occurrences with a plain indexed array, not an associative
# array (`declare -A`) — macOS ships bash 3.2, which lacks it, and
# this repo must run on that stock bash.
heading_exists() {
    local target_file=$1 anchor=$2 heading slug repeat_count
    local anchor_candidate seen_slug
    local seen_slugs=()
    while IFS= read -r heading; do
        slug="$(slugify_heading "$heading")"
        repeat_count=0
        for seen_slug in "${seen_slugs[@]}"; do
            [ "$seen_slug" = "$slug" ] && repeat_count=$((repeat_count + 1))
        done
        if [ "$repeat_count" -eq 0 ]; then
            anchor_candidate="$slug"
        else
            anchor_candidate="${slug}-${repeat_count}"
        fi
        seen_slugs+=("$slug")
        [ "$anchor_candidate" = "$anchor" ] && return 0
    done < <(grep -E '^#{1,6}[[:space:]]' "$target_file" 2>/dev/null || true)
    return 1
}

# True (0) when $path starts with `/` and its first path segment
# is a real directory entry on this filesystem (e.g. `/tmp`, `/Users`).
#
# A slash-command mention like `/implement` also starts with `/` but
# resolves to no real top-level entry, so without this check it gets
# treated as a filesystem-absolute ref and reported broken — it is
# prose, not a path.
is_real_absolute_path_candidate() {
    local path=$1 first_segment
    first_segment="${path#/}"
    first_segment="${first_segment%%/*}"
    [ -d "/$first_segment" ]
}

# Resolve $path relative to $referencing_file's own directory (or as
# an absolute/home path). Existence is NOT checked here — that's the
# caller's job, since an unresolved path is exactly the broken-ref
# case this script exists to report, not a case to filter out.
resolve_target_path() {
    local referencing_file=$1 path=$2
    case "$path" in
        /*) printf '%s\n' "$path" ;;
        '~/'*) printf '%s\n' "$HOME/${path#\~/}" ;;
        *) printf '%s\n' "$(dirname "$referencing_file")/$path" ;;
    esac
}

# Report $target as broken for $file:$line, and flip the exit status.
report_broken() {
    local file=$1 line=$2 target=$3
    printf '%s:%s -> %s\n' "$file" "$line" "$target"
    found_broken=1
}

# Validate, resolve, and verify one candidate ref found at
# $file:$line. Reports it as broken when the target file is missing,
# or — given an anchor — when no heading in the target slugifies to
# it. Silently does nothing for a candidate that isn't a real
# file-ref target: an in-page `#anchor`-only link, a URL scheme, a
# trailing-slash directory mention (`scripts/`), or prose caught by
# an over-eager backtick/link match. Those aren't the blocking
# heuristic's cross-file-reference target, so they're not refs to
# begin with, not refs that happen to resolve.
check_candidate() {
    local file=$1 line=$2 raw=$3 path anchor resolved
    case "$raw" in
        *#*) path="${raw%%#*}"; anchor="${raw#*#}" ;;
        *) path="$raw"; anchor="" ;;
    esac

    case "$path" in
        *[!A-Za-z0-9_./~-]*|''|*/) return 0 ;;
    esac

    case "$path" in
        /*) is_real_absolute_path_candidate "$path" || return 0 ;;
    esac

    resolved="$(resolve_target_path "$file" "$path")"
    if [ ! -e "$resolved" ]; then
        report_broken "$file" "$line" "$raw"
        return 0
    fi

    if [ -n "$anchor" ] && ! heading_exists "$resolved" "$anchor"; then
        report_broken "$file" "$line" "$raw"
    fi
}

for file in "$@"; do
    line_num=0
    while IFS= read -r line || [ -n "$line" ]; do
        line_num=$((line_num + 1))

        while IFS= read -r match; do
            [ -n "$match" ] || continue
            candidate="${match#\]\(}"
            candidate="${candidate%)}"
            check_candidate "$file" "$line_num" "$candidate"
        done < <(grep -oE '\]\([^)]+\)' <<<"$line" 2>/dev/null || true)

        while IFS= read -r match; do
            [ -n "$match" ] || continue
            candidate="${match#\`}"
            candidate="${candidate%\`}"
            case "$candidate" in
                */*) check_candidate "$file" "$line_num" "$candidate" ;;
            esac
        done < <(grep -oE '`[^`]+`' <<<"$line" 2>/dev/null || true)
    done < "$file"
done

exit "$found_broken"
