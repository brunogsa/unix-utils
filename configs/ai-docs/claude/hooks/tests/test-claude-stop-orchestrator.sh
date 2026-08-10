#!/usr/bin/env bash
# Plain-bash test file for claude-stop-orchestrator.sh.
#
# Usage:
#   bash test-claude-stop-orchestrator.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# Same no-bats rationale as the sibling test files.
#
# How the orchestrator is exercised: it resolves its children by BASH_SOURCE
# directory, so each case runs a COPY of the real script in a temp dir beside
# stub children. That keeps the orchestrator's own sequencing under test (the
# thing that broke) while making "did it notify?" observable — the real
# notification script only touches tmux and would be invisible here.
#
# claude-implement-stop-hook.sh is copied in REAL, not stubbed: the regression
# these tests guard lives in how the two scripts interact, so a stub would
# assert the bug away.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORCHESTRATOR="$hooks_dir/claude-stop-orchestrator.sh"
IMPLEMENT_GATE="$hooks_dir/claude-implement-stop-hook.sh"

work_dir=$(mktemp -d)

# The implement gate reads a fixed /tmp path (no HOME involved), so tests write
# real /tmp state files. The trap removes them; the rm clears leftovers from an
# interrupted prior run.
trap 'rm -rf "$work_dir"; rm -f /tmp/implement_sess-orch-*.json' EXIT
rm -f /tmp/implement_sess-orch-*.json

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

# build_hook_dir - assembles a temp hooks dir: the real orchestrator and the
# real implement gate, plus stubs for the three children whose behavior each
# case controls. Prints the dir path.
#
# The markdown, agent-contract and sdd stubs block only when STUB_MD_BLOCKS /
# STUB_AGENT_CONTRACT_BLOCKS / STUB_SDD_BLOCKS
# is 1 in the environment, so a case picks which gate fires without a second
# fixture dir. The notify stub records its state argument in notify.log, which
# is how every case answers "did the ping fire, and with which state?".
build_hook_dir() {
  local dir="$work_dir/hooks"
  rm -rf "$dir"
  mkdir -p "$dir"

  cp "$ORCHESTRATOR" "$dir/claude-stop-orchestrator.sh"
  cp "$IMPLEMENT_GATE" "$dir/claude-implement-stop-hook.sh"

  cat > "$dir/claude-markdown-standards-stop-hook.sh" <<'STUB'
#!/usr/bin/env bash
cat > /dev/null
[ "${STUB_MD_BLOCKS:-0}" = "1" ] && printf '%s\n' '{"decision": "block", "reason": "stub markdown gate"}'
exit 0
STUB

  cat > "$dir/claude-agent-contract-stop-hook.sh" <<'STUB'
#!/usr/bin/env bash
cat > /dev/null
[ "${STUB_AGENT_CONTRACT_BLOCKS:-0}" = "1" ] && printf '%s\n' '{"decision": "block", "reason": "stub agent-contract gate"}'
exit 0
STUB

  cat > "$dir/claude-sdd-stop-hook.sh" <<'STUB'
#!/usr/bin/env bash
cat > /dev/null
[ "${STUB_SDD_BLOCKS:-0}" = "1" ] && printf '%s\n' '{"decision": "block", "reason": "stub sdd gate"}'
exit 0
STUB

  cat > "$dir/claude-tmux-notification.sh" <<'STUB'
#!/usr/bin/env bash
cat > /dev/null
printf '%s\n' "$1" >> "$(dirname "$0")/notify.log"
exit 0
STUB

  printf '%s' "$dir"
}

# run_orchestrator - runs the orchestrator copy with the given stdin JSON,
# capturing its stdout in ORCH_OUT and whatever the notify stub recorded in
# NOTIFIED (empty string when the ping never fired).
run_orchestrator() {
  local stdin_json="$1"
  local dir
  dir=$(build_hook_dir)
  ORCH_OUT=$(printf '%s' "$stdin_json" | bash "$dir/claude-stop-orchestrator.sh" 2>/dev/null)
  NOTIFIED=$(cat "$dir/notify.log" 2>/dev/null || true)
}

# write_state - writes the given JSON body as the plain-run state file for
# session_id, at the implement gate's fixed /tmp path.
write_state() {
  local session_id="$1" body="$2"
  printf '%s' "$body" > "/tmp/implement_$session_id.json"
}

it_should_notify_done_when_no_gate_blocks_and_no_implement_run_is_active() {
  run_orchestrator '{"session_id": "sess-orch-idle", "stop_hook_active": false}'
  assert_eq "should notify done when no gate blocks and no implement run is active (notified state)" "done" "$NOTIFIED"
}

