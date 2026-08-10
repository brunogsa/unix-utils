#!/usr/bin/env bash
# test-claude-tmux-title-compact-reminder.sh - plain-bash
# test file for claude-tmux-title-compact-reminder.sh's
# subagent guard: a SessionStart:compact firing inside a
# subagent must not receive the retitle directive, since a
# subagent must never call tmux-window-title.sh itself.
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency, matching the sibling hook suites.
#
# Scope: only the agent_id/agent_type guard. The hook's
# pre-existing tmux/entrypoint behavior is out of scope
# here -- see test-claude-implement-compact-reminder.sh for
# the same narrow-scope precedent.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_SCRIPT="$script_dir/claude-tmux-title-compact-reminder.sh"

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

# run_hook - pipes the given stdin JSON into the hook under
# test, with TMUX set and CLAUDE_CODE_ENTRYPOINT forced to
# "cli" so the pre-existing headless guards let execution
# reach the guard under test. Sets HOOK_STDOUT and HOOK_EXIT.
run_hook() {
  HOOK_STDOUT=$(printf '%s' "$1" \
    | TMUX="/tmp/fake-tmux-socket,1234,0" CLAUDE_CODE_ENTRYPOINT="cli" \
      bash "$HOOK_SCRIPT" 2>/dev/null)
  HOOK_EXIT=$?
}

# emitted_directive - the retitle text the hook adds to the
# compacting session's context, or empty when it stayed
# silent.
emitted_directive() {
  printf '%s' "$HOOK_STDOUT" \
    | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null
}

it_should_stay_silent_when_a_subagent_identified_by_agent_id_compacts() {
  run_hook '{"agent_id":"agent-a3d57f1063a3d"}'
  assert_eq "should exit 0 when a subagent identified by agent_id compacts" \
    "0" "$HOOK_EXIT"
  assert_eq "should hand a compacting subagent identified by agent_id no retitle directive" \
    "" "$(emitted_directive)"
}

it_should_stay_silent_when_a_subagent_identified_only_by_agent_type_compacts() {
  run_hook '{"agent_type":"tdd-coder"}'
  assert_eq "should hand a compacting subagent no retitle directive when it carries agent_type but no agent_id" \
    "" "$(emitted_directive)"
}

it_should_still_emit_the_directive_when_neither_agent_id_nor_agent_type_is_present() {
  run_hook '{}'
  assert_eq "should still tell the main session to re-assess its window title when no agent field is present" \
    "yes" "$([ -n "$(emitted_directive)" ] && echo yes || echo no)"
}

it_should_stay_silent_when_a_subagent_identified_by_agent_id_compacts
it_should_stay_silent_when_a_subagent_identified_only_by_agent_type_compacts
it_should_still_emit_the_directive_when_neither_agent_id_nor_agent_type_is_present

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
