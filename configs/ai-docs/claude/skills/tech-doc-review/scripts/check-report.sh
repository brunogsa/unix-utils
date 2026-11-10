#!/usr/bin/env bash
# check-report.sh - count the words of a review report.
#
# Usage:
#   check-report.sh <report-file>
#
# stdin: unused
# stdout: words=<n>, the wc -w count of the report
# exit: 0 when the report is within the word cap
#       1 when the report is over the word cap

MAX_WORDS=2400

report="$1"
words=$(wc -w < "$report" | tr -d ' ')
echo "words=$words"

if [ "$words" -gt "$MAX_WORDS" ]; then
  exit 1
fi
