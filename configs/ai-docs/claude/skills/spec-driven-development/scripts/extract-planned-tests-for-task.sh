#!/usr/bin/env bash
# extract-planned-tests-for-task - extract per-task planned test titles from a plan file (plan_<slug>.md).
#
# Usage:
#   extract-planned-tests-for-task.sh <plan-path> <task-N>
#
# Two Test Design forms, detected from extract-design-tests.sh --annotations the same way as
# check-ac-coverage.sh / check-test-distribution.sh (any it() row with a non-empty AC or T
# column puts the WHOLE plan in annotated form; a plan whose Test Design has no it() at all —
# e.g. the "N/A" escape — falls back to LIST form below, since there is nothing to annotate):
#
# ANNOTATED form (new): filters Test Design's it() titles by the task's own `T<task-N>` token,
# printing each matching bare title verbatim, in Test Design order. No `**Tests (planned)**:`
# bullet list exists in this form — the distribution lives only in the annotation.
#
# LIST form (old — unchanged; a transition path for plan_gate-roi.md/plan_script-overhaul.md-
# shaped plans, kept until no plan uses it): parses the task's own `**Tests (planned)**:`
# bullet list. Stripped of leading bullet marker, surrounding quotes, and trailing
# `[on-demand]` / `[skip]` tags.
#
# Both forms print one bare test title per line on stdout — this contract is pinned by
# /implement's post-commit planned-test step (test-sdd/SKILL.md), so it must not change.
#
# Exit codes:
#   0  - success. stdout may be empty (annotated form: no it() carries the task's T<n>; list
#        form: the task declared `**Tests (planned)**: N/A`).
#   1  - the task heading is missing, OR (list form only) the `**Tests (planned)**:` bullet
#        is missing.
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

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$task_n" in
  ''|*[!0-9]*)
    echo "error: task-N must be a positive integer, got: $task_n" >&2
    exit 2
    ;;
esac

# Slice the task section: from `### <N>.` heading to the next `### ` heading or EOF.
# Checked BEFORE form detection, for both forms: a missing task heading is a plan defect
# whichever Test Design form the plan uses.
section=$("$script_dir/plan-section.sh" "$plan" "###" "^${task_n}[.]")

if [ -z "$section" ]; then
  echo "error: no '### $task_n.' task heading found in $plan" >&2
  exit 1
fi

# Detect the plan's Test Design form. A design_extract failure (e.g. the "N/A" escape, no
# it() lines at all) means there is nothing to annotate — fall back to LIST form below, which
# already handles that case correctly via the task's own **Tests (planned)** bullet.
design_extract="$script_dir/extract-design-tests.sh"
is_annotated="no"

if annotation_rows=$("$design_extract" --annotations "$plan" 2>/dev/null); then
  is_annotated=$(printf '%s\n' "$annotation_rows" | awk -F'\t' '$3 != "" || $4 != "" { found = 1 } END { print (found ? "yes" : "no") }')
fi

if [ "$is_annotated" = "yes" ]; then
  # ANNOTATED form: print every it() title whose T column carries this task's exact "T<N>"
  # token, in Test Design order — see header comment.
  printf '%s\n' "$annotation_rows" | awk -F'\t' -v want="T${task_n}" '
    {
      n = split($4, toks, " ")
      for (i = 1; i <= n; i++) {
        if (toks[i] == want) { print $1; break }
      }
    }
  '
  exit 0
fi

# LIST form (below): unchanged from before this dispatch — see header comment.

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
