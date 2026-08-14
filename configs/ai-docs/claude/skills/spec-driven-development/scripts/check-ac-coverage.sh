#!/usr/bin/env bash
# check-ac-coverage - verify a plan's spec ACs are all covered by Test Design.
#
# Usage:
#   check-ac-coverage.sh <plan-path> <spec-path>
#
# Two Test Design forms, detected per-plan from extract-design-tests.sh --annotations (any
# it() line carrying an `// AC-<n>` or `T<n>` token puts the WHOLE plan in annotated form):
#
# ANNOTATED form (single source — the AC -> test mapping lives ONLY as inline `// AC-N T<n>`
# comments on Test Design's it() lines; see plan-template.md). One check remains:
#   COMPLETENESS - every `### AC-N:` defined in the spec's Acceptance Criteria section is cited
#                  by >=1 it() annotation in Test Design (catches a silently-dropped AC).
# The HONESTY check this script used to run (every cited breadcrumb exists verbatim among Test
# Design's breadcrumbs) is DELETED for this form, not merely skipped: HONESTY existed to catch
# a plan citing a test that was never designed, and annotated form has no second copy of the
# mapping left to fake — the failure class it guarded against no longer exists.
#
# LIST form (old — still required so plan_gate-roi.md/plan_script-overhaul.md-shaped plans keep
# passing unchanged; a transition path this comment already marks for removal once no plan uses
# it): the AC -> test mapping is a SEMANTIC judgment ("does this test prove this AC?") that no
# script can make — it stays human-authored in the plan as an AC-grouped nested list, each
# cited test written as a breadcrumb (<describe> [> class] > it), same as Test Design:
#
#   - **AC-1** <short title>
#     - "SgeSyncPicAgreementUseCase > happy > verbatim test title from Test Design"
#     - "SgeClient > another verbatim test title"   (2-segment for a flat helper block)
#
# This form mechanizes the two GAMING vectors around that judgment, leaving the judgment
# itself to the human read:
#   COMPLETENESS - every `### AC-N:` defined in the spec's Acceptance Criteria section appears
#                  as an `- **AC-N**` header in the plan (catches a silently-dropped AC).
#   HONESTY      - every cited breadcrumb exists verbatim among the plan's Test Design
#                  breadcrumbs (reconstructed by the shared extract-design-tests.sh; a `...`-
#                  truncated or invented citation simply won't match -> flagged).
#
# Honesty is a SUBSET check (cited ⊆ design), not equality: one test may prove several ACs,
# and a corner/failure test need not map to any spec AC.
#
# Exit codes:
#   0  - complete (annotated form), or complete AND honest (list form).
#   1  - a spec AC has no annotation/header, a list-form plan header names a non-spec AC, or a
#        list-form cited test is not a real Test Design title (diffs printed to stderr).
#   2  - usage error (wrong arg count, a file not found).

set -eo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $(basename "$0") <plan-path> <spec-path>" >&2
  exit 2
fi

plan="$1"
spec="$2"

for f in "$plan" "$spec"; do
  if [ ! -f "$f" ]; then
    echo "error: file not found: $f" >&2
    exit 2
  fi
done

script_dir="$(cd "$(dirname "$0")" && pwd)"
design_extract="$script_dir/extract-design-tests.sh"

if [ ! -x "$design_extract" ]; then
  echo "error: sibling script not found or not executable: $design_extract" >&2
  exit 2
fi

# spec ACs: canonical set from `### AC-N:` definition headings, scoped to the spec's
# `## ...Acceptance Criteria...` section so a stray `### AC-N:` used as an example elsewhere
# can't leak in. Falls back to the whole file (with a warning) if that heading is absent.
ac_section=$(awk '
  /^## / {
    if (in_ac) exit
    if (tolower($0) ~ /acceptance criteria/) { in_ac = 1; next }
  }
  in_ac { print }
' "$spec")

if [ -z "$ac_section" ]; then
  echo "warning: no '## ...Acceptance Criteria...' heading in $spec; scanning whole file for '### AC-N:'" >&2
  ac_section=$(cat "$spec")
fi

# `|| true` keeps grep's no-match exit 1 from killing the script
# under `set -e`, so the empty case reaches the error below.
spec_acs=$(printf '%s\n' "$ac_section" | grep -oE '^### AC-[0-9]+:' | grep -oE 'AC-[0-9]+' | sort -u || true)

if [ -z "$spec_acs" ]; then
  echo "error: no '### AC-N:' definitions found in spec $spec" >&2
  exit 1
fi

