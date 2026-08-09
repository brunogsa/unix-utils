#!/usr/bin/env bash
# check-pr-page-fit - Check that a PR body's visible text fits on one screen.
#
# GitHub's hard 65536-char cap (see the sibling check-pr-body-size.sh) is about
# what the API accepts. This checks something else: what a reviewer actually
# sees before scrolling. A PR whose body needs three screens gets skimmed.
#
# What counts as one rendered line — the measurement model:
#   * A collapsed <details> block            -> 1 line (only its summary shows).
#   * An expanded <details open> block       -> summary + its text, minus images.
#   * A ```mermaid fence                     -> 0 lines (renders as a diagram).
#   * Any other fenced code block            -> counted, it is text the eye reads.
#   * ![image](...) lines                    -> 0 lines.
#   * HTML comments and [ref]: link defs     -> 0 lines (never rendered).
#   * A heading                              -> 1 line.
#   * A long source line                     -> ceil(chars / width), since it wraps.
#   * Blank lines                            -> 0 lines (separators, not content).
#
# The appendix needs no special case: its bulk sits inside collapsed <details>,
# so it costs only its own headings plus one line per collapsed block. Leaving
# an appendix section expanded costs its full text, which is the point.
#
# Usage:
#   check-pr-page-fit.sh <file> [page-lines] [wrap-width]
#
#   <file>       Markdown file to measure (e.g. pr_<slug>_pr<N>.ideal.md).
#   page-lines   Optional. Rendered lines the whole body may occupy. Default: 64,
#                the sum of the per-section budgets in create-pr's
#                references/pr-page-budget.md, which is the authority on how
#                those 64 lines are divided.
#   wrap-width   Optional. Chars per rendered line before wrapping. Default: 95 —
#                GitHub's ~860px description column at 14px/1.5 body type.
#
# Output: a verdict line, then a breakdown per heading — top-level sections
# worst-first, each subsection indented under its parent and included in its
# total. Compare it against the per-section budgets in create-pr's
# references/pr-page-budget.md: a body can pass the total while one section has
# eaten another's allowance.
#
# Exit codes:
#   0  fits on one page
#   1  bad usage / file not found (message on stderr)
#   2  within 20% of the budget (close — trim soon)
#   3  over the budget (does not fit one page)
#
# Examples:
#   check-pr-page-fit.sh pr_<slug>_pr<N>.ideal.md
#   check-pr-page-fit.sh pr_<slug>_pr<N>.ideal.md 80      # taller screen
#   check-pr-page-fit.sh pr_<slug>_pr<N>.ideal.md 64 110  # wider column

set -euo pipefail

# Prints the header block above as help. Walks until the first non-comment line
# rather than a fixed range, so editing the header can never desync the help.
usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

case "${1:-}" in
    -h | --help)
        usage
        exit 0
        ;;
esac

file="${1:-}"
page_lines="${2:-64}"
wrap_width="${3:-95}"

if [[ -z "$file" ]]; then
    echo "error: missing <file> argument" >&2
    usage >&2
    exit 1
fi
if [[ ! -f "$file" ]]; then
    echo "error: file not found: $file" >&2
    exit 1
fi
if ! [[ "$page_lines" =~ ^[0-9]+$ ]] || ((page_lines < 1)); then
    echo "error: page-lines must be a positive integer, got: $page_lines" >&2
    exit 1
fi
if ! [[ "$wrap_width" =~ ^[0-9]+$ ]] || ((wrap_width < 20)); then
    echo "error: wrap-width must be an integer >= 20, got: $wrap_width" >&2
    exit 1
fi

