#!/usr/bin/env bash
# check-test-distribution - verify a plan's Test Design titles are all distributed to a task.
#
# Usage:
#   check-test-distribution.sh <plan-path>
#
# Two Test Design forms, detected per-plan from extract-design-tests.sh --annotations (any
# it() line carrying an `// AC-<n>` or `T<n>` token puts the WHOLE plan in annotated form):
#
# ANNOTATED form (single source — the distribution lives ONLY as inline `T<n>` comments on Test
# Design's it() lines; see plan-template.md). Two checks:
#   (a) every it() line carries >=1 T<n> token (catches an undistributed/orphan designed test).
#   (b) every T<n> token names a task the `## Task Breakdown` actually defines (catches a
#       distribution to an invented/typo'd task number).
#
# LIST form (old — still required so plan_gate-roi.md/plan_script-overhaul.md-shaped plans keep
# passing unchanged; a transition path this comment already marks for removal once no plan uses
# it): asserts SET EQUALITY between two regions of a plan_<slug>.md:
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
#   0  - annotated form: every it() has >=1 T<n>, all naming real tasks. List form: A == B, or
#        the "N/A" Test Design escape when no task plans a test either.
#   1  - annotated form: an it() has no T<n>, or a T<n> names a task Task Breakdown never
#        defines. List form: A != B (diffs printed to stderr), or a task is missing its
#        `**Tests (planned)**:` bullet.
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

# Detect the plan's Test Design form the same way check-ac-coverage.sh does: any it() row with
# a non-empty T column puts the whole plan in annotated form. Skipped when the design is N/A
# (no it() lines at all — form doesn't apply; the list-form N/A handling below covers it).
is_annotated=false

if [ "$is_design_na" = false ]; then
  annotation_rows=$("$design_extract" --annotations "$plan")
  if printf '%s\n' "$annotation_rows" | awk -F'\t' '$4 != "" { found = 1 } END { exit !found }'; then
    is_annotated=true
  fi
fi

if [ "$is_annotated" = true ]; then
  # ANNOTATED form: the distribution lives ONLY as `T<n>` tokens on each it() line, so there is
  # no per-task `**Tests (planned)**:` bullet list to reuse extract-planned-tests-for-task.sh on.
  fail=0

  untagged=$(printf '%s\n' "$annotation_rows" | awk -F'\t' '$4 == "" { print $1 }')
  if [ -n "$untagged" ]; then
    fail=1
    echo "FAIL: designed tests with NO T<n> distribution tag:" >&2
    printf '%s\n' "$untagged" | sed 's/^/  - /' >&2
  fi

  all_t_tokens=$(printf '%s\n' "$annotation_rows" | cut -f4 | tr ' ' '\n' | grep -v '^$' | sort -u || true)
  invented=""
  for tok in $all_t_tokens; do
    n="${tok#T}"
    if ! printf '%s\n' "$task_nums" | grep -qxF "$n"; then
      invented="$invented $tok"
    fi
  done

  if [ -n "$invented" ]; then
    fail=1
    echo "FAIL: T<n> tokens naming a task the Task Breakdown never defines:" >&2
    for tok in $invented; do echo "  - $tok" >&2; done
  fi

  if [ "$fail" -eq 0 ]; then
    count=$(printf '%s\n' "$annotation_rows" | wc -l | tr -d ' ')
    echo "OK: $count designed tests, all distributed to tasks; no task invents a task number."
    exit 0
  fi

  exit 1
fi

# LIST form (below): unchanged from before this dispatch — see header comment.

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
