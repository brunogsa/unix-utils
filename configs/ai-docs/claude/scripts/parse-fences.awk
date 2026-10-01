# parse-fences.awk - CommonMark code-fence state machine.
#
# Load it before a caller's own awk file.
#
# Usage:
#   awk [-v fence_indent=1] [-v fence_exit_code=N] \
#     [-v fence_file=<path>] [-v fence_line_offset=N] \
#     -f <scripts-dir>/parse-fences.awk -f <caller>.awk <file>
#
# A fence opens on 3+ backticks or tildes at column 0.
#
# It closes only on a line with the same character, a run at
# least as long as the opener, and no info string. Every
# other line inside is content.
#
# Per record, before the caller's rules run:
#   in_fence     1 while inside a fence, after this line
#   fence_event  "open", "close", "inner" (a fence-shaped line
#                that stays content), or "" for prose;
#
#   fence_tail   text after the run of a fence line (the
#                info string of an opener);
#
#   fence_line   line number where the current fence opened.
#
# stdout: nothing.
#
# stderr and exit: a fence still open at EOF prints
# "error: unclosed code fence opened at line N in <file>" and
# exits fence_exit_code (default 2). END rules loaded after
# this file are skipped.
#
# fence_indent=1 also accepts a fence indented by spaces or
# tabs.
#
# A caller piping a slice of a document in has no FILENAME and
# an NR counted from the slice, so that message would name no
# file and a line the reader cannot find.
#
# fence_file and fence_line_offset let it hand over the real
# coordinates: the path to name, and the number of document
# lines preceding the slice.
#
# Both are unset by default, leaving the message byte-identical
# for a caller that passes a file path.
#
# An offset that is not a whole non-negative number is a caller
# bug, so it exits 2 on the spot rather than shifting the line
# to somewhere nobody can check.

BEGIN {
  fence_start_pattern = fence_indent ? "^[ \t]*(```|~~~)" : "^(```|~~~)"

  if (fence_line_offset != "" && fence_line_offset !~ /^[0-9]+$/) {
    print "error: fence_line_offset must be a non-negative integer, got \"" \
      fence_line_offset "\"" > "/dev/stderr"
    fence_bad_config = 1
    exit 2
  }
}

{ fence_event = "" }

$0 ~ fence_start_pattern {
  match($0, /^[ \t]*/)
  fence_lead = RLENGTH
  fence_marker = substr($0, fence_lead + 1, 1)
  fence_run = 0
  while (substr($0, fence_lead + fence_run + 1, 1) == fence_marker) fence_run++
  fence_tail = substr($0, fence_lead + fence_run + 1)

  if (!in_fence) {
    in_fence = 1
    fence_char = fence_marker
    fence_len = fence_run
    fence_line = NR
    fence_event = "open"
  } else if (fence_marker == fence_char && fence_run >= fence_len && fence_tail ~ /^[ \t]*$/) {
    in_fence = 0
    fence_event = "close"
  } else {
    fence_event = "inner"
  }
}

END {
  if (fence_bad_config) exit 2

  if (in_fence) {
    fence_reported_file = fence_file != "" ? fence_file : FILENAME
    print "error: unclosed code fence opened at line " \
      (fence_line + fence_line_offset) " in " fence_reported_file > "/dev/stderr"
    exit (fence_exit_code ? fence_exit_code : 2)
  }
}
