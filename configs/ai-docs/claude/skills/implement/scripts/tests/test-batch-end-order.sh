#!/usr/bin/env bash
# test-batch-end-order.sh - plain-bash test file guarding
# the batch-end stage ORDER that SKILL.md and
# references/batch-end-review.md declare in prose.
#
# Two audited /implement sessions finished their feature
# work and then stalled on a gate that never emitted a
# verdict. Push sat behind that gate, so 9 commits in one
# repo and 16 in the other stayed local across ~40 hours.
#
# The order this suite pins puts the push and the draft PR
# ahead of both gates, so a gate that cannot terminate can
# no longer strand delivered work.
#
# The phase-presented assertion is the load-bearing one: it
# is the single line standing between this reorder and a run
# that could legally stop with its gates unrun, having
# already opened a PR.
#
# It also pins that both full-suite runs - the pre-flight
# baseline and the batch-end gate - are dispatched to the
# repo-green-runner agent, each naming its mode.
#
# Running them inline is what let those two sessions stall
# with no verdict and no separable cost.
#
# Assertions anchor on prose markers and compare their line
# offsets, never on hardcoded line numbers, so ordinary
# edits above a marker do not fail the suite.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling hook/skill
# suites (e.g. test-audit-session-shard-tiers.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_FILE="$script_dir/../SKILL.md"
REVIEW_FILE="$script_dir/../references/batch-end-review.md"
BASELINE_FILE="$script_dir/../references/full-suite-baseline.md"

# SKILL.md's four stage-summary bullets. Loose enough to
# match the old order too, so a run against the pre-reorder
# file reports "out of order" rather than "marker missing".
SKILL_PUSH_MARKER='^- \*\*§8\.[0-9]+ — push'
SKILL_QUALITY_MARKER='^- \*\*§8\.[0-9]+ — the quality-gate tail'
SKILL_GREEN_MARKER='^- \*\*§8\.[0-9]+ — repo-green gate'

# batch-end-review.md's own section markers. The push one
# matches its numbered Finalize step wherever that step
# lives, which is what moved.
REVIEW_PUSH_MARKER='\*\*Push the branch — always'
REVIEW_QUALITY_MARKER='^## The quality-gate tail'
REVIEW_GREEN_MARKER='^## Repo-green GATE'
REVIEW_PRESENTED_MARKER='phase: "presented"'
REVIEW_PACKAGE_MARKER='^## The review package'

# Both suite runs are dispatched to the repo-green-runner
# agent rather than run inline.
#
# Two audited sessions stalled on an inline gate that never
# emitted a verdict, so the dispatch is what makes a verdict
# mandatory and gives the run its own usage-report line.
#
# The mode markers are matched without their surrounding
# markdown backticks, so the prose can format them freely.
RUNNER_AGENT_MARKER='subAgent=repo-green-runner'
BASELINE_MODE_MARKER='mode: baseline'
GATE_MODE_MARKER='mode: gate'

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# line_of <file> <regex> - 1-based line number of the FIRST
# line matching the regex, or empty when the file or the
# marker is absent.
line_of() {
  local file="$1" pattern="$2"
  [ -f "$file" ] || return 0
  grep -n -m1 -E "$pattern" "$file" | cut -d: -f1
}

# check_precedes <file> <earlier-regex> <later-regex> -
# returns 0 only when both markers exist and the earlier one
# really sits at the lower line offset. Prints the reason to
# stdout and returns 1 on any failure.
check_precedes() {
  local file="$1" earlier="$2" later="$3"
  local earlier_line later_line
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  earlier_line=$(line_of "$file" "$earlier")
  later_line=$(line_of "$file" "$later")
  if [ -z "$earlier_line" ]; then
    printf 'no line matching %s in %s\n' "$earlier" "$file"
    return 1
  fi
  if [ -z "$later_line" ]; then
    printf 'no line matching %s in %s\n' "$later" "$file"
    return 1
  fi
  if [ "$earlier_line" -ge "$later_line" ]; then
    printf 'out of order in %s: %s at line %s, %s at line %s\n' \
      "$file" "$earlier" "$earlier_line" "$later" "$later_line"
    return 1
  fi
  return 0
}