# Detect the plan's Test Design form via extract-design-tests.sh --annotations: any it() row
# with a non-empty AC or T column puts the WHOLE plan in annotated form (see header comment).
if ! annotation_rows=$("$design_extract" --annotations "$plan"); then
  echo "error: could not extract Test Design breadcrumbs from $plan (see above)" >&2
  exit 1
fi

is_annotated=$(printf '%s\n' "$annotation_rows" | awk -F'\t' '$3 != "" || $4 != "" { found = 1 } END { print (found ? "yes" : "no") }')

fail=0

if [ "$is_annotated" = "yes" ]; then
  # ANNOTATED form: COMPLETENESS only, checked against the union of `// AC-N` tokens across
  # every it() annotation — HONESTY is deleted here (see header comment), not skipped: there is
  # no second citation list left for a `...`-truncated or invented reference to hide behind.
  annotated_acs=$(printf '%s\n' "$annotation_rows" | cut -f3 | tr ' ' '\n' | grep -v '^$' | sort -u || true)

  spec_only=$(comm -23 <(printf '%s\n' "$spec_acs") <(printf '%s\n' "$annotated_acs"))

  if [ -n "$spec_only" ]; then
    fail=1
    echo "FAIL (completeness): spec ACs with NO annotation in Test Design:" >&2
    printf '%s\n' "$spec_only" | sed 's/^/  - /' >&2
  fi

  if [ "$fail" -eq 0 ]; then
    ac_count=$(printf '%s\n' "$spec_acs" | wc -l | tr -d ' ')
    echo "OK: all $ac_count spec ACs are annotated in Test Design."
    exit 0
  fi

  exit 1
fi

# LIST form (below): unchanged from before this dispatch — see header comment.

# plan AC headers: `- **AC-N**` bullets. Also collect the tests cited under each.
# A cited test is an indented `- "..."` sub-bullet belonging to the most recent AC header.
# The AC region ends at a `## ` heading or a `---` divider.
plan_acs=$(awk '
  /^## / { in_ac = 0 }
  /^---$/ { in_ac = 0 }
  /^- \*\*AC-[0-9]+\*\*/ {
    if (match($0, /AC-[0-9]+/)) { print substr($0, RSTART, RLENGTH); in_ac = 1 }
    next
  }
' "$plan" | sort -u)

cited_tests=$(awk '
  /^## / { in_ac = 0 }
  /^---$/ { in_ac = 0 }
  /^- \*\*AC-[0-9]+\*\*/ { in_ac = 1; next }
  in_ac && /^[[:space:]]+- "/ {
    line = $0
    sub(/^[[:space:]]+- "/, "", line)
    sub(/"[[:space:]]*$/, "", line)
    if (length(line) > 0) print line
  }
' "$plan" | sort -u)

# design tests: Test Design breadcrumbs (<describe> [> class] > it) via the shared extractor,
# so `cited ⊆ design` compares breadcrumb-to-breadcrumb (the plan's lists carry the same format).
if ! design_tests=$("$design_extract" "$plan" | sort -u); then
  echo "error: could not extract Test Design breadcrumbs from $plan (see above)" >&2
  exit 1
fi

# COMPLETENESS: spec_acs == plan_acs.
spec_only=$(comm -23 <(printf '%s\n' "$spec_acs") <(printf '%s\n' "$plan_acs"))
plan_only=$(comm -13 <(printf '%s\n' "$spec_acs") <(printf '%s\n' "$plan_acs"))

if [ -n "$spec_only" ]; then
  fail=1
  echo "FAIL (completeness): spec ACs with NO coverage header in the plan:" >&2
  printf '%s\n' "$spec_only" | sed 's/^/  - /' >&2
fi

if [ -n "$plan_only" ]; then
  fail=1
  echo "FAIL (completeness): plan coverage headers naming an AC absent from the spec:" >&2
  printf '%s\n' "$plan_only" | sed 's/^/  - /' >&2
fi

# HONESTY: cited_tests ⊆ design_tests.
cited_not_design=$(comm -23 <(printf '%s\n' "$cited_tests") <(printf '%s\n' "$design_tests"))

if [ -n "$cited_not_design" ]; then
  fail=1
  echo "FAIL (honesty): tests cited under an AC but ABSENT (verbatim) from Test Design:" >&2
  printf '%s\n' "$cited_not_design" | sed 's/^/  - /' >&2
fi

if [ "$fail" -eq 0 ]; then
  ac_count=$(printf '%s\n' "$spec_acs" | wc -l | tr -d ' ')
  cite_count=$(printf '%s\n' "$cited_tests" | grep -c . || true)
  echo "OK: all $ac_count spec ACs have coverage headers; all $cite_count cited tests exist verbatim in Test Design."
  exit 0
fi

exit 1
