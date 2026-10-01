# extract-design-tests.awk - print each it("...") title in a
# plan's Test Design section, for extract-design-tests.sh.
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

# describe("Name", ...) — set the current describe, reset the
# class.
match($0, /describe\("[^"]*"/) {
  d = substr($0, RSTART, RLENGTH)
  sub(/^describe\("/, "", d)
  sub(/"$/, "", d)
  desc = d
  cls = ""
  next
}

# Class markers — only these three exact comments set the
# class; other // lines are ignored so intra-section notes
# (e.g. "// Checagens NOSSAS...") keep the current class.
/^[[:space:]]*\/\/ Happy cases[[:space:]]*$/    { cls = "happy";   next }
/^[[:space:]]*\/\/ Corner cases[[:space:]]*$/   { cls = "corner";  next }
/^[[:space:]]*\/\/ Failure scenarios[[:space:]]*$/ { cls = "failure"; next }

# it("Title") — emit the breadcrumb (3-segment under a
# class, else 2-segment). The title match ends at the
# closing double quote, not at a quote-paren pair, so
# one-arg and two-arg it() forms share one matchEnd.
match($0, /it\("[^"]*"/) {
  t = substr($0, RSTART, RLENGTH)
  matchEnd = RSTART + RLENGTH
  sub(/^it\("/, "", t)
  sub(/"$/, "", t)
  crumb = (cls != "") ? (desc " > " cls " > " t) : (desc " > " t)
  if (annotations) {
    # `rest` is captured before any inner match() call below,
    # since those overwrite the same RSTART/RLENGTH the outer
    # it() match just set.
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
