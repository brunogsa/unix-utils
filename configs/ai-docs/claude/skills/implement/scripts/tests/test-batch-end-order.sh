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
FLOWCHART_FILE="$script_dir/../assets/flowchart.md"
IMPLEMENT_DIR="$script_dir/.."

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

# §1.2 used to ask the baseline and the gate as two
# independent yes/no questions, which admitted the reachable
# combination gate=yes, baseline=no.
#
# Under it the repo-green gate has no baseline to diff
# against and HALTs a finished batch with every commit still
# local.
#
# The two questions are now one: SKILL_MERGED_GATE_MARKER is
# the bullet's bold heading text, and it is the ONLY toggle
# §1.2 may declare governing the baseline.
#
# A still-present old baseline question is the regression
# this section-scoped check exists to catch.
SKILL_MERGED_GATE_MARKER='^- \*\*Run the repo-green gate at batch end\?\*\*'
SKILL_OLD_BASELINE_QUESTION_MARKER='^- \*\*Capture a full-suite green baseline before starting\?\*\*'

# The state object's `baseline` key used to carry its own
# `wanted` boolean, redundant with `repo_green_gate.wanted`
# once the two questions merged.
#
# A leftover reference to it anywhere under
# skills/implement/ is drift from a doc the merge should
# have retargeted.
BASELINE_WANTED_STRING='baseline.wanted'

# The interview used to ask a third, independent toggle -
# "Auto-solve its findings?" - that a prior commit removed
# from the skill body without updating this diagram, which
# stays authoritative for the flow it depicts.
#
# check_absent matches case-insensitively, but "auto-solve"
# and "auto_solve" are still two distinct fixed strings, so
# both are checked.
AUTO_SOLVE_MARKER='auto-solve'
AUTO_SOLVE_UNDERSCORE_MARKER='auto_solve'

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

# check_absent <file> <fixed-string> - returns 0 only when
# the string never occurs in the file.
#
# Fixed-string, case-insensitive match (grep -Fi), so a
# caller passing a literal dotted key never needs its own
# escaping, and prose that capitalizes the same word
# (e.g. "Auto-solve") still gets caught.
check_absent() {
  local file="$1" needle="$2"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  if grep -qFi "$needle" "$file"; then
    printf 'found forbidden string %s in %s\n' "$needle" "$file"
    return 1
  fi
  return 0
}

# check_absent_in_tree <dir> <fixed-string> - same contract as
# check_absent, scanned recursively over every file under dir.
#
# Excludes this guard script's own basename: it legitimately
# carries the needle as literal test data (constants, function
# names), and that self-reference is not the regression this
# scan exists to catch.
check_absent_in_tree() {
  local dir="$1" needle="$2"
  if [ ! -d "$dir" ]; then
    printf 'missing directory: %s\n' "$dir"
    return 1
  fi
  local self_name hit
  self_name=$(basename "${BASH_SOURCE[0]}")
  hit=$(grep -rlFi "$needle" "$dir" 2>/dev/null | grep -v "/${self_name}$")
  if [ -n "$hit" ]; then
    printf 'found forbidden string %s under %s:\n%s\n' "$needle" "$dir" "$hit"
    return 1
  fi
  return 0
}

# check_single_interview_toggle <file> - returns 0 only when
# SKILL.md's §1.2 section declares the merged gate/baseline
# toggle exactly once and carries no leftover separate
# baseline question.
#
# Two independent yes/no questions admit gate=yes,
# baseline=no - a combination the repo-green-runner agent
# HALTs on, stranding a finished batch's commits unpushed.
# One toggle makes that combination unreachable.
check_single_interview_toggle() {
  local file="$1"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  local start_line end_line section merged_count old_count
  start_line=$(grep -n -m1 -E '^### 1\.2\.' "$file" | cut -d: -f1)
  end_line=$(grep -n -m1 -E '^### 1\.3\.' "$file" | cut -d: -f1)
  if [ -z "$start_line" ] || [ -z "$end_line" ]; then
    printf 'section 1.2 boundaries not found in %s\n' "$file"
    return 1
  fi
  section=$(sed -n "${start_line},${end_line}p" "$file")
  merged_count=$(printf '%s\n' "$section" | grep -c -E "$SKILL_MERGED_GATE_MARKER")
  old_count=$(printf '%s\n' "$section" | grep -c -E "$SKILL_OLD_BASELINE_QUESTION_MARKER")
  if [ "$merged_count" -ne 1 ]; then
    printf 'expected exactly one merged gate/baseline toggle in section 1.2 of %s, found %s\n' \
      "$file" "$merged_count"
    return 1
  fi
  if [ "$old_count" -ne 0 ]; then
    printf 'old separate baseline question still present in section 1.2 of %s\n' "$file"
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

it_should_assert_skill_md_never_mentions_baseline_wanted() {
  assert_eq "should assert SKILL.md contains no baseline.wanted occurrence" \
    "passed" "$(run_check check_absent "$SKILL_FILE" "$BASELINE_WANTED_STRING")"
}

it_should_assert_section_1_2_declares_exactly_one_merged_toggle() {
  assert_eq "should assert section 1.2 declares exactly one toggle governing both baseline and gate" \
    "passed" "$(run_check check_single_interview_toggle "$SKILL_FILE")"
}

it_should_fail_when_skill_md_still_mentions_baseline_wanted() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Reintroduce the leftover dotted key SKILL.md's prose
  # used to carry, so the check fails on a file that
  # regressed back to referencing it.
  #
  # Must be the exact dotted form check_absent searches
  # for, not merely a JSON key/value pair that happens to
  # sit nearby.
  #
  # The backticks belong to the fixture: they are the
  # markdown code spans SKILL.md's prose wraps this key in,
  # and check_absent greps the dotted form as a fixed
  # string.
  #
  # Double quotes would make the shell try to run them, so
  # SC2016 is reporting the literal this line needs rather
  # than an expansion that goes missing.
  #
  # shellcheck disable=SC2016
  { cat "$SKILL_FILE"; printf 'empty when `%s` is `false`.\n' "$BASELINE_WANTED_STRING"; } > "$tmp_file"
  assert_eq "should fail when SKILL.md still mentions baseline.wanted" \
    "failed" "$(run_check check_absent "$tmp_file" "$BASELINE_WANTED_STRING")"
  rm -f "$tmp_file"
}

