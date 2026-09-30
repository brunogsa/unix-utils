# check-ac-coverage-ac-section.awk - print the spec's
# "Acceptance Criteria" section, for check-ac-coverage.sh.
#
# Run after parse-fences.awk, which supplies in_fence and
# fence_event.
#
# Every fence-shaped line prints, in or out of the section, and
# fenced content prints too: the fence only stops a `## ` line
# quoted as sample markup from ending the section early.
fence_event != "" { print; next }

!in_fence && /^## / {
  if (in_ac) exit
  if (tolower($0) ~ /acceptance criteria/) { in_ac = 1; next }
}

in_ac { print }
