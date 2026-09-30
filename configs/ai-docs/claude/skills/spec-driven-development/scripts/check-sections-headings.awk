# check-sections-headings.awk - print every `## ` heading outside
# a fenced code block, for check-sections.sh.
#
# Run after parse-fences.awk, which supplies in_fence.
!in_fence && /^## / { print }
