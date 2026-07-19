#!/usr/bin/env bash
# get-pr-tasks.sh - resolves a PR Breakdown's PR-N label to its listed task-id list.
#
# Usage:
#   get-pr-tasks.sh <plan-file> <PR-N>
#
# Extracts the "## PR Breakdown" section from <plan-file>, finds the entry
# labeled <PR-N> (e.g. "PR-2"), and prints its "Tasks: <N, N>" clause verbatim.
# The printed format is the same comma-space "N, N" list /implement's own
# <task-ids> argument already expects (see implement/SKILL.md's Usage
# section), so /implement's pre-flight can pipe this straight through.
#
# Exit codes:
#   0 - PR-N found; its task-id list printed to stdout.
#   1 - PR-N not found in the plan's PR Breakdown (diagnostic on stderr).
#   2 - usage error (wrong arg count, plan file missing, section unparsable).

set -eo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $(basename "$0") <plan-file> <PR-N>" >&2
  exit 2
fi

plan_file="$1"
pr_label="$2"

if [ ! -f "$plan_file" ]; then
  echo "error: plan file not found: $plan_file" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# parse-pr-breakdown.sh does the section-extraction + entry-parse pipeline
# shared with need-git-checkout.sh and check-pr-dependencies-ready.sh; this
# script only consumes the Tasks: field (column 2) of its TSV output. Its
# non-zero exit codes distinguish a trivial section (1: absent/"Single PR."),
# which needs this script's own $pr_label-specific diagnostic below, from a
# malformed one (2: content present but unparsable), whose diagnostic
# parse-pr-breakdown.sh already printed to stderr itself - re-printing it
# here would duplicate the line, since $(...) only captures stdout, never
# stderr. Assigned inside an if-condition (never a bare assignment) so a
# non-zero exit here doesn't abort the script under `set -e`.
if entries=$("$script_dir/parse-pr-breakdown.sh" "$plan_file"); then
  :
else
  parse_exit=$?
  if [ "$parse_exit" -eq 1 ]; then
    echo "error: PR-N label not found in the plan's PR Breakdown (section absent or Single PR.): $pr_label" >&2
    exit 1
  else
    exit 2
  fi
fi

# Looked up via a plain string match (never a failing awk exit code): under
# `set -e`, a command substitution's failure inside a bare assignment (not an
# if/while/&&/|| condition) aborts the script before the diagnostic below can
# print, so "not found" must surface as an empty string, not a non-zero exit.
matched_entry=$(printf '%s\n' "$entries" | awk -F'\t' -v target="$pr_label" '$1 == target { print; exit }')

if [ -z "$matched_entry" ]; then
  echo "error: PR-N label not found in the plan's PR Breakdown: $pr_label" >&2
  exit 1
fi

tasks=$(printf '%s' "$matched_entry" | cut -f2)

if [ -z "$tasks" ]; then
  echo "error: PR-N entry found but its Tasks: clause could not be parsed: $pr_label" >&2
  exit 2
fi

printf '%s\n' "$tasks"
