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
# The scan reaches the hooks tree as well as the skill's
# own, because the compaction hook restates the order in a
# payload it injects the moment §8 leaves working memory.
#
# A stale order surviving there outranks the prose: it
# arrives as an instruction, at the one moment nothing else
# is left to contradict it.
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
IMPLEMENT_DIR="$script_dir/.."

# repo-green-runner.md lives outside skills/implement/ - agents/
# is a sibling of skills/ under configs/ai-docs/claude/, same
# depth HOOKS_DIR below already reaches.
AGENT_FILE="$script_dir/../../../agents/repo-green-runner.md"

# The hooks tree drives this skill from outside its own
# directory, so a stage order living only there is an order
# no scan of skills/implement/ can reach.
HOOKS_DIR="$script_dir/../../../hooks"
COMPACT_REMINDER_FILE="$HOOKS_DIR/claude-implement-compact-reminder.sh"

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

# The compaction hook re-injects the §8 sequence at the one
# moment an orchestrator has just lost it, so a stale order
# there reinstates the stranding this whole suite pins.
#
# It writes that sequence as a single physical line, which
# is why these three are compared by byte offset rather
# than by line offset.
HOOK_PUSH_MARKER='§8\.[0-9]+ push the branch'
HOOK_QUALITY_MARKER='§8\.[0-9]+ quality-gate tail'
HOOK_GREEN_MARKER='§8\.[0-9]+ repo-green gate'

# §2.2 seeds one batch-end reminder per step the interview
# left on - two, three or four - and seeds nothing for a
# step toggled off.
#
# A payload naming a fixed count therefore orders reminders
# §2.2 forbids seeding, so the count belongs to §2.2 alone.
HOOK_FIXED_REMINDER_COUNT_PATTERN='re-seed the (one|two|three|four|[0-9]+)'

# Scout #38 - signature diffing assumed the set of suite
# entries producing signatures never changes between baseline
# and gate.
#
# A test-*.sh added, deleted, or renamed mid-batch breaks that
# assumption in both directions, so baseline mode now records
# which entries ran, and gate mode carries that record through
# to diff against.
INVENTORY_KEY_MARKER='baseline.inventory'

# The two rules the agent file states as one principle and its
# inverse (repo-green-runner.md's gate-mode step). Matched as
# fixed substrings of the exact sentences, so a rewrite that
# drops either direction's reasoning fails this suite.
ADDED_ENTRY_RULE_MARKER='entry that would produce it actually ran'
REMOVED_ENTRY_RULE_MARKER='entry that produced it still ran'

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

# check_precedes_in_text <file> <earlier-regex> <later-regex>
# - the ordering contract of check_precedes, compared by byte
# offset instead of by line offset.
#
# A directive written as one long line carries both markers
# at the same line offset, where a line comparison can see
# no order at all.
check_precedes_in_text() {
  local file="$1" earlier="$2" later="$3"
  local earlier_offset later_offset
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  earlier_offset=$(grep -obE "$earlier" "$file" | head -1 | cut -d: -f1)
  later_offset=$(grep -obE "$later" "$file" | head -1 | cut -d: -f1)
  if [ -z "$earlier_offset" ]; then
    printf 'no text matching %s in %s\n' "$earlier" "$file"
    return 1
  fi
  if [ -z "$later_offset" ]; then
    printf 'no text matching %s in %s\n' "$later" "$file"
    return 1
  fi
  if [ "$earlier_offset" -ge "$later_offset" ]; then
    printf 'out of order in %s: %s at byte %s, %s at byte %s\n' \
      "$file" "$earlier" "$earlier_offset" "$later" "$later_offset"
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

# check_present <file> <fixed-string> - the mirror of
# check_absent: returns 0 only when the string occurs at
# least once in the file.
#
# Some assertions need to confirm a marker IS there (a
# recorded state key, a stated rule), not that a forbidden
# one is missing.
check_present() {
  local file="$1" needle="$2"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  if ! grep -qFi "$needle" "$file"; then
    printf 'expected string %s not found in %s\n' "$needle" "$file"
    return 1
  fi
  return 0
}

# check_pattern_absent <file> <regex> - returns 0 only when
# the pattern matches nowhere in the file.
#
# Its sibling check_absent takes a fixed string, which can
# only name the one wrong value somebody already wrote, not
# the family that value belongs to.
check_pattern_absent() {
  local file="$1" pattern="$2"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  if grep -qEi "$pattern" "$file"; then
    printf 'found forbidden pattern %s in %s\n' "$pattern" "$file"
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

it_should_assert_the_pre_flight_baseline_records_the_suite_inventory() {
  assert_eq "should assert full-suite-baseline.md records the suite inventory alongside baseline.failures" \
    "passed" "$(run_check check_present "$BASELINE_FILE" "$INVENTORY_KEY_MARKER")"
}

it_should_fail_when_the_baseline_reference_never_mentions_the_inventory() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Dropping the inventory key is the pre-fix shape: baseline
  # mode records only failures and a log path, leaving gate
  # mode with no per-entry record to diff its own against.
  grep -v -F "$INVENTORY_KEY_MARKER" "$BASELINE_FILE" > "$tmp_file"
  assert_eq "should fail when full-suite-baseline.md never mentions baseline.inventory" \
    "failed" "$(run_check check_present "$tmp_file" "$INVENTORY_KEY_MARKER")"
  rm -f "$tmp_file"
}

it_should_assert_the_repo_green_gate_dispatch_passes_the_baseline_inventory() {
  assert_eq "should assert batch-end-review.md's gate dispatch passes baseline.inventory" \
    "passed" "$(run_check check_present "$REVIEW_FILE" "$INVENTORY_KEY_MARKER")"
  assert_eq "should assert the baseline.inventory mention sits inside the repo-green gate section" \
    "passed" "$(run_check check_precedes "$REVIEW_FILE" "$REVIEW_GREEN_MARKER" "$INVENTORY_KEY_MARKER")"
}

it_should_fail_when_the_gate_dispatch_never_passes_the_inventory() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Passing failures + log path but not the inventory
  # reproduces Scout #38's premise: the gate can classify a
  # signature but has no way to tell whether the entry that
  # would produce it ever ran at baseline.
  grep -v -F "$INVENTORY_KEY_MARKER" "$REVIEW_FILE" > "$tmp_file"
  assert_eq "should fail when the repo-green gate dispatch never passes baseline.inventory" \
    "failed" "$(run_check check_present "$tmp_file" "$INVENTORY_KEY_MARKER")"
  rm -f "$tmp_file"
}

