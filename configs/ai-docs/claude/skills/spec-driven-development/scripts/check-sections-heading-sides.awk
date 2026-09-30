# check-sections-heading-sides.awk - print "<side><TAB><heading>"
# for every `## ` heading outside a fenced code block, for
# check-sections.sh. The side flips from body to appendix once
# the literal "# Appendix" line is crossed.
#
# Run after parse-fences.awk, which supplies in_fence.
in_fence { next }
/^# Appendix[ \t]*$/ { side = "appendix"; next }
/^## / { print (side == "appendix" ? "appendix" : "body") "\t" $0 }