# check_presented_after_gates <file> - returns 0 only when
# the file writes phase: "presented" at least once and EVERY
# such write sits below both gate sections.
#
# A presented written above either gate would let the Stop
# hook release a run whose gates never executed, with the PR
# already open.
check_presented_after_gates() {
  local file="$1"
  local quality_line green_line last_gate_line presented_line
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  quality_line=$(line_of "$file" "$REVIEW_QUALITY_MARKER")
  green_line=$(line_of "$file" "$REVIEW_GREEN_MARKER")
  if [ -z "$quality_line" ] || [ -z "$green_line" ]; then
    printf 'a gate section is missing from %s\n' "$file"
    return 1
  fi
  last_gate_line="$quality_line"
  if [ "$green_line" -gt "$last_gate_line" ]; then
    last_gate_line="$green_line"
  fi
  local presented_lines
  presented_lines=$(grep -n -F "$REVIEW_PRESENTED_MARKER" "$file" | cut -d: -f1)
  if [ -z "$presented_lines" ]; then
    printf 'no phase: "presented" write found in %s\n' "$file"
    return 1
  fi
  for presented_line in $presented_lines; do
    if [ "$presented_line" -le "$last_gate_line" ]; then
      printf 'phase: "presented" at line %s precedes the last gate at line %s in %s\n' \
        "$presented_line" "$last_gate_line" "$file"
      return 1
    fi
  done
  return 0
}

# check_dispatches <file> <mode-regex> - returns 0 only when
# the file both names the repo-green-runner agent and states
# the mode it dispatches that agent in.
#
# Naming the agent without its mode is the failure worth
# catching: the runner behaves differently per mode, and it
# infers nothing the caller left unsaid.
check_dispatches() {
  local file="$1" mode_pattern="$2"
  local agent_line mode_line
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  agent_line=$(line_of "$file" "$RUNNER_AGENT_MARKER")
  mode_line=$(line_of "$file" "$mode_pattern")
  if [ -z "$agent_line" ]; then
    printf 'no repo-green-runner dispatch in %s\n' "$file"
    return 1
  fi
  if [ -z "$mode_line" ]; then
    printf 'dispatch in %s never names %s\n' "$file" "$mode_pattern"
    return 1
  fi
  return 0
}

# run_check <check-fn> <args...> - "passed" or "failed", so
# a negative control asserts on the verdict rather than on
# the reason text.
run_check() {
  if "$@" >/dev/null 2>&1; then
    printf 'passed'
  else
    printf 'failed'
  fi
}

it_should_assert_the_push_stage_is_declared_before_the_quality_gate_tail_stage() {
  assert_eq "should assert SKILL.md declares the push stage before the quality-gate tail stage" \
    "passed" "$(run_check check_precedes "$SKILL_FILE" "$SKILL_PUSH_MARKER" "$SKILL_QUALITY_MARKER")"
  assert_eq "should assert batch-end-review.md places its push step before the quality-gate tail section" \
    "passed" "$(run_check check_precedes "$REVIEW_FILE" "$REVIEW_PUSH_MARKER" "$REVIEW_QUALITY_MARKER")"
}

it_should_assert_the_push_stage_is_declared_before_the_repo_green_gate_stage() {
  assert_eq "should assert SKILL.md declares the push stage before the repo-green gate stage" \
    "passed" "$(run_check check_precedes "$SKILL_FILE" "$SKILL_PUSH_MARKER" "$SKILL_GREEN_MARKER")"
  assert_eq "should assert batch-end-review.md places its push step before the repo-green gate section" \
    "passed" "$(run_check check_precedes "$REVIEW_FILE" "$REVIEW_PUSH_MARKER" "$REVIEW_GREEN_MARKER")"
}

it_should_assert_the_run_is_marked_presented_only_after_both_gates_have_run() {
  assert_eq "should assert every phase presented write sits below both gate sections" \
    "passed" "$(run_check check_presented_after_gates "$REVIEW_FILE")"
}

it_should_fail_when_a_batch_end_file_is_missing() {
  assert_eq "should fail when the batch-end file it reads is missing" \
    "failed" "$(run_check check_precedes "$script_dir/../references/does-not-exist.md" \
      "$REVIEW_PUSH_MARKER" "$REVIEW_QUALITY_MARKER")"
}

