#!/usr/bin/env bash
# check-report.sh - count the words of a review report.
#
# Usage:
#   check-report.sh <report-file>
#
# stdin: unused
# stdout: words=<n>, the wc -w count of the report
# exit: 0 when the report passes every check

report="$1"
words=$(wc -w < "$report" | tr -d ' ')
echo "words=$words"
