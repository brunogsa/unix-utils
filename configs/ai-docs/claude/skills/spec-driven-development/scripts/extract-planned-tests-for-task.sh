#!/usr/bin/env bash
# extract-planned-tests-for-task - extract per-task planned test titles from a plan file (plan_<slug>.md).
#
# Usage:
#   extract-planned-tests-for-task.sh <plan-path> <task-N>
#
# Prints one test title per line on stdout. Stripped of leading bullet marker,
# surrounding quotes, and trailing `[on-demand]` / `[skip]` tags.
#
# Exit codes:
#   0  - success. stdout may be empty when the task declared `**Tests (planned)**: N/A`.
#   1  - the plan file is malformed (task heading missing OR `**Tests (planned)**:` bullet missing).
#   2  - usage error (wrong arg count, non-integer task-N, plan file not found).
#
# Used by /implement's post-commit planned-test step. The orchestrator verifies each
# title against the subagent's committed diff using this stdout as its list.

set -eo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $(basename "$0") <plan-path> <task-N>" >&2
  exit 2
fi

plan="$1"
task_n="$2"

if [ ! -f "$plan" ]; then
  echo "error: plan file not found: $plan" >&2
  exit 2
fi

case "$task_n" in
  ''|*[!0-9]*)
    echo "error: task-N must be a positive integer, got: $task_n" >&2
    exit 2
    ;;
esac

# Slice the task section: from `### <N>.` heading to the next `### ` heading or EOF.
section=$(awk -v n="$task_n" '
  /^### / {
    if (in_section) exit
    stripped = $0
    sub(/^### /, "", stripped)
    if (stripped ~ ("^" n "\\.")) {
      in_section = 1
      next
    }
  }
  in_section { print }
' "$plan")

if [ -z "$section" ]; then
  echo "error: no '### $task_n.' task heading found in $plan" >&2
  exit 1
fi

# Within the section, capture content under `**Tests (planned)**:` until the next
# bold heading, next ### heading, or section divider.
tests_block=$(printf '%s\n' "$section" | awk '
  /^\*\*Tests \(planned\)\*\*:/ {
    in_block = 1
    rest = $0
    sub(/^\*\*Tests \(planned\)\*\*:[[:space:]]*/, "", rest)
    if (length(rest) > 0) {
      # Inline "N/A — reason" form short-circuits to empty output (exit 0).
      if (tolower(rest) ~ /^n\/a([^a-z]|$)/) exit
      print rest
    }
    next
  }
  in_block {
    if ($0 ~ /^\*\*[A-Z]/) exit
    if ($0 ~ /^### /) exit
    if ($0 ~ /^---$/) exit
    print
  }
')

# Did the bullet exist at all?
if ! printf '%s\n' "$section" | grep -q '^\*\*Tests (planned)\*\*:'; then
  echo "error: '**Tests (planned)**:' bullet missing in task $task_n" >&2
  exit 1
fi

# Bullet present but N/A or empty body -> exit 0 with empty stdout.
if [ -z "$tests_block" ]; then
  exit 0
fi

# Emit cleaned titles, one per line.
printf '%s\n' "$tests_block" | awk '
  /^[[:space:]]*[-*][[:space:]]+/ {
    line = $0
    sub(/^[[:space:]]*[-*][[:space:]]+/, "", line)
    sub(/[[:space:]]*\[on-demand\][[:space:]]*$/, "", line)
    sub(/[[:space:]]*\[skip\][[:space:]]*$/, "", line)
    # Strip surrounding double quotes.
    if (line ~ /^".*"$/) {
      line = substr(line, 2, length(line) - 2)
    } else if (line ~ /^'\''.*'\''$/) {
      # Strip surrounding single quotes (awk-escaped).
      line = substr(line, 2, length(line) - 2)
    }
    if (length(line) > 0) print line
  }
'
