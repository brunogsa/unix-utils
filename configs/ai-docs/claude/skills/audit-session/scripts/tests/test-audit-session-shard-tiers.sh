#!/usr/bin/env bash
# test-audit-session-shard-tiers.sh - plain-bash test file
# guarding the per-shard model/effort tiers that
# assets/subagent-prompt.md declares in prose.
#
# Only the auditor agent's own model:opus pin is
# hook-enforced (subagent-model-guard.py gates model
# only, never effort); the five shard model values and
# five effort values live in prose a later edit could
# change silently. This suite is that guard: it extracts
# each shard's dispatch line from the one committed
# fixed-schema table and checks it against the tier the
# plan assigns.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling hook/skill
# suites (e.g. test-claude-tmux-title-compact-reminder.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE="$script_dir/../assets/subagent-prompt.md"

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

# shard_dispatch_line <file> <shard-id> - the one
# dispatch-table row for the given shard id (S1..S4),
# or empty when the file or that row is absent.
shard_dispatch_line() {
  local file="$1" shard_id="$2"
  [ -f "$file" ] || return 0
  grep -E "^\| $shard_id \|" "$file" || true
}

# shard_model <line> - the model= value quoted in a
# dispatch line, or empty when none is present.
shard_model() {
  printf '%s' "$1" | grep -oE 'model=[a-z]+' | head -n1 | cut -d= -f2
}

# shard_effort <line> - the effort= value quoted in a
# dispatch line, or empty when none is present.
shard_effort() {
  printf '%s' "$1" | grep -oE 'effort=[a-z]+' | head -n1 | cut -d= -f2
}

# check_shard_tiers <file> - verifies the file exists and
# every one of S1..S5 names an explicit model matching its
# assigned tier below. Prints the first mismatch reason to
# stdout and returns 1 on any failure; returns 0 only when
# all five shards match exactly.
check_shard_tiers() {
  local file="$1"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  local shard_id expected_model expected_effort line model effort
  for entry in "S1:opus:max" "S2:opus:max" "S3:opus:high" "S4:opus:high" "S5:opus:high"; do
    shard_id="${entry%%:*}"
    expected_model="${entry#*:}"; expected_model="${expected_model%%:*}"
    expected_effort="${entry##*:}"
    line=$(shard_dispatch_line "$file" "$shard_id")
    if [ -z "$line" ]; then
      printf 'no dispatch row found for %s\n' "$shard_id"
      return 1
    fi
    model=$(shard_model "$line")
    effort=$(shard_effort "$line")
    if [ -z "$model" ]; then
      printf '%s names no explicit model\n' "$shard_id"
      return 1
    fi
    if [ "$model" != "$expected_model" ] || [ "$effort" != "$expected_effort" ]; then
      printf '%s tier mismatch: got model=%s effort=%s, want model=%s effort=%s\n' \
        "$shard_id" "$model" "$effort" "$expected_model" "$expected_effort"
      return 1
    fi
  done
  return 0
}

it_should_assert_s1_time_is_dispatched_with_model_opus_and_effort_max() {
  local line
  line=$(shard_dispatch_line "$PROMPT_FILE" "S1")
  assert_eq "should assert S1 Time is dispatched with model opus" "opus" "$(shard_model "$line")"
  assert_eq "should assert S1 Time is dispatched with effort max" "max" "$(shard_effort "$line")"
}

it_should_assert_s2_money_is_dispatched_with_model_opus_and_effort_max() {
  local line
  line=$(shard_dispatch_line "$PROMPT_FILE" "S2")
  assert_eq "should assert S2 Money is dispatched with model opus" "opus" "$(shard_model "$line")"
  assert_eq "should assert S2 Money is dispatched with effort max" "max" "$(shard_effort "$line")"
}

it_should_assert_s3_work_done_is_dispatched_with_model_opus_and_effort_high() {
  local line
  line=$(shard_dispatch_line "$PROMPT_FILE" "S3")
  assert_eq "should assert S3 Work done is dispatched with model opus" "opus" "$(shard_model "$line")"
  assert_eq "should assert S3 Work done is dispatched with effort high" "high" "$(shard_effort "$line")"
}

it_should_assert_s4_status_and_next_steps_is_dispatched_with_model_opus_and_effort_high() {
  local line
  line=$(shard_dispatch_line "$PROMPT_FILE" "S4")
  assert_eq "should assert S4 Status and next steps is dispatched with model opus" "opus" "$(shard_model "$line")"
  assert_eq "should assert S4 Status and next steps is dispatched with effort high" "high" "$(shard_effort "$line")"
}

it_should_assert_s5_recommendations_is_dispatched_with_model_opus_and_effort_high() {
  local line
  line=$(shard_dispatch_line "$PROMPT_FILE" "S5")
  assert_eq "should assert S5 Recommendations is dispatched with model opus" "opus" "$(shard_model "$line")"
  assert_eq "should assert S5 Recommendations is dispatched with effort high" "high" "$(shard_effort "$line")"
}

it_should_assert_every_shard_dispatch_names_an_explicit_model() {
  local shard_id line model all_present="yes"
  for shard_id in S1 S2 S3 S4 S5; do
    line=$(shard_dispatch_line "$PROMPT_FILE" "$shard_id")
    model=$(shard_model "$line")
    [ -n "$model" ] || all_present="no"
  done
  assert_eq "should assert every one of the five shard dispatches names an explicit model" \
    "yes" "$all_present"
}

it_should_fail_when_subagent_prompt_is_missing() {
  local result
  if check_shard_tiers "$script_dir/../assets/does-not-exist-subagent-prompt.md" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  assert_eq "should fail when assets/subagent-prompt.md is missing" "failed" "$result"
}

it_should_fail_when_a_shard_tier_is_altered() {
  local tmp_file result
  tmp_file="$(mktemp)"
  # S2 (Money) is assigned effort=max -- downgrade it to
  # effort=high to simulate a later edit silently drifting
  # the tier away from what the plan assigned.
  sed 's/^| S2 |\(.*\)effort=max)/| S2 |\1effort=high)/' "$PROMPT_FILE" > "$tmp_file"
  if check_shard_tiers "$tmp_file" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  rm -f "$tmp_file"
  assert_eq "should fail when any one shard's model or effort value has been altered from its assigned tier" \
    "failed" "$result"
}

it_should_fail_when_a_shard_dispatch_omits_its_model() {
  local tmp_file result
  tmp_file="$(mktemp)"
  # S3 (Work done) loses its ", model=opus" clause entirely
  # -- simulates a dispatch line edited down to the unpinned
  # general-purpose default the guard hook would deny.
  sed 's/^| S3 |\(.*\), model=opus\(.*\)/| S3 |\1\2/' "$PROMPT_FILE" > "$tmp_file"
  if check_shard_tiers "$tmp_file" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  rm -f "$tmp_file"
  assert_eq "should fail when any one shard's dispatch omits its explicit model" \
    "failed" "$result"
}

it_should_assert_s1_time_is_dispatched_with_model_opus_and_effort_max
it_should_assert_s2_money_is_dispatched_with_model_opus_and_effort_max
it_should_assert_s3_work_done_is_dispatched_with_model_opus_and_effort_high
it_should_assert_s4_status_and_next_steps_is_dispatched_with_model_opus_and_effort_high
it_should_assert_s5_recommendations_is_dispatched_with_model_opus_and_effort_high
it_should_assert_every_shard_dispatch_names_an_explicit_model
it_should_fail_when_subagent_prompt_is_missing
it_should_fail_when_a_shard_tier_is_altered
it_should_fail_when_a_shard_dispatch_omits_its_model

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
