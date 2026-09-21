#!/usr/bin/env bash
# check-pr-evidence - Check that every manual-evidence
# scenario in a PR body pastes an artifact rather than a
# claim about one.
#
# A narrated scenario ("ran four collection shapes against
# the ERP and read back each response") asserts an outcome
# no reviewer can check. A pasted request/response, log
# tail or screenshot can be checked; this is that gate.
#
# Why it keys off the anchors, not the section heading:
# this skill writes PR bodies in the team's primary
# language, so `## Evidences` is often `## Evidências`.
#
# The `<a id="scenario-N"></a>` anchor is mandated verbatim
# by references/pr-template.md, and is the same in every
# language.
#
# Usage:
#   check-pr-evidence.sh <file>
#
#   <file>  Markdown file to check, e.g.
#           pr_<slug>_pr<N>.ideal.md.
#
# Checks, in order:
# - A fenced non-mermaid block, or an image, per scenario.
# - An anchor for every `#scenario-N` link in the file.
# - A 20NN-NN-NN date per scenario — warn, never fail.
#
# The date only warns because the rules require a timestamp
# but leave its form free, so failing on it would flag a
# real timestamp the regex happens not to match.
#
# Output: a verdict line, then one line per scenario — on a
# pass too, since a passing total says nothing about which
# scenarios were checked.
#
# Exit codes:
#
# - 0, every scenario carries a dated artifact.
# - 1, bad usage / file not found (message on stderr).
# - 2, every artifact present, one or more dates missing.
# - 3, a scenario has no artifact, or a link dangles.
#
# Examples:
#   check-pr-evidence.sh pr_<slug>_pr<N>.ideal.md

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

# One SCENARIO row per anchor, one DANGLING row per link
# that has none. A row is tab-separated so the shell below
# reads fields without re-parsing the markdown.
report=$(awk '
# Only the digits in `<a id="scenario-7"></a>` or
# `#scenario-7`, which carry no other digit.
function number_in(s) { gsub(/[^0-9]/, "", s); return s + 0 }

{
    line = $0

    # Links are collected file-wide: an Acceptance-criteria
    # line may point at a scenario the Evidences section
    # never anchored.
    rest = line
    while (match(rest, /#scenario-[0-9]+/)) {
        linked[number_in(substr(rest, RSTART, RLENGTH))] = 1
        rest = substr(rest, RSTART + RLENGTH)
    }

    if (match(line, /<a id="scenario-[0-9]+"><\/a>/)) {
        current = number_in(substr(line, RSTART, RLENGTH))
        if (!(current in seen)) {
            seen[current] = 1
            order[++count] = current
        }
        in_block = 1
        in_fence = 0
        next
    }

    if (!in_block) next

    # Read the date before skipping fenced content: a log
    # tail timestamp is as good as a prose one.
    if (line ~ /20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]/) dated[current] = 1

    if (line ~ /^[ \t]*```/) {
        if (in_fence) { in_fence = 0; next }
        in_fence = 1
        if (tolower(line) !~ /mermaid/) artifact[current] = 1
        next
    }
    if (in_fence) next

    if (line ~ /!\[[^]]*\]\([^)]*\)/) artifact[current] = 1

    if (line ~ /^[ \t]*<\/details>/) in_block = 0
}

END {
    for (i = 1; i <= count; i++) {
        n = order[i]
        printf "SCENARIO\t%d\t%d\t%d\n", n, artifact[n], dated[n]
    }
    for (target in linked) if (!(target in seen)) printf "DANGLING\t%d\n", target
}
' "$file")

tab=$(printf '\t')
scenarios=$(printf '%s\n' "$report" | awk -F'\t' '$1 == "SCENARIO"')
dangling=$(printf '%s\n' "$report" | awk -F'\t' '$1 == "DANGLING"' | LC_ALL=C sort -t"$tab" -k2,2n)

count_rows() { printf '%s\n' "$1" | grep -c . || true; }

scenario_count=$(count_rows "$scenarios")
dangling_count=$(count_rows "$dangling")
missing_artifact=$(printf '%s\n' "$scenarios" | awk -F'\t' '$1 == "SCENARIO" && $3 == 0' | grep -c . || true)
missing_date=$(printf '%s\n' "$scenarios" | awk -F'\t' '$1 == "SCENARIO" && $4 == 0' | grep -c . || true)

print_breakdown() {
    printf '%s\n' "$scenarios" | awk -F'\t' 'NF == 4 {
        if ($3 == 0) verdict = "NO ARTIFACT — prose or a mermaid diagram only, nothing pasted"
        else if ($4 == 0) verdict = "no 20NN-NN-NN date in the block"
        else verdict = "artifact pasted, block dated"
        printf "  scenario %s  %s\n", $2, verdict
    }'
    printf '%s\n' "$dangling" | awk -F'\t' 'NF == 2 {
        printf "  scenario %s  DANGLING LINK — no <a id=\"scenario-%s\"></a> anchor\n", $2, $2
    }'
}

if ((scenario_count == 1)); then
    noun="manual scenario"
else
    noun="manual scenarios"
fi

if ((missing_artifact > 0 || dangling_count > 0)); then
    echo "MISSING EVIDENCE: $missing_artifact of $scenario_count $noun with no pasted artifact, $dangling_count dangling link(s)."
    print_breakdown
    exit 3
elif ((missing_date > 0)); then
    echo "UNDATED: every artifact pasted, $missing_date with no date — $scenario_count $noun checked."
    print_breakdown
    exit 2
elif ((scenario_count == 0)); then
    echo "OK: no manual scenarios — this body claims only automated coverage."
    exit 0
else
    echo "OK: a dated artifact pasted in every one — $scenario_count $noun checked."
    print_breakdown
    exit 0
fi
