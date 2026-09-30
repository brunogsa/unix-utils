# check-sections-has-appendix.awk - exit 0 when a literal
# "# Appendix" line sits outside a fenced code block, for
# check-sections.sh.
#
# Run after parse-fences.awk, which supplies in_fence.
!in_fence && /^# Appendix[ \t]*$/ { found = 1 }
END { exit !found }
