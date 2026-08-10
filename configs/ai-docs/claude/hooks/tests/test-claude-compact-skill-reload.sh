#!/usr/bin/env bash
# test-claude-compact-skill-reload.sh - plain-bash test
# file for claude-compact-skill-reload.sh's subagent guard:
# a SessionStart:compact firing inside a subagent must not
# receive the "reload your skills" directive.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling hook suites.
#
# Scope: only the agent_id/agent_type guard. The hook's
# pre-existing transcript-parsing behavior is out of scope
# here -- see test-claude-implement-compact-reminder.sh for
# the same narrow-scope precedent.
#
# Why a real transcript fixture is needed even for the
# guard cases: without a Skill-load line on disk, the hook
# would exit 0 on its own transcript-empty path, and the
# guard would never be exercised at all.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SCRIPT="$script_dir/claude-compact-skill-reload.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

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

# write_transcript - lays down a transcript with one real
# Skill-tool-call line, the shape the hook greps for.
write_transcript() {
  local path="$1"
  printf '%s\n' '{"name":"Skill","input":{"skill":"implement"}}' > "$path"
}

# run_hook - pipes the given stdin JSON into the hook under
# test. Sets HOOK_STDOUT.
run_hook() {
  HOOK_STDOUT=$(printf '%s' "$1" | bash "$HOOK_SCRIPT" 2>/dev/null)
}

# emitted_directive - the reload text the hook adds to the
# compacting session's context, or empty when it stayed
# silent.
emitted_directive() {
  printf '%s' "$HOOK_STDOUT" \
    | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null
}

it_should_stay_silent_when_a_subagent_identified_by_agent_id_compacts() {
  local transcript="$work_dir/agent-id.jsonl"
  write_transcript "$transcript"
  run_hook "{\"transcript_path\":\"$transcript\",\"agent_id\":\"agent-a3d57f1063a3d\"}"

  assert_eq "should hand a compacting subagent identified by agent_id no skill-reload directive" \
    "" "$(emitted_directive)"
}

it_should_stay_silent_when_a_subagent_identified_only_by_agent_type_compacts() {
  local transcript="$work_dir/agent-type.jsonl"
  write_transcript "$transcript"
  run_hook "{\"transcript_path\":\"$transcript\",\"agent_type\":\"tdd-coder\"}"

  assert_eq "should hand a compacting subagent no skill-reload directive when it carries agent_type but no agent_id" \
    "" "$(emitted_directive)"
}

it_should_still_emit_the_directive_when_neither_agent_id_nor_agent_type_is_present() {
  local transcript="$work_dir/main-session.jsonl"
  write_transcript "$transcript"
  run_hook "{\"transcript_path\":\"$transcript\"}"

  assert_eq "should still remind the main session to reload its skills when no agent field is present" \
    "yes" "$([ -n "$(emitted_directive)" ] && echo yes || echo no)"
}

it_should_stay_silent_when_a_subagent_identified_by_agent_id_compacts
it_should_stay_silent_when_a_subagent_identified_only_by_agent_type_compacts
it_should_still_emit_the_directive_when_neither_agent_id_nor_agent_type_is_present

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
