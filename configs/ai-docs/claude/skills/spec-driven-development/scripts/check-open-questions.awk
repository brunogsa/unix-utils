# check-open-questions.awk - print each unsettled QUESTION line
# outside a fenced code block, for check-open-questions.sh.
#
# Run after parse-fences.awk with -v fence_indent=1, since a
# plan may indent a fence under a list item.
fence_event != "" { next }
!in_fence && /\*\*QUESTION:\*\*/ { print }
