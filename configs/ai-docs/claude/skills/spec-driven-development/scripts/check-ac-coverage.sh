#!/usr/bin/env bash
# check-ac-coverage - verify a plan's AC -> test coverage list is complete and honest.
#
# Usage:
#   check-ac-coverage.sh <plan-path> <spec-path>
#
# The AC -> test mapping is a SEMANTIC judgment ("does this test prove this AC?") that no
# script can make — it stays human-authored in the plan as an AC-grouped nested list, each
# cited test written as a breadcrumb (<describe> [> class] > it), same as Test Design:
#
#   - **AC-1** <short title>
#     - "SgeSyncPicAgreementUseCase > happy > verbatim test title from Test Design"
#     - "SgeClient > another verbatim test title"   (2-segment for a flat helper block)
#
# This script mechanizes the two GAMING vectors around that judgment, leaving the judgment
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
#   0  - complete AND honest.
#   1  - a spec AC has no header, a plan header names a non-spec AC, or a cited test is not
#        a real Test Design title (diffs printed to stderr).
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

spec_acs=$(printf '%s\n' "$ac_section" | grep -oE '^### AC-[0-9]+:' | grep -oE 'AC-[0-9]+' | sort -u)

if [ -z "$spec_acs" ]; then
  echo "error: no '### AC-N:' definitions found in spec $spec" >&2
  exit 1
fi

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

fail=0

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