it_should_fail_when_section_1_2_still_declares_two_separate_questions() {
  local tmp_file line_num
  tmp_file="$(mktemp)"
  line_num=$(grep -n -m1 -E "$SKILL_MERGED_GATE_MARKER" "$SKILL_FILE" | cut -d: -f1)

  # Reconstruct the pre-merge shape: re-insert the old,
  # separate baseline question right after the merged
  # toggle bullet, so section 1.2 declares both again.
  #
  # That is the exact combination that let gate=yes,
  # baseline=no reach the repo-green-runner agent's HALT
  # rule.
  {
    head -n "$line_num" "$SKILL_FILE"
    printf -- '- **Capture a full-suite green baseline before starting?** (yes/no) — on yes, section 1.6 runs the full suite first.\n'
    tail -n "+$((line_num + 1))" "$SKILL_FILE"
  } > "$tmp_file"
  assert_eq "should fail when section 1.2 still declares two separate baseline/gate questions" \
    "failed" "$(run_check check_single_interview_toggle "$tmp_file")"
  rm -f "$tmp_file"
}

it_should_assert_no_baseline_wanted_reference_anywhere_under_implement() {
  assert_eq "should assert no file under skills/implement/ references baseline.wanted" \
    "passed" "$(run_check check_absent_in_tree "$IMPLEMENT_DIR" "$BASELINE_WANTED_STRING")"
}

it_should_assert_flowchart_carries_no_auto_solve_reference() {
  assert_eq "should assert flowchart.md carries no auto-solve reference" \
    "passed" "$(run_check check_absent "$FLOWCHART_FILE" "$AUTO_SOLVE_MARKER")"
  assert_eq "should assert flowchart.md carries no auto_solve reference" \
    "passed" "$(run_check check_absent "$FLOWCHART_FILE" "$AUTO_SOLVE_UNDERSCORE_MARKER")"
}

it_should_fail_when_a_file_under_implement_still_mentions_baseline_wanted() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  # A single leftover file anywhere under the tree is the
  # regression this dir-wide scan exists to catch, so seed
  # exactly one such file.
  printf '%s\n' "$BASELINE_WANTED_STRING" > "$tmp_dir/leftover-reference.md"
  assert_eq "should fail when a file under the scanned tree still mentions baseline.wanted" \
    "failed" "$(run_check check_absent_in_tree "$tmp_dir" "$BASELINE_WANTED_STRING")"
  rm -rf "$tmp_dir"
}

it_should_fail_when_flowchart_still_mentions_auto_solve() {
  local tmp_file
  tmp_file="$(mktemp)"

  { cat "$FLOWCHART_FILE"; printf '\n- Auto-solve its findings? (default yes)\n'; } > "$tmp_file"
  assert_eq "should fail when flowchart.md still mentions auto-solve" \
    "failed" "$(run_check check_absent "$tmp_file" "$AUTO_SOLVE_MARKER")"
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
it_should_assert_skill_md_never_mentions_baseline_wanted
it_should_assert_section_1_2_declares_exactly_one_merged_toggle
it_should_fail_when_skill_md_still_mentions_baseline_wanted
it_should_fail_when_section_1_2_still_declares_two_separate_questions
it_should_assert_no_baseline_wanted_reference_anywhere_under_implement
it_should_assert_flowchart_carries_no_auto_solve_reference
it_should_fail_when_a_file_under_implement_still_mentions_baseline_wanted
it_should_fail_when_flowchart_still_mentions_auto_solve

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