it_should_fail_when_the_push_step_is_moved_back_behind_a_gate() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Rebuild the pre-reorder shape: drop the push step from
  # wherever it now sits and re-append it at the end of the
  # file, behind both gate sections.
  {
    grep -v -E "$REVIEW_PUSH_MARKER" "$REVIEW_FILE"
    printf '1. **Push the branch — always, on every batch end.**\n'
  } > "$tmp_file"
  assert_eq "should fail when the push step is moved back behind the quality-gate tail section" \
    "failed" "$(run_check check_precedes "$tmp_file" "$REVIEW_PUSH_MARKER" "$REVIEW_QUALITY_MARKER")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_run_is_marked_presented_before_the_gates_run() {
  local tmp_file
  tmp_file="$(mktemp)"

  # A presented write hoisted above every heading is the
  # exact regression this assertion exists to catch: gates
  # unrun, PR already open, Stop hook free to release.
  #
  # The fixture line carries no markdown backticks: the
  # check greps the marker as a fixed string, so backticks
  # would only read to shellcheck as a command it must warn
  # about never expanding.
  {
    printf 'Set phase: "presented" here.\n'
    cat "$REVIEW_FILE"
  } > "$tmp_file"
  assert_eq "should fail when a phase presented write is hoisted above the gate sections" \
    "failed" "$(run_check check_presented_after_gates "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_run_never_marks_itself_presented() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Losing the write entirely leaves the Stop hook blocking
  # forever, so an absent marker is a failure, not a pass by
  # vacuous truth.
  grep -v -F "$REVIEW_PRESENTED_MARKER" "$REVIEW_FILE" > "$tmp_file"
  assert_eq "should fail when the file carries no phase presented write at all" \
    "failed" "$(run_check check_presented_after_gates "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_assert_the_pre_flight_baseline_is_dispatched_to_the_repo_green_runner() {
  assert_eq "should assert the baseline step dispatches the repo-green-runner in baseline mode" \
    "passed" "$(run_check check_dispatches "$BASELINE_FILE" "$BASELINE_MODE_MARKER")"
}

it_should_assert_the_repo_green_gate_is_dispatched_to_the_repo_green_runner() {
  assert_eq "should assert the repo-green gate dispatches the repo-green-runner in gate mode" \
    "passed" "$(run_check check_dispatches "$REVIEW_FILE" "$GATE_MODE_MARKER")"
}

it_should_assert_the_gate_dispatch_sits_inside_the_repo_green_gate_section() {
  assert_eq "should assert the gate dispatch is written below the repo-green gate heading" \
    "passed" "$(run_check check_precedes "$REVIEW_FILE" "$REVIEW_GREEN_MARKER" "$RUNNER_AGENT_MARKER")"
  assert_eq "should assert the gate dispatch is written above the review-package section" \
    "passed" "$(run_check check_precedes "$REVIEW_FILE" "$RUNNER_AGENT_MARKER" "$REVIEW_PACKAGE_MARKER")"
}

it_should_fail_when_a_suite_run_names_no_repo_green_runner_dispatch() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Dropping the dispatch is the pre-agent shape: the suite
  # runs inline in the main session, where nothing forces a
  # verdict and the cost hides inside the session's own.
  grep -v -E "$RUNNER_AGENT_MARKER" "$REVIEW_FILE" > "$tmp_file"
  assert_eq "should fail when the repo-green gate names no repo-green-runner dispatch" \
    "failed" "$(run_check check_dispatches "$tmp_file" "$GATE_MODE_MARKER")"
  rm -f "$tmp_file"
}

it_should_fail_when_a_dispatch_names_no_mode() {
  local tmp_file
  tmp_file="$(mktemp)"

  # The runner reads its mode from the caller and infers
  # nothing, so a dispatch missing it would run the wrong
  # half of the agent - baseline fixing nothing where a gate
  # was wanted, or a gate fixing where a baseline was.
  grep -v -E "$GATE_MODE_MARKER" "$REVIEW_FILE" > "$tmp_file"
  assert_eq "should fail when the repo-green gate dispatch never names gate mode" \
    "failed" "$(run_check check_dispatches "$tmp_file" "$GATE_MODE_MARKER")"
  rm -f "$tmp_file"
}

it_should_assert_the_push_stage_is_declared_before_the_quality_gate_tail_stage
it_should_assert_the_push_stage_is_declared_before_the_repo_green_gate_stage
it_should_assert_the_pre_flight_baseline_is_dispatched_to_the_repo_green_runner
it_should_assert_the_repo_green_gate_is_dispatched_to_the_repo_green_runner
it_should_assert_the_gate_dispatch_sits_inside_the_repo_green_gate_section
it_should_fail_when_a_suite_run_names_no_repo_green_runner_dispatch
it_should_fail_when_a_dispatch_names_no_mode
it_should_assert_the_run_is_marked_presented_only_after_both_gates_have_run
it_should_fail_when_a_batch_end_file_is_missing
it_should_fail_when_the_push_step_is_moved_back_behind_a_gate
it_should_fail_when_the_run_is_marked_presented_before_the_gates_run
it_should_fail_when_the_run_never_marks_itself_presented

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
