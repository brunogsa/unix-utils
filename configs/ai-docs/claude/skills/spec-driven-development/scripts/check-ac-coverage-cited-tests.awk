# check-ac-coverage-cited-tests.awk - print each test cited
# under a plan `- **AC-N**` header, for check-ac-coverage.sh.
#
# Run after parse-fences.awk, which supplies in_fence and
# fence_event.
fence_event != "" { next }

!in_fence && /^## / { in_ac = 0 }
!in_fence && /^---$/ { in_ac = 0 }
/^- \*\*AC-[0-9]+\*\*/ { in_ac = 1; next }
in_ac && /^[[:space:]]+- "/ {
  line = $0
  sub(/^[[:space:]]+- "/, "", line)
  sub(/"[[:space:]]*$/, "", line)
  if (length(line) > 0) print line
}