it_should_block_without_notifying_when_the_markdown_gate_blocks() {
  STUB_MD_BLOCKS=1 run_orchestrator '{"session_id": "sess-orch-md", "stop_hook_active": false}'
  assert_eq "should block without notifying when the markdown gate blocks (stdout carries the decision)" \
    "block" "$(printf '%s' "$ORCH_OUT" | jq -r '.decision // empty')"
  assert_eq "should block without notifying when the markdown gate blocks (nothing notified)" "" "$NOTIFIED"
}

it_should_block_without_notifying_when_the_agent_contract_gate_blocks() {
  STUB_AGENT_CONTRACT_BLOCKS=1 run_orchestrator '{"session_id": "sess-orch-agent", "stop_hook_active": false}'
  assert_eq "should block without notifying when the agent-contract gate blocks (stdout carries the decision)" \
    "block" "$(printf '%s' "$ORCH_OUT" | jq -r '.decision // empty')"
  assert_eq "should block without notifying when the agent-contract gate blocks (nothing notified)" "" "$NOTIFIED"
}

# The markdown gate runs first, so its block must short-circuit before the
# agent-contract gate is ever consulted — otherwise two gates could each emit a
# decision and the orchestrator would print both, which is not valid hook output.
it_should_pass_through_only_the_first_blocking_gates_decision() {
  STUB_MD_BLOCKS=1 STUB_AGENT_CONTRACT_BLOCKS=1 \
    run_orchestrator '{"session_id": "sess-orch-both", "stop_hook_active": false}'
  assert_eq "should pass through only the first blocking gate's decision (markdown wins)" \
    "stub markdown gate" "$(printf '%s' "$ORCH_OUT" | jq -r '.reason // empty')"
  assert_eq "should pass through only the first blocking gate's decision (single JSON object)" \
    "1" "$(printf '%s' "$ORCH_OUT" | grep -c 'decision')"
}

it_should_block_without_notifying_when_the_sdd_gate_blocks() {
  STUB_SDD_BLOCKS=1 run_orchestrator '{"session_id": "sess-orch-sdd", "stop_hook_active": false}'
  assert_eq "should block without notifying when the sdd gate blocks (stdout carries the decision)" \
    "block" "$(printf '%s' "$ORCH_OUT" | jq -r '.decision // empty')"
  assert_eq "should block without notifying when the sdd gate blocks (nothing notified)" "" "$NOTIFIED"
}

it_should_block_without_notifying_when_an_implement_run_is_mid_batch() {
  write_state "sess-orch-mid" '{"phase": "tasks"}'
  run_orchestrator '{"session_id": "sess-orch-mid", "stop_hook_active": false}'
  assert_eq "should block without notifying when an implement run is mid-batch (stdout carries the decision)" \
    "block" "$(printf '%s' "$ORCH_OUT" | jq -r '.decision // empty')"
  assert_eq "should block without notifying when an implement run is mid-batch (nothing notified)" "" "$NOTIFIED"
}

# The reported bug: /implement pinged success once per task. Its task loop ends
# a turn, the gate blocks it, Claude does one more thing and ends the turn again
# — and that second stop arrives with stop_hook_active=true, which disarms the
# gate's loop guard. The orchestrator used to read that silence as "the batch is
# finished" and fire the green "done" ping while the task subagent was still
# running.
it_should_stay_silent_when_an_implement_run_is_mid_batch_and_the_gates_loop_guard_has_disarmed_it() {
  write_state "sess-orch-disarmed" '{"phase": "tasks"}'
  run_orchestrator '{"session_id": "sess-orch-disarmed", "stop_hook_active": true}'
  assert_eq "should stay silent when an implement run is mid-batch and the gate's loop guard has disarmed it (nothing notified)" \
    "" "$NOTIFIED"
  assert_eq "should stay silent when an implement run is mid-batch and the gate's loop guard has disarmed it (no stdout)" \
    "" "$ORCH_OUT"
}

# The other half of the contract: a run that stopped FOR the human is exactly
# the stop worth interrupting for, so silencing it would trade one bug for another.
it_should_notify_done_when_an_implement_run_halted_for_the_human() {
  write_state "sess-orch-halted" '{"phase": "halted"}'
  run_orchestrator '{"session_id": "sess-orch-halted", "stop_hook_active": true}'
  assert_eq "should notify done when an implement run halted for the human (notified state)" "done" "$NOTIFIED"
}

it_should_notify_done_when_no_gate_blocks_and_no_implement_run_is_active
it_should_block_without_notifying_when_the_markdown_gate_blocks
it_should_block_without_notifying_when_the_agent_contract_gate_blocks
it_should_pass_through_only_the_first_blocking_gates_decision
it_should_block_without_notifying_when_the_sdd_gate_blocks
it_should_block_without_notifying_when_an_implement_run_is_mid_batch
it_should_stay_silent_when_an_implement_run_is_mid_batch_and_the_gates_loop_guard_has_disarmed_it
it_should_notify_done_when_an_implement_run_halted_for_the_human

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
