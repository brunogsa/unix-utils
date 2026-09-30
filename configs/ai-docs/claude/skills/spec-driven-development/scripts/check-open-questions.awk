# check-open-questions.awk - print each unsettled QUESTION line
# outside a fenced code block, for check-open-questions.sh.
#
# Run after parse-fences.awk with -v fence_indent=1, since a
# plan may indent a fence under a list item.
#
# With -v locate_heading=1 it prints the file line of the
# Open Questions heading instead, so the shell can turn a line
# number relative to the extracted section into a file line.
locate_heading && !in_fence && /^## Open Questions[ \t]*$/ { print NR; exit }
locate_heading { next }
fence_event != "" { next }
!in_fence && /\*\*QUESTION:\*\*/ { print }
