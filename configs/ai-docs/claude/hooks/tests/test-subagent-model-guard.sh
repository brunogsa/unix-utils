#!/usr/bin/env bash
# test-subagent-model-guard.sh - plain-bash test file for
# subagent-model-guard.py's pin resolution, in particular the built-in
# Explore agent type's casing.
#
# Usage:
#   bash test-subagent-model-guard.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design — a handful of small scripts don't justify a new
# cross-platform test-runner dependency in install.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/subagent-model-guard.py"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual, prints ok/not-ok.
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

# run_guard - pipes the given stdin JSON into subagent-model-guard.py and
# sets HOOK_DECISION to "allow" (empty stdout, the guard's own allow
# signal) or the JSON's hookSpecificOutput.permissionDecision otherwise.
# An optional second arg overrides HOME for the invocation only, so a
# tmp-only agents-dir fixture never touches the real ~/.claude/agents
# (which is a live symlink into this repo's configs/ai-docs/claude/agents/).
run_guard() {
  local json_input="$1" fake_home="${2:-}"
  if [ -n "$fake_home" ]; then
    HOOK_OUTPUT=$(printf '%s' "$json_input" | HOME="$fake_home" python3 "$SCRIPT" 2>/dev/null)
  else
    HOOK_OUTPUT=$(printf '%s' "$json_input" | python3 "$SCRIPT" 2>/dev/null)
  fi
  if [ -z "$HOOK_OUTPUT" ]; then
    HOOK_DECISION="allow"
  else
    HOOK_DECISION=$(printf '%s' "$HOOK_OUTPUT" | jq -r '.hookSpecificOutput.permissionDecision // "allow"')
  fi
}

# --- happy cases ---

it_should_allow_explore_with_no_model_given() {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"Explore"}}'
  assert_eq "should allow the dispatch when subagent_type is Explore and no model is given" "allow" "$HOOK_DECISION"
}

it_should_allow_explore_when_model_matches_the_sonnet_pin() {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"Explore","model":"sonnet"}}'
  assert_eq "should allow the dispatch when subagent_type is Explore and the model matches the sonnet pin" "allow" "$HOOK_DECISION"
}

# --- corner cases ---

it_should_index_the_pin_under_both_frontmatter_name_and_filename_stem() {
  local fixture_home
  fixture_home=$(mktemp -d)
  mkdir -p "$fixture_home/.claude/agents"

  # Deliberately differing name/stem — never lands under
  # configs/ai-docs/claude/agents/, so it can never register as a real
  # agent type in the live harness.
  cat > "$fixture_home/.claude/agents/guard-fixture-thing.md" <<'EOF'
---
name: GuardFixturePin
model: haiku
---
Fixture agent for SubagentModelGuardPinResolution's dual-key indexing
test. Exists only under a tmp HOME.
EOF

  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"GuardFixturePin"}}' "$fixture_home"
  assert_eq "should index the pin under both frontmatter name and filename stem, via a tmp-only fixture never under configs/ai-docs/claude/agents/, with differing name and stem (name key)" "allow" "$HOOK_DECISION"

  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"guard-fixture-thing"}}' "$fixture_home"
  assert_eq "should index the pin under both frontmatter name and filename stem, via a tmp-only fixture never under configs/ai-docs/claude/agents/, with differing name and stem (stem key)" "allow" "$HOOK_DECISION"

  rm -rf "$fixture_home"
}

it_should_deny_retired_lowercase_explore_with_no_model_given() {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"explore"}}'
  assert_eq "should deny the dispatch when the guard is invoked directly with subagent_type explore (retired lowercase, no pin resolves) and no model is given" "deny" "$HOOK_DECISION"
}

# --- failure scenarios ---

it_should_deny_explore_when_model_contradicts_the_sonnet_pin() {
  run_guard '{"tool_name":"Agent","tool_input":{"subagent_type":"Explore","model":"haiku"}}'
  assert_eq "should deny the dispatch when subagent_type is Explore and the model contradicts the sonnet pin" "deny" "$HOOK_DECISION"
}

it_should_allow_explore_with_no_model_given
it_should_allow_explore_when_model_matches_the_sonnet_pin
it_should_index_the_pin_under_both_frontmatter_name_and_filename_stem
it_should_deny_retired_lowercase_explore_with_no_model_given
it_should_deny_explore_when_model_contradicts_the_sonnet_pin

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