# Wrapping is decided by what GitHub RENDERS, not by what the source spells, so the
# second input below is a width-only copy with the invisible markup removed:
#
#   * HTML tags        - <summary><strong>x</strong></summary> shows as `x`.
#   * Link targets     - [types.ts](https://…200 chars…) shows as `types.ts`.
#   * Emphasis markers - **x**, _x_, and `x` all show as `x`.
#
# awk's length() then counts BYTES and ignores LC_ALL, so an accented character in a
# non-English body would still be charged twice. Deleting UTF-8 continuation bytes
# (0x80-0xBF) leaves one byte per character, giving true widths.
#
# awk reads structure from the original file, so headings still print intact.
report=$(awk -v width="$wrap_width" '
function ceil(x) { return (x == int(x)) ? x : int(x) + 1 }

# Vertical cost of one source line, once we know it renders at all.
function cost(i,   n) {
    if (arr[i] ~ /^[ \t]*$/) return 1
    n = len[i]
    return (n <= width) ? 1 : ceil(n / width)
}

# Charge a cost to the running total and to every heading still open above it,
# so a section reports what it consumes including its subsections.
function bump(n,   d) {
    total += n
    for (d = 0; d <= depth_top; d++)
        if (open[d] != "") cnt[open[d]] += n
}

FNR == NR { arr[FNR] = $0; nlines = FNR; next }
{ len[FNR] = length($0) }

END {
    i = 1
    # Skip YAML frontmatter — bundled reference files carry budget overrides
    # that are not part of the PR body they reproduce.
    if (nlines > 0 && arr[1] ~ /^---[ \t]*$/) {
        i = 2
        while (i <= nlines && arr[i] !~ /^---[ \t]*$/) i++
        i++
    }

    # Everything before the first heading still belongs to a section, so the
    # review guide and any preamble are reported rather than silently absorbed.
    open[0] = "(before first heading)"
    id[open[0]] = ++nsec; ord[nsec] = open[0]; lvl[nsec] = 0; cnt[open[0]] = 0
    depth_top = 0
    total = 0

    while (i <= nlines) {
        l = arr[i]

        # Never-rendered constructs.
        if (l ~ /^[ \t]*<!--/) {                       # HTML comment
            while (i <= nlines && arr[i] !~ /-->/) i++
            i++; continue
        }
        if (l ~ /^[ \t]*\[[^]]+\]:[ \t]/) { i++; continue }   # link-ref definition
        if (l ~ /!\[/) { i++; continue }                      # image
        if (l ~ /^[ \t]*<a[ \t][^>]*><\/a>[ \t]*$/) { i++; continue }   # empty anchor

        # <details>: collapsed shows only its summary; open renders its contents.
        if (l ~ /<details/) {
            if (l ~ /<details[ \t]+open/) {
                i++                                    # fall through to inner lines
                continue
            }
            # Charge the summary the reader sees, at its true wrapped width — a
            # long summary line costs the same two lines collapsed or expanded.
            j = i + 1
            while (j <= nlines && arr[j] !~ /<summary/ && arr[j] !~ /<\/details>/) j++
            bump((j <= nlines && arr[j] ~ /<summary/) ? cost(j) : 1)
            while (i <= nlines && arr[i] !~ /<\/details>/) i++
            i++; continue
        }
        if (l ~ /^[ \t]*<\/details>/) { i++; continue }

        # <summary> of an expanded block: visible text, so it wraps like any other.
        if (l ~ /<summary/) { bump(cost(i)); i++; continue }

        # Fenced code: mermaid renders as a diagram, everything else as text.
        if (l ~ /^[ \t]*```/) {
            is_mermaid = (tolower(l) ~ /mermaid/)
            i++
            n = 0
            while (i <= nlines && arr[i] !~ /^[ \t]*```/) { n += cost(i); i++ }
            i++                                        # closing fence
            if (!is_mermaid) bump(n + 2)               # + the two fence lines
            continue
        }

        # A heading opens a section and closes every section at or below its
        # depth, so nesting in the report mirrors nesting in the document.
        if (l ~ /^#+[ \t]/) {
            d = match(l, /^#+/) ? RLENGTH : 1
            title = l
            gsub(/^#+[ \t]*/, "", title)
            for (k = d; k <= depth_top; k++) open[k] = ""
            open[0] = ""                               # the preamble is not an ancestor
            open[d] = title
            depth_top = d
            if (!(title in id)) {
                id[title] = ++nsec; ord[nsec] = title; lvl[nsec] = d; cnt[title] = 0
            }
            bump(1); i++; continue
        }

        # A blank line is a separator, not content: between list items it renders
        # as nothing, and between paragraphs as margin rather than a line of text.
        if (l ~ /^[ \t]*$/) { i++; continue }

        bump(cost(i)); i++
    }

    # Shallowest real heading defines indent depth 0 for the report.
    minlvl = 99
    for (k = 1; k <= nsec; k++) if (lvl[k] > 0 && lvl[k] < minlvl) minlvl = lvl[k]

    printf "TOTAL %d\n", total
    # Sort key: top-level sections worst-first, children in document order below.
    for (k = 1; k <= nsec; k++) {
        s = ord[k]
        if (cnt[s] <= 0) continue
        if (lvl[k] <= minlvl) { anchor = cnt[s]; }
        printf "%09d\t%09d\t%d\t%d\t%s\n", 999999999 - anchor, k, lvl[k] - minlvl, cnt[s], s
    }
}
' "$file" <(sed -E -e 's/<[^>]*>//g' -e 's/\]\([^)]*\)/]/g' -e 's/[*_`]//g' <"$file" |
    LC_ALL=C tr -d '\200-\277'))

total=$(printf '%s\n' "$report" | awk '/^TOTAL /{print $2; exit}')
sections=$(printf '%s\n' "$report" | awk 'NR>1' | LC_ALL=C sort -t"$(printf '\t')" -k1,1n -k2,2n)
warn_threshold=$((page_lines * 80 / 100))

# Indent by heading depth so a section's subsections read as its breakdown.
print_breakdown() {
    echo "  lines  section (subsections roll up into their parent)"
    printf '%s\n' "$sections" | awk -F'\t' 'NF==5 {
        pad = ""
        for (n = 0; n < $3; n++) pad = pad "  "
        printf "  %4d  %s%s\n", $4, pad, $5
    }'
}

if ((total > page_lines)); then
    echo "OVER: ~$total rendered lines — a one-page body is $page_lines. Cut ~$((total - page_lines))."
    print_breakdown
    exit 3
elif ((total > warn_threshold)); then
    echo "CLOSE: ~$total rendered lines of the $page_lines that fit one page."
    print_breakdown
    exit 2
else
    echo "OK: ~$total rendered lines — fits one page ($page_lines), $((page_lines - total)) to spare."
    # Printed even on success: the total passing does not mean every section stayed
    # within its own budget, and only the breakdown can show that.
    print_breakdown
    exit 0
fi
