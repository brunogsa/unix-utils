#!/usr/bin/env bash
# extract-design-tests - emit the Test Design test titles of a plan as breadcrumbs.
#
# Usage:
#   extract-design-tests.sh [--pairs] <plan-path>
#
# Default: prints one breadcrumb per line, reconstructed from the `## Test Design` section only:
#
#   <describe> > <happy|corner|failure> > <it>   when the it() sits under a class comment
#   <describe> > <it>                            for a flat helper block (no class comment)
#
# --pairs: prints `<bare-it><TAB><breadcrumb>` per line instead — consumed by
# normalize-list-breadcrumbs.sh to upgrade bare list titles to breadcrumbs. This keeps the
# describe/class reconstruction in ONE place (both gates and the normalizer read it here).
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
if [ "${1:-}" = "--pairs" ]; then
  pairs=1
  shift
fi

if [ $# -ne 1 ]; then
  echo "usage: $(basename "$0") [--pairs] <plan-path>" >&2
  exit 2
fi

plan="$1"

if [ ! -f "$plan" ]; then
  echo "error: plan file not found: $plan" >&2
  exit 2
fi

titles=$(awk -v pairs="$pairs" '
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
    sub(/^it\("/, "", t)
    sub(/"\)$/, "", t)
    crumb = (cls != "") ? (desc " > " cls " > " t) : (desc " > " t)
    if (pairs) print t "\t" crumb
    else print crumb
  }
' "$plan")

if [ -z "$titles" ]; then
  echo "error: no it(\"...\") titles found in the '## Test Design' section of $plan" >&2
  exit 1
fi

printf '%s\n' "$titles"
