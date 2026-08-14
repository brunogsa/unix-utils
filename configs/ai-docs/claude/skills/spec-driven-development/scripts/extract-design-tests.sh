#!/usr/bin/env bash
# extract-design-tests - emit the Test Design test titles of a plan as breadcrumbs.
#
# Usage:
#   extract-design-tests.sh [--pairs|--annotations] <plan-path>
#
# Default: prints one breadcrumb per line, reconstructed from the `## Test Design` section only:
#
#   <describe> > <happy|corner|failure> > <it>   when the it() sits under a class comment
#   <describe> > <it>                            for a flat helper block (no class comment)
#
# --pairs: prints `<bare-it><TAB><breadcrumb>` per line — each
# bare it() title next to its reconstructed breadcrumb.
#
# --annotations: prints `<bare-it><TAB><breadcrumb><TAB><AC tokens><TAB><T tokens>` per line —
# the AC/T tokens parsed from a trailing `// AC-<n>... T<n>... [on-demand]` comment on the
# it() line (the single-source annotation grammar; see plan-template.md's Test Design section).
# Both columns are space-joined when an annotation cites several tokens, and empty (but the tab
# still present) when the it() line carries no annotation at all — a plan still on the old
# list-form Test Design (no annotations anywhere) reads as every row's AC/T columns empty, which
# is exactly the signal check-ac-coverage.sh, check-test-distribution.sh, and
# extract-planned-tests-for-task.sh use to fall back to the pre-annotation list-form behavior.
# Consumed by those three sibling scripts, so the annotation grammar lives in ONE place too.
#
# The bare title and breadcrumb columns are already clean of the trailing annotation comment
# without any extra stripping step: the same `it\("[^"]*"\)` match the default/--pairs modes
# use stops at the closing `")`, before the `//` comment ever begins — so default and --pairs
# output are byte-identical whether or not the plan's it() lines carry annotations.
#
# The breadcrumb is DERIVED from Test Design's own structure — the `describe("X")` name and
# the nearest `// Happy cases` / `// Corner cases` / `// Failure scenarios` comment above the
# it(). Test Design keeps bare `it("...")`; the plan's two lists (AC coverage, per-task Tests
# (planned)) carry the breadcrumb verbatim. Both gate scripts reconstruct via THIS script, so
# the breadcrumb lives in one place and any format drift between list and design surfaces red.
#
# Why breadcrumb and not bare title: two describe blocks may share an it() title; bare titles
# collapse under `sort -u`, silently hiding a coverage gap. The describe (+ class) prefix keeps
# same-named tests distinct and makes each citation self-describing (its exact home is visible).
#
# Exit codes:
#   0  - success (>=1 title found).
#   1  - no `## Test Design` section, or no it("...") titles within it.
#   2  - usage error (wrong arg count, plan file not found).

set -eo pipefail

pairs=0
annotations=0
case "${1:-}" in
  --pairs) pairs=1; shift ;;
  --annotations) annotations=1; shift ;;
esac

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") [--pairs|--annotations] <plan-path>" >&2
  exit 2
fi

plan="$1"

if [ ! -f "$plan" ]; then
  echo "error: plan file not found: $plan" >&2
  exit 2
fi

titles=$(awk -v pairs="$pairs" -v annotations="$annotations" '
  # Enter/leave the Test Design section; a later `## ` heading ends it.
  /^## / {
    if (in_design) exit
    if ($0 ~ /^## Test Design[[:space:]]*$/) in_design = 1
    next
  }
  !in_design { next }

  # describe("Name", ...) — set the current describe, reset the class.
  match($0, /describe\("[^"]*"/) {
    d = substr($0, RSTART, RLENGTH)
    sub(/^describe\("/, "", d)
    sub(/"$/, "", d)
    desc = d
    cls = ""
    next
  }

  # Class markers — only these three exact comments set the class; other // lines are ignored
  # so intra-section notes (e.g. "// Checagens NOSSAS...") keep the current class.
  /^[[:space:]]*\/\/ Happy cases[[:space:]]*$/    { cls = "happy";   next }
  /^[[:space:]]*\/\/ Corner cases[[:space:]]*$/   { cls = "corner";  next }
  /^[[:space:]]*\/\/ Failure scenarios[[:space:]]*$/ { cls = "failure"; next }

  # it("Title") — emit the breadcrumb (3-segment under a class, else 2-segment).
  match($0, /it\("[^"]*"\)/) {
    t = substr($0, RSTART, RLENGTH)
    matchEnd = RSTART + RLENGTH
    sub(/^it\("/, "", t)
    sub(/"\)$/, "", t)
    crumb = (cls != "") ? (desc " > " cls " > " t) : (desc " > " t)
    if (annotations) {
      # `rest` is captured before any inner match() call below, since those
      # overwrite the same RSTART/RLENGTH the outer it() match just set.
      rest = substr($0, matchEnd)
      comment = ""
      slashPos = index(rest, "//")
      if (slashPos > 0) comment = substr(rest, slashPos + 2)

      acs = ""; x = comment
      while (match(x, /AC-[0-9]+/)) {
        tok = substr(x, RSTART, RLENGTH)
        acs = (acs == "" ? tok : acs " " tok)
        x = substr(x, RSTART + RLENGTH)
      }

      tnums = ""; x = comment
      while (match(x, /T[0-9]+/)) {
        tok = substr(x, RSTART, RLENGTH)
        tnums = (tnums == "" ? tok : tnums " " tok)
        x = substr(x, RSTART + RLENGTH)
      }

      print t "\t" crumb "\t" acs "\t" tnums
    } else if (pairs) print t "\t" crumb
    else print crumb
  }
' "$plan")

if [ -z "$titles" ]; then
  echo "error: no it(\"...\") titles found in the '## Test Design' section of $plan" >&2
  exit 1
fi

printf '%s\n' "$titles"
