#!/usr/bin/env bash
# test-claude-tmux-title-compact-reminder.sh - plain-bash
# test file for claude-tmux-title-compact-reminder.sh's
# subagent guard.
#
# A SessionStart:compact firing inside a subagent must not
# receive the retitle directive, since a subagent must never
# call tmux-window-title.sh itself.
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
    | env -u TMUX_PANE TMUX="/tmp/fake-tmux-socket,1234,0" CLAUDE_CODE_ENTRYPOINT="cli" \
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

it_should_still_emit_the_directive_when_a_main_session_started_with_agent_flag_compacts() {
  run_hook '{"agent_type":"tdd-coder"}'
  assert_eq "should still tell a main session started with --agent (agent_type but no agent_id) to re-assess its title" \
    "yes" "$([ -n "$(emitted_directive)" ] && echo yes || echo no)"
}

it_should_still_emit_the_directive_when_neither_agent_id_nor_agent_type_is_present() {
  run_hook '{}'
  assert_eq "should still tell the main session to re-assess its window title when no agent field is present" \
    "yes" "$([ -n "$(emitted_directive)" ] && echo yes || echo no)"
}

# run_hook_in_pane - run the hook as a Claude living in pane
# `$2` of the private tmux server on socket `$1`, so the
# window-ownership check reads real tmux state. Sets
# HOOK_STDOUT and HOOK_EXIT.
run_hook_in_pane() {
  local sock="$1" pane="$2" socket_path
  socket_path=$(tmux -L "$sock" display-message -p '#{socket_path}')
  HOOK_STDOUT=$(printf '{}' \
    | TMUX="$socket_path,0,0" TMUX_PANE="$pane" CLAUDE_CODE_ENTRYPOINT="cli" \
      bash "$HOOK_SCRIPT" 2>/dev/null)
  HOOK_EXIT=$?
}

it_should_emit_the_compact_directive_only_to_the_Claude_that_owns_the_tmux_window() {
  local sock="tmux-title-compact-hook-test-$$-${RANDOM}" owner other script
  script="$script_dir/../scripts/tmux-window-title.sh"
  tmux -f /dev/null -L "$sock" new-session -d -s t cat 2>/dev/null
  owner=$(tmux -L "$sock" display-message -p '#{pane_id}')
  other=$(tmux -L "$sock" split-window -d -t "$owner" -P -F '#{pane_id}' cat)
  TMUX="$(tmux -L "$sock" display-message -p '#{socket_path}'),0,0" TMUX_PANE="$owner" \
    bash "$script" --claim-owner

  run_hook_in_pane "$sock" "$owner"
  assert_eq "should tell the Claude that owns the tmux window to re-assess its title after a compaction" \
    "yes" "$([ -n "$(emitted_directive)" ] && echo yes || echo no)"

  run_hook_in_pane "$sock" "$other"
  assert_eq "should hand a compacting Claude that does not own the tmux window no retitle directive" \
    "" "$(emitted_directive)"

  tmux -L "$sock" kill-server 2>/dev/null
}

it_should_stay_silent_when_a_subagent_identified_by_agent_id_compacts
it_should_emit_the_compact_directive_only_to_the_Claude_that_owns_the_tmux_window
it_should_still_emit_the_directive_when_a_main_session_started_with_agent_flag_compacts
it_should_still_emit_the_directive_when_neither_agent_id_nor_agent_type_is_present

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
