# check-ac-coverage-plan-acs.awk - print the AC id of every
# `- **AC-N**` header in the plan, for check-ac-coverage.sh.
#
# Run after parse-fences.awk, which supplies in_fence and
# fence_event.
fence_event != "" { next }

!in_fence && /^## / { in_ac = 0 }
!in_fence && /^---$/ { in_ac = 0 }
/^- \*\*AC-[0-9]+\*\*/ {
  if (match($0, /AC-[0-9]+/)) { print substr($0, RSTART, RLENGTH); in_ac = 1 }
  next
}
