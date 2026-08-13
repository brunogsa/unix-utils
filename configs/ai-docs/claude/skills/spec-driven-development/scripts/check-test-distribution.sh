#!/usr/bin/env bash
# check-test-distribution - verify a plan's Test Design titles match its per-task Tests (planned) lists.
#
# Usage:
#   check-test-distribution.sh <plan-path>
#
# Asserts SET EQUALITY between two regions of a plan_<slug>.md:
#   A = every Test Design title as a breadcrumb (<describe> [> class] > it), reconstructed by
#       the shared extract-design-tests.sh (the design, single source).
#   B = the union of every task's `**Tests (planned)**:` bullet list (the distribution),
#       which carries those same breadcrumbs verbatim.
#
# Set-equality (not a >=2 occurrence count) is deliberate: a naive count is fooled by a
# third region that also quotes titles verbatim (the AC -> test coverage table). Equality
# pins down exactly which two regions must agree and reports BOTH diffs:
#   A \ B -> a designed test assigned to no task (orphan test).
#   B \ A -> a task lists a test absent from the design (invented/renamed title).
# A byte-level difference surfaces as the title in A\B and its near-twin in B\A.
#
# Reuses extract-planned-tests-for-task.sh (sibling) for B, so bullet/quote/[on-demand]/[skip]
# normalization stays in one place. N/A tasks contribute nothing (correct).
#
# A Test Design section whose body reads "N/A — <reason>"
# designs no test at all, so it has nothing to distribute.
# plan-template.md sanctions that escape for a pure
# refactor, config edit, or similar no-behavior-change work.
#
# That escape is a CONJUNCTION, granted only when B is empty
# too - both regions must agree nothing is testable here.
#
# An N/A design over a task that still plans a real test is
# drift, not an escape, and keeps failing as B \ A.
#
# Exit codes:
#   0  - A == B. Every designed test is distributed to a task; no task invents a test.
#        Also the "N/A" Test Design escape, when no task plans a test either.
#   1  - A != B (diffs printed to stderr), OR a task is missing its `**Tests (planned)**:` bullet.
#   2  - usage error (wrong arg count, plan file not found, sibling script missing).

set -eo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") <plan-path>" >&2
  exit 2
fi

plan="$1"

if [ ! -f "$plan" ]; then
  echo "error: plan file not found: $plan" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
extract="$script_dir/extract-planned-tests-for-task.sh"
design_extract="$script_dir/extract-design-tests.sh"
section_slice="$script_dir/plan-section.sh"

for sib in "$extract" "$design_extract" "$section_slice"; do
  if [ ! -x "$sib" ]; then
    echo "error: sibling script not found or not executable: $sib" >&2
    exit 2
  fi
done

# A: Test Design breadcrumbs (<describe> [> class] > it), reconstructed by the shared extractor
# so the breadcrumb format lives in ONE place (check-ac-coverage.sh reconstructs via the same script).
#
# Its diagnostic is held back until the "N/A" escape below is ruled out: on an
# N/A Test Design, "no it() titles found" is the expected reading, not a defect.
design_err=$(mktemp)
trap 'rm -f "$design_err"' EXIT

is_design_na=false

if ! set_a=$("$design_extract" "$plan" 2>"$design_err"); then
  # Per-section escape sanctioned by plan-template.md: a
  # Test Design body reading "N/A" (case-insensitive,
  # word-boundary so "N/Ax" misses) designs no test, so
  # there is no distribution to check. Mirrors the same
  # escape in check-pr-dag.sh.
  #
  # Tested HERE, after extraction, not against the raw
  # body: the AC -> test coverage list shares this
  # section, so a plan carrying real it() titles keeps
  # facing the full set-equality check below.
  #
  # An absent section slices to an empty body, which no
  # escape matches - so a missing Test Design still fails.
  design_body=$("$section_slice" "$plan" "##" '^Test Design[[:space:]]*$' | sed '/^[[:space:]]*$/d')

  if printf '%s' "$design_body" | grep -qiE '^N/A([^a-zA-Z]|$)'; then
    # The verdict is deferred, not granted: the escape is a
    # claim about BOTH regions, so it stands only once set B
    # below is known to be empty too.
    is_design_na=true
  else
    cat "$design_err" >&2
    echo "error: could not extract Test Design breadcrumbs from $plan (see above)" >&2
    exit 1
  fi
fi

# B: union of every task's Tests (planned) list. Iterate the task numbers, reuse the sibling extractor.
task_nums=$(grep -oE '^### [0-9]+\.' "$plan" | grep -oE '[0-9]+' || true)

if [ -z "$task_nums" ]; then
  echo "error: no '### <N>.' task headings found in $plan" >&2
  exit 1
fi

set_b=""
for n in $task_nums; do
  # extract exits 1 if a task lacks its `**Tests (planned)**:` bullet — surface that as a plan defect.
  if ! titles=$("$extract" "$plan" "$n"); then
    echo "error: task $n is malformed (missing '**Tests (planned)**:' bullet); see extractor output above" >&2
    exit 1
  fi
  if [ -n "$titles" ]; then
    set_b=$(printf '%s\n%s' "$set_b" "$titles")
  fi
done

# Blank lines are dropped with sed, not `grep -v`: an all-N/A
# breakdown leaves set B empty, and grep's "no match" exit 1
# would trip `set -eo pipefail` and kill the run with no
# diagnostic at all.
sorted_b=$(printf '%s\n' "$set_b" | sed '/^[[:space:]]*$/d' | sort -u)

# The deferred "N/A" verdict, now that both regions are known.
#
# The escape is a CONJUNCTION - Test Design claims no test
# exists AND no task plans one - so it is granted only on an
# empty set B.
#
# A task still planning a test against an N/A design is
# genuine drift between the two regions, which is precisely
# what this gate exists to catch. Waving it through on the
# design's say-so alone would turn the escape into a hole
# any plan could opt into.
if [ "$is_design_na" = true ]; then
  if [ -n "$sorted_b" ]; then
    echo "FAIL: Test Design reads 'N/A' but tasks still plan tests (Tests-planned \\ Test Design):" >&2
    printf '%s\n' "$sorted_b" | sed 's/^/  - /' >&2
    exit 1
  fi

  echo "OK: Test Design has nothing to distribute (reads 'N/A — ...'), and no task plans a test."
  exit 0
fi

# Sorted, de-duplicated view of A for set comparison.
sorted_a=$(printf '%s\n' "$set_a" | sort -u)

a_only=$(comm -23 <(printf '%s\n' "$sorted_a") <(printf '%s\n' "$sorted_b"))
b_only=$(comm -13 <(printf '%s\n' "$sorted_a") <(printf '%s\n' "$sorted_b"))

if [ -z "$a_only" ] && [ -z "$b_only" ]; then
  count=$(printf '%s\n' "$sorted_a" | wc -l | tr -d ' ')
  echo "OK: $count designed tests, all distributed to tasks; no task invents a test."
  exit 0
fi

if [ -n "$a_only" ]; then
  echo "FAIL: designed tests assigned to NO task (Test Design \\ Tests-planned):" >&2
  printf '%s\n' "$a_only" | sed 's/^/  - /' >&2
fi

if [ -n "$b_only" ]; then
  echo "FAIL: tasks list tests ABSENT from Test Design (Tests-planned \\ Test Design):" >&2
  printf '%s\n' "$b_only" | sed 's/^/  - /' >&2
fi

exit 1
