# check-ac-coverage-ac-section.awk - print the spec's
# "Acceptance Criteria" section, for check-ac-coverage.sh.
#
# Run after parse-fences.awk, which supplies in_fence and
# fence_event.
#
# A fence-shaped line prints only while inside the section,
# and never reaches the heading test below: fenced content
# prints too, and the fence only stops a `## ` line quoted as
# sample markup from ending the section early.
#
# Outside the section nothing prints, so a spec with no
# Acceptance Criteria heading yields empty output and the
# caller's whole-file fallback warning fires.
fence_event != "" { if (in_ac) print; next }

!in_fence && /^## / {
  if (in_ac) exit
  if (tolower($0) ~ /acceptance criteria/) { in_ac = 1; next }
}

in_ac { print }
