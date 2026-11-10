#!/usr/bin/env bash
# check-report.sh - count a review report's words and check its
# tier headings.
#
# Usage:
#   check-report.sh <report-file>
#
# stdin: unused.
#
# stdout: words=<n>, the wc -w count of the report.
#
# exit: 0 when the report is within the word cap and its tier
#       headings are in order.
#
#       1 when the report is over the word cap.
#
#       2 when a tier heading is out of order or repeated.
#         A "## " heading outside the tier set is also 2.
#         So is a resolvidos line of 30 or more words.
#         This wins over 1.
#
#         Lines inside a fenced code block are not checked.
#         An unclosed fence covers the rest of the report.
#         The word count still includes fenced text.
#
#       3 on a usage error: no argument was given.
#         The path must be a readable regular file.
#         A message goes to stderr.
#         No words= line is printed.

MAX_WORDS=2400
MAX_RESOLVED_WORDS=29
RESOLVED_PREFIX="**Resolvidos desde o último relatório:**"
TIERS=("Bloqueia" "Gera dúvida" "Boa prática")

# A fence line is 3 backticks after at most 3 spaces.
# This is the CommonMark rule.
FENCE_PATTERN='^ {0,3}```'

report="$1"
if [ -z "$report" ] || [ ! -f "$report" ] || [ ! -r "$report" ]; then
  echo "usage: check-report.sh <report-file> (argument missing, or the path is missing, not a regular file, or unreadable: '$report')" >&2
  exit 3
fi
words=$(wc -w < "$report" | tr -d ' ')
echo "words=$words"

# A tier heading is a whole line "## <tier>".
# Any other line is body text.
last_tier_index=-1
has_shape_defect=false
is_in_fence=false
while IFS= read -r line || [ -n "$line" ]; do
  # Trailing CR or spaces must not make a tier foreign.
  line="${line%"${line##*[![:space:]]}"}"

  # A fence line toggles the fence.
  # No check runs inside a fence.
  if [[ "$line" =~ $FENCE_PATTERN ]]; then
    if [ "$is_in_fence" = true ]; then is_in_fence=false; else is_in_fence=true; fi
    continue
  fi
  if [ "$is_in_fence" = true ]; then
    continue
  fi
  is_tier=false
  for i in "${!TIERS[@]}"; do
    if [ "$line" = "## ${TIERS[$i]}" ]; then
      is_tier=true
      if [ "$i" -le "$last_tier_index" ]; then
        has_shape_defect=true
      fi
      last_tier_index=$i
    fi
  done

  # Any other "## " heading is outside the template's set.
  if [ "$is_tier" = false ] && [[ "$line" == "## "* ]]; then
    has_shape_defect=true
  fi

  # The resolvidos line is a summary.
  # A long one is a shape defect.
  # Only at line start, after one optional bullet marker.
  if [[ "$line" == "$RESOLVED_PREFIX"* || "$line" == "- $RESOLVED_PREFIX"* \
    || "$line" == "* $RESOLVED_PREFIX"* ]]; then
    line_words=$(echo "$line" | wc -w | tr -d ' ')
    if [ "$line_words" -gt "$MAX_RESOLVED_WORDS" ]; then
      has_shape_defect=true
    fi
  fi
done < "$report"

if [ "$has_shape_defect" = true ]; then
  exit 2
fi

if [ "$words" -gt "$MAX_WORDS" ]; then
  exit 1
fi
