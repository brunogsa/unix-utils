#!/usr/bin/env bash
# check-deterministic-gates - run every member of the
# self-review deterministic bucket in one call.
#
# Usage:
#   check-deterministic-gates.sh <plan-file> [<spec-file>]
#   check-deterministic-gates.sh --spec-only <spec-file>
#
# Members and their order live in
# references/self-review-checks.md; this script is that
# list made executable.
#
# Why one runner: callers used to assemble the invocation
# by hand, and dropped members, or reversed
# check-ac-coverage.sh's <plan> <spec> order.
#
# That reversal exits 1 with a message that reads like a
# document defect.
#
# One stdout line per gate invocation, shaped
# `PASS exit=0 <gate> (<doc>)`. FAIL carries the gate's
# exit code, WARN is always exit=1, SKIP is exit=-.
#
# A gate's own output is replayed under its FAIL or WARN
# line and never for a PASS, so a green run stays short.
#
# With no <spec-file> every gate that reads the spec is
# reported SKIP — never PASS — since `light` mode has no
# spec and a skip that reads as a pass is the defect.
#
# --spec-only is the mirror, for a spec gated before any plan
# exists. It runs exactly the spec gates and reports every
# plan gate SKIP.
#
# It is a flag, not an empty plan argument, so an unset
# variable expanding to nothing cannot reach it.
#
# WARN is check-density.sh / check-bullet-gap.py /
# check-bullet-structure.py exiting 1.
#
# The reference reports density as a [Scout], never a
# blocker, so it does not fail the run. Any other non-zero
# density exit (a usage error) is a FAIL.
#
# Runs every gate even after one fails, so the caller gets
# the whole red set in one pass.
#
# Exit codes:
#   0 - no gate failed (WARN and SKIP do not count).
#   1 - at least one gate exited non-zero.
#   2 - usage error (wrong arg count, a named file missing,
#       --spec-only without exactly one file).

set -uo pipefail

usage="usage: $(basename "$0") <plan-file> [<spec-file>] | --spec-only <spec-file>"

if [ "${1:-}" = "--spec-only" ]; then
  if [ $# -ne 2 ]; then
    echo "$usage" >&2
    exit 2
  fi
  plan=""
  spec="$2"
else
  if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "$usage" >&2
    exit 2
  fi
  plan="$1"
  spec="${2:-}"
fi

for f in ${plan:+"$plan"} ${spec:+"$spec"}; do
  if [ ! -f "$f" ]; then
    echo "error: file not found: $f" >&2
    exit 2
  fi
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
assets_dir="$(cd "$script_dir/../assets" && pwd)" || {
  echo "error: cannot resolve the assets directory: $script_dir/../assets" >&2
  exit 2
}

# doc-standards is a sibling skill dir in both the repo
# source and the ~/.claude symlink.
density_dir="$(cd "$script_dir/../../doc-standards/scripts" && pwd)" || {
  echo "error: cannot resolve the doc-standards scripts directory: $script_dir/../../doc-standards/scripts" >&2
  exit 2
}

failed=0
out_file=$(mktemp)
trap 'rm -f "$out_file"' EXIT

# run_gate - <kind> <doc-label> <gate-name> <command...>:
# runs one invocation, prints its status line, and replays
# its output when it did not pass. kind "density" downgrades
# exit 1 to WARN.
run_gate() {
  local kind="$1" label="$2" name="$3"
  shift 3
  "$@" >"$out_file" 2>&1
  local rc=$?
  local status=PASS
  if [ "$rc" -ne 0 ]; then
    if [ "$kind" = density ] && [ "$rc" -eq 1 ]; then
      status=WARN
    else
      status=FAIL
      failed=1
    fi
  fi
  printf '%s exit=%s %s (%s)\n' "$status" "$rc" "$name" "$label"
  [ "$status" = PASS ] || sed 's/^/  /' "$out_file"
}

# skip_gate - <doc-label> <gate-name>: reports an invocation
# that needs the spec when none was given.
skip_gate() {
  printf 'SKIP exit=- %s (%s)\n' "$2" "$1"
}

# run_spec_gate - like run_gate, but SKIPs when there is no
# spec.
run_spec_gate() {
  if [ -z "$spec" ]; then
    skip_gate "$2" "$3"
  else
    run_gate "$@"
  fi
}

# run_plan_gate - like run_gate, but SKIPs when there is no
# plan (--spec-only mode).
run_plan_gate() {
  if [ -z "$plan" ]; then
    skip_gate "$2" "$3"
  else
    run_gate "$@"
  fi
}

run_plan_gate gate plan check-mermaid-renders.sh bash "$script_dir/check-mermaid-renders.sh" "$plan"
run_spec_gate gate spec check-mermaid-renders.sh bash "$script_dir/check-mermaid-renders.sh" "$spec"
run_plan_gate density plan check-density.sh bash "$density_dir/check-density.sh" "$plan"
run_plan_gate density plan check-bullet-gap.py "$density_dir/check-bullet-gap.py" "$plan"
run_plan_gate density plan check-bullet-structure.py "$density_dir/check-bullet-structure.py" "$plan"
run_spec_gate density spec check-density.sh bash "$density_dir/check-density.sh" "$spec"
run_spec_gate density spec check-bullet-gap.py "$density_dir/check-bullet-gap.py" "$spec"
run_spec_gate density spec check-bullet-structure.py "$density_dir/check-bullet-structure.py" "$spec"
run_plan_gate gate plan check-sections.sh bash "$script_dir/check-sections.sh" "$plan" "$assets_dir/plan-template.md"
run_spec_gate gate spec check-sections.sh bash "$script_dir/check-sections.sh" "$spec" "$assets_dir/spec-template.md"
run_plan_gate gate plan check-test-distribution.sh bash "$script_dir/check-test-distribution.sh" "$plan"
run_plan_gate gate plan check-pr-dag.sh bash "$script_dir/check-pr-dag.sh" "$plan"
run_plan_gate gate plan check-tasks-dag.sh bash "$script_dir/check-tasks-dag.sh" "$plan"
run_plan_gate gate plan check-files-union.sh bash "$script_dir/check-files-union.sh" "$plan"
run_plan_gate gate plan check-ac-task-consistency.py "$script_dir/check-ac-task-consistency.py" "$plan"

# Plan first, spec second — the reverse of the intuitive order.
# Needs both documents, so it skips when either is absent.
if [ -z "$plan" ]; then
  skip_gate plan+spec check-ac-coverage.sh
else
  run_spec_gate gate plan+spec check-ac-coverage.sh bash "$script_dir/check-ac-coverage.sh" "$plan" "$spec"
fi
run_spec_gate gate spec check-coverage-checklists.sh bash "$script_dir/check-coverage-checklists.sh" "$spec"

exit "$failed"
