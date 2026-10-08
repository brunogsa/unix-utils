# extract-design-tests.awk - print each it("...") and
# it.each(...)("...") title in a plan's Test Design section,
# for extract-design-tests.sh.
#
# Run after parse-fences.awk, which supplies in_fence. Inputs:
# -v pairs=<0|1> -v annotations=<0|1>.
#
# it() rows conventionally sit INSIDE one big Test Design fence,
# so fenced content is never skipped wholesale. Fence state only
# stops a `## ` line quoted as sample markup inside a fence from
# ending the section early.
fence_event != "" { next }

# Enter/leave the Test Design section; a later `## ` heading
# ends it.
!in_fence && /^## / {
  if (in_design) exit
  if ($0 ~ /^## Test Design[[:space:]]*$/) in_design = 1
  next
}
!in_design { next }

# describe("Name", ...) - set the current describe, reset the
# class.
match($0, /describe\("[^"]*"/) {
  d = substr($0, RSTART, RLENGTH)
  sub(/^describe\("/, "", d)
  sub(/"$/, "", d)
  desc = d
  cls = ""
  next
}

# Class markers - only these three exact comments set the
# class; other // lines are ignored so intra-section notes
# (e.g. "// Checagens NOSSAS...") keep the current class.
/^[[:space:]]*\/\/ Happy cases[[:space:]]*$/    { cls = "happy";   next }
/^[[:space:]]*\/\/ Corner cases[[:space:]]*$/   { cls = "corner";  next }
/^[[:space:]]*\/\/ Failure scenarios[[:space:]]*$/ { cls = "failure"; next }

# it.each(cases)( with its "Title" wrapped onto the next
# line - remember it, so that next line's leading string
# is read as the title.
/it\.each\(.*\)\([[:space:]]*$/ { pending_each = 1; next }

pending_each && match($0, /^[[:space:]]*"[^"]*"/) {
  pending_each = 0
  t = substr($0, RSTART, RLENGTH)
  rest = substr($0, RSTART + RLENGTH)
  sub(/^[[:space:]]*"/, "", t)
  sub(/"$/, "", t)
  print_row(t, rest)
  next
}
{ pending_each = 0 }

# it.each(cases)("Title") on one line. The greedy `.*`
# lands on the last `)("`, so a cases expression that
# itself calls a function still yields the title.
match($0, /it\.each\(.*\)\("[^"]*"/) {
  t = substr($0, RSTART, RLENGTH)
  rest = substr($0, RSTART + RLENGTH)
  sub(/^it\.each\(.*\)\("/, "", t)
  sub(/"$/, "", t)
  print_row(t, rest)
  next
}

# it("Title"). The title match ends at the closing double
# quote, not at a quote-paren pair, so one-arg and two-arg
# it() forms share one end position.
match($0, /it\("[^"]*"/) {
  t = substr($0, RSTART, RLENGTH)
  rest = substr($0, RSTART + RLENGTH)
  sub(/^it\("/, "", t)
  sub(/"$/, "", t)
  print_row(t, rest)
}

# print_row - emit one row for title t, where rest is the
# line text after the title: the breadcrumb (3-segment
# under a class, else 2-segment), plus the AC and T tokens
# of rest's trailing // comment in --annotations mode.
function print_row(t, rest,    crumb, comment, slashPos, acs, tnums, x, tok) {
  crumb = (cls != "") ? (desc " > " cls " > " t) : (desc " > " t)
  if (annotations) {
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
