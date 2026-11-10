#!/usr/bin/env bash
# check-report.sh - count the words of a review report and check its tier headings.
#
# Usage:
#   check-report.sh <report-file>
#
# stdin: unused
# stdout: words=<n>, the wc -w count of the report
# exit: 0 when the report is within the word cap and its tier headings are in order
#       1 when the report is over the word cap
#       2 when a tier heading is out of order or repeated (wins over 1)

MAX_WORDS=2400
TIERS=("Bloqueia" "Gera dúvida" "Boa prática")

report="$1"
words=$(wc -w < "$report" | tr -d ' ')
echo "words=$words"

# A tier heading is a whole line "## <tier>"; any other line is body text.
last_tier_index=-1
has_shape_defect=false
while IFS= read -r line; do
  for i in "${!TIERS[@]}"; do
    if [ "$line" = "## ${TIERS[$i]}" ]; then
      if [ "$i" -le "$last_tier_index" ]; then
        has_shape_defect=true
      fi
      last_tier_index=$i
    fi
  done
done < "$report"

if [ "$has_shape_defect" = true ]; then
  exit 2
fi

if [ "$words" -gt "$MAX_WORDS" ]; then
  exit 1
fi
