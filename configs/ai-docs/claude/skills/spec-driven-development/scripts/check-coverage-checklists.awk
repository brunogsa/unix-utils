# check-coverage-checklists.awk - drop fenced code blocks, fence
# lines included, for check-coverage-checklists.sh.
#
# Run after parse-fences.awk, which supplies in_fence and
# fence_event.
fence_event != "" || in_fence { next }
{ print }
