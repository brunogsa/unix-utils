#!/usr/bin/env bash
# test-session-auditor-frontmatter.sh - plain-bash test file
# guarding the session-auditor agent's model/effort pins.
#
# subagent-model-guard.py enforces model:opus at dispatch
# time for any caller of session-auditor, by name or
# filename stem, but it gates model only -- it never
# enforces effort. This suite is the guard for both values:
# it extracts each from the committed frontmatter block and
# checks it against the tier D14 assigns, so a later edit
# that quietly downgrades either value goes red here.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling suite
# test-audit-session-shard-tiers.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_FILE="$script_dir/../../../agents/session-auditor.md"

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

# frontmatter_block <file> - the lines strictly between the
# opening and closing --- delimiters, or empty when the file
# is absent or carries no frontmatter.
frontmatter_block() {
  local file="$1"
  [ -f "$file" ] || return 0
  sed -n '2,/^---$/p' "$file" | sed '$d'
}

# frontmatter_field <file> <key> - the value of a
# zero-indented "<key>: <value>" line inside the frontmatter
# block, or empty when the file or that key is absent.
frontmatter_field() {
  local file="$1" key="$2"
  frontmatter_block "$file" | grep -E "^${key}: " | head -n1 | sed -E "s/^${key}: *//"
}

# check_frontmatter <file> - verifies the file exists and
# pins model to opus and effort to high. Prints the failure
# reason to stdout and returns 1 on any mismatch; returns 0
# only when both values match exactly.
check_frontmatter() {
  local file="$1"
  if [ ! -f "$file" ]; then
    printf 'missing: %s\n' "$file"
    return 1
  fi
  local model effort
  model=$(frontmatter_field "$file" "model")
  effort=$(frontmatter_field "$file" "effort")
  if [ "$model" != "opus" ]; then
    printf 'model mismatch: got %s, want opus\n' "$model"
    return 1
  fi
  if [ "$effort" != "high" ]; then
    printf 'effort mismatch: got %s, want high\n' "$effort"
    return 1
  fi
  return 0
}

it_should_assert_the_frontmatter_pins_model_to_opus() {
  local model
  model=$(frontmatter_field "$AGENT_FILE" "model")
  assert_eq "should assert the frontmatter pins model to opus" "opus" "$model"
}

it_should_assert_the_frontmatter_pins_effort_to_high() {
  local effort
  effort=$(frontmatter_field "$AGENT_FILE" "effort")
  assert_eq "should assert the frontmatter pins effort to high" "high" "$effort"
}

it_should_fail_when_agent_file_is_missing() {
  local result
  if check_frontmatter "$script_dir/../../../agents/does-not-exist-session-auditor.md" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  assert_eq "should fail when agents/session-auditor.md is missing" "failed" "$result"
}

it_should_fail_when_model_value_is_altered_away_from_opus() {
  local tmp_file result
  tmp_file="$(mktemp)"
  sed 's/^model: opus$/model: sonnet/' "$AGENT_FILE" > "$tmp_file"
  if check_frontmatter "$tmp_file" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  rm -f "$tmp_file"
  assert_eq "should fail when the frontmatter's model value has been altered away from opus" \
    "failed" "$result"
}

it_should_fail_when_effort_value_is_altered_away_from_high() {
  local tmp_file result
  tmp_file="$(mktemp)"
  sed 's/^effort: high$/effort: max/' "$AGENT_FILE" > "$tmp_file"
  if check_frontmatter "$tmp_file" >/dev/null 2>&1; then
    result="passed"
  else
    result="failed"
  fi
  rm -f "$tmp_file"
  assert_eq "should fail when the frontmatter's effort value has been altered away from high" \
    "failed" "$result"
}

it_should_assert_the_frontmatter_pins_model_to_opus
it_should_assert_the_frontmatter_pins_effort_to_high
it_should_fail_when_agent_file_is_missing
it_should_fail_when_model_value_is_altered_away_from_opus
it_should_fail_when_effort_value_is_altered_away_from_high

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