it_should_assert_the_agent_file_states_the_added_entry_rule() {
  assert_eq "should assert repo-green-runner.md states an added suite entry reads as unmeasured, not batch-caused" \
    "passed" "$(run_check check_present "$AGENT_FILE" "$ADDED_ENTRY_RULE_MARKER")"
}

it_should_fail_when_the_agent_file_omits_the_added_entry_rule() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Without this direction, a suite entry added mid-batch (a
  # new test-*.sh dropped into any of run-tests.sh's four
  # globbed trees) has no baseline signature, so the gate
  # reads its red as batch-caused and fixes red it doesn't own.
  grep -v -F "$ADDED_ENTRY_RULE_MARKER" "$AGENT_FILE" > "$tmp_file"
  assert_eq "should fail when repo-green-runner.md drops the added-entry rule" \
    "failed" "$(run_check check_present "$tmp_file" "$ADDED_ENTRY_RULE_MARKER")"
  rm -f "$tmp_file"
}

it_should_assert_the_agent_file_states_the_removed_entry_rule() {
  assert_eq "should assert repo-green-runner.md states a removed suite entry never counts as fixed" \
    "passed" "$(run_check check_present "$AGENT_FILE" "$REMOVED_ENTRY_RULE_MARKER")"
}

it_should_fail_when_the_agent_file_omits_the_removed_entry_rule() {
  local tmp_file
  tmp_file="$(mktemp)"

  # Without this direction, a suite entry removed since
  # baseline (deleted, renamed, or moved test-*.sh) vanishes
  # from the gate's own signature set, and "no longer failing"
  # reads as fixed - a false green nobody investigates.
  grep -v -F "$REMOVED_ENTRY_RULE_MARKER" "$AGENT_FILE" > "$tmp_file"
  assert_eq "should fail when repo-green-runner.md drops the removed-entry rule" \
    "failed" "$(run_check check_present "$tmp_file" "$REMOVED_ENTRY_RULE_MARKER")"
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

it_should_assert_no_auto_solve_reference_under_implement_or_its_hooks() {
  assert_eq "should assert no file under skills/implement/ references auto-solve" \
    "passed" "$(run_check check_absent_in_tree "$IMPLEMENT_DIR" "$AUTO_SOLVE_MARKER")"
  assert_eq "should assert no file under skills/implement/ references auto_solve" \
    "passed" "$(run_check check_absent_in_tree "$IMPLEMENT_DIR" "$AUTO_SOLVE_UNDERSCORE_MARKER")"
  assert_eq "should assert no hook driving the skill references auto-solve" \
    "passed" "$(run_check check_absent_in_tree "$HOOKS_DIR" "$AUTO_SOLVE_MARKER")"
  assert_eq "should assert no hook driving the skill references auto_solve" \
    "passed" "$(run_check check_absent_in_tree "$HOOKS_DIR" "$AUTO_SOLVE_UNDERSCORE_MARKER")"
}

it_should_assert_the_compaction_hook_orders_the_push_ahead_of_both_gates() {
  assert_eq "should assert the compaction hook's directive orders the push before the quality-gate tail" \
    "passed" "$(run_check check_precedes_in_text "$COMPACT_REMINDER_FILE" \
      "$HOOK_PUSH_MARKER" "$HOOK_QUALITY_MARKER")"
  assert_eq "should assert the compaction hook's directive orders the push before the repo-green gate" \
    "passed" "$(run_check check_precedes_in_text "$COMPACT_REMINDER_FILE" \
      "$HOOK_PUSH_MARKER" "$HOOK_GREEN_MARKER")"
}

it_should_assert_the_compaction_hook_names_no_fixed_reminder_count() {
  assert_eq "should assert the compaction hook's directive names no fixed batch-end reminder count" \
    "passed" "$(run_check check_pattern_absent "$COMPACT_REMINDER_FILE" \
      "$HOOK_FIXED_REMINDER_COUNT_PATTERN")"
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

it_should_fail_when_a_file_under_a_scanned_tree_still_mentions_auto_solve() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  # The removed third interview toggle, seeded once, is the
  # regression the widened scan exists to catch wherever it
  # survives - a doc, a diagram or a hook payload.
  printf -- '- Auto-solve its findings? (default yes)\n' > "$tmp_dir/leftover-toggle.md"
  assert_eq "should fail when a file under a scanned tree still mentions auto-solve" \
    "failed" "$(run_check check_absent_in_tree "$tmp_dir" "$AUTO_SOLVE_MARKER")"
  rm -rf "$tmp_dir"
}

it_should_fail_when_the_compaction_hook_orders_a_gate_ahead_of_the_push() {
  local tmp_file
  tmp_file="$(mktemp)"

  # The pre-reorder payload, gates first, on one line: what
  # a compaction would replay into an orchestrator that had
  # just lost §8 from working memory.
  printf '%s\n' \
    '§8.1 quality-gate tail → §8.2 repo-green gate → §8.3 push the branch' > "$tmp_file"
  assert_eq "should fail when the compaction hook's directive orders a gate before the push" \
    "failed" "$(run_check check_precedes_in_text "$tmp_file" \
      "$HOOK_PUSH_MARKER" "$HOOK_QUALITY_MARKER")"
  rm -f "$tmp_file"
}

it_should_fail_when_the_compaction_hook_names_a_fixed_reminder_count() {
  local tmp_file
  tmp_file="$(mktemp)"

  # A run with both gates off owes two reminders, so a
  # payload asserting four orders the orchestrator to seed
  # reminders for steps the interview turned off.
  printf '%s\n' 'If this compaction dropped them, re-seed the four from §2.2.' > "$tmp_file"
  assert_eq "should fail when the compaction hook's directive names a fixed reminder count" \
    "failed" "$(run_check check_pattern_absent "$tmp_file" \
      "$HOOK_FIXED_REMINDER_COUNT_PATTERN")"
  rm -f "$tmp_file"
}

it_should_assert_the_push_stage_is_declared_before_the_quality_gate_tail_stage
it_should_assert_the_push_stage_is_declared_before_the_repo_green_gate_stage
it_should_assert_the_pre_flight_baseline_is_dispatched_to_the_repo_green_runner
it_should_assert_the_repo_green_gate_is_dispatched_to_the_repo_green_runner
it_should_assert_the_gate_dispatch_sits_inside_the_repo_green_gate_section
it_should_fail_when_a_suite_run_names_no_repo_green_runner_dispatch
it_should_fail_when_a_dispatch_names_no_mode
it_should_assert_the_pre_flight_baseline_records_the_suite_inventory
it_should_fail_when_the_baseline_reference_never_mentions_the_inventory
it_should_assert_the_repo_green_gate_dispatch_passes_the_baseline_inventory
it_should_fail_when_the_gate_dispatch_never_passes_the_inventory
it_should_assert_the_agent_file_states_the_added_entry_rule
it_should_fail_when_the_agent_file_omits_the_added_entry_rule
it_should_assert_the_agent_file_states_the_removed_entry_rule
it_should_fail_when_the_agent_file_omits_the_removed_entry_rule
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
it_should_assert_no_auto_solve_reference_under_implement_or_its_hooks
it_should_assert_the_compaction_hook_orders_the_push_ahead_of_both_gates
it_should_assert_the_compaction_hook_names_no_fixed_reminder_count
it_should_fail_when_a_file_under_implement_still_mentions_baseline_wanted
it_should_fail_when_a_file_under_a_scanned_tree_still_mentions_auto_solve
it_should_fail_when_the_compaction_hook_orders_a_gate_ahead_of_the_push
it_should_fail_when_the_compaction_hook_names_a_fixed_reminder_count

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
