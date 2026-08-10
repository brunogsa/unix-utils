#!/usr/bin/env bash
# Plain-bash test file for claude-agent-contract-stop-hook.sh.
#
# Usage:
#   bash test-claude-agent-contract-stop-hook.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# Same no-bats rationale as the sibling test files.
#
# How the hook is exercised: it reads a transcript path out of its stdin JSON
# and derives the agents directory from the file paths it finds there, so each
# case writes a real fixture dir plus a minimal transcript naming a subset of
# it. That makes the two filters observable — which is the whole point, since
# the orchestrator's own test stubs this gate out entirely.
#
# The checker itself is NOT stubbed: these tests assert the hook's filtering,
# and a stub that always reports a violation would assert the filters away.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$hooks_dir/claude-agent-contract-stop-hook.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

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

# write_agent - writes an agent file. Passing "valid" gives it all six headings;
# anything else stops after Objective, which the checker reports as five
# missing headings — deliberately more than one, so the grouping assertion has
# something to group.
write_agent() {
  local dir="$1" name="$2" shape="$3"
  mkdir -p "$dir"
  {
    printf -- '---\nname: %s\ndescription: fixture\nmodel: sonnet\n---\n\n' "$name"
    printf '## Objective\nSomething.\n'
    if [ "$shape" = "valid" ]; then
      printf '\n## Inputs\nx.\n\n## Sources and tools\nx.\n\n## Procedure\nx.\n\n## Boundaries\nx.\n\n## Report format\nx.\n'
    fi
  } > "$dir/$name.md"
}

# write_transcript - writes a transcript naming the given absolute paths as
# this session's own Edit tool calls. Prints the transcript path.
write_transcript() {
  local out="$1"; shift
  : > "$out"
  local p
  for p in "$@"; do
    printf '{"message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"%s"}}]}}\n' "$p" >> "$out"
  done
  printf '%s' "$out"
}

# run_hook - runs the hook with the given stdin JSON, capturing stdout in
# HOOK_OUT and the decoded reason (empty when it stayed silent) in HOOK_REASON.
run_hook() {
  HOOK_OUT=$(printf '%s' "$1" | bash "$HOOK" 2>/dev/null)
  HOOK_REASON=$(printf '%s' "$HOOK_OUT" | jq -r '.reason // empty' 2>/dev/null || true)
}

it_should_block_when_an_agent_file_this_session_edited_breaks_the_contract() {
  local d="$work_dir/case-block"
  write_agent "$d/agents" touched broken
  local t; t=$(write_transcript "$d/transcript.jsonl" "$d/agents/touched.md")
  run_hook "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should block when an agent file this session edited breaks the contract (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_eq "should block when an agent file this session edited breaks the contract (names the file)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -c 'touched\.md')"
}

# The checker validates a whole DIRECTORY, so it also reports files this session
# never opened. Without the output filter, one pre-existing broken agent file
# would block every stop in every session until someone fixed a file they never
# touched.
it_should_not_block_on_a_broken_agent_file_this_session_never_touched() {
  local d="$work_dir/case-filter"
  write_agent "$d/agents" touched broken
  write_agent "$d/agents" untouched broken
  local t; t=$(write_transcript "$d/transcript.jsonl" "$d/agents/touched.md")
  run_hook "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should not block on a broken agent file this session never touched (untouched absent)" \
    "0" "$(printf '%s' "$HOOK_REASON" | grep -c 'untouched\.md')"
}

# A file missing all six headings emits five violation rows; repeating its
# absolute path on each would inject the same long string five times into the
# main context on every block.
it_should_name_each_offending_path_once_with_its_reasons_grouped() {
  local d="$work_dir/case-group"
  write_agent "$d/agents" touched broken
  local t; t=$(write_transcript "$d/transcript.jsonl" "$d/agents/touched.md")
  run_hook "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should name each offending path once with its reasons grouped (path appears once)" \
    "1" "$(printf '%s' "$HOOK_REASON" | grep -o "$d/agents/touched\.md" | wc -l | tr -d ' ')"
  assert_eq "should name each offending path once with its reasons grouped (all five reasons kept)" \
    "5" "$(printf '%s' "$HOOK_REASON" | grep -o 'missing required heading' | wc -l | tr -d ' ')"
}

it_should_stay_silent_when_the_edited_agent_file_satisfies_the_contract() {
  local d="$work_dir/case-clean"
  write_agent "$d/agents" touched valid
  local t; t=$(write_transcript "$d/transcript.jsonl" "$d/agents/touched.md")
  run_hook "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when the edited agent file satisfies the contract" "" "$HOOK_OUT"
}

# Loop guard: the hook cannot re-verify its own fix, so it must bow out on the
# stop its own block caused — otherwise an always-on gate spins forever.
it_should_stay_silent_when_its_own_block_caused_this_stop() {
  local d="$work_dir/case-loop"
  write_agent "$d/agents" touched broken
  local t; t=$(write_transcript "$d/transcript.jsonl" "$d/agents/touched.md")
  run_hook "{\"session_id\":\"s\",\"stop_hook_active\":true,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when its own block caused this stop" "" "$HOOK_OUT"
}

# A missing session signal must fail open to "no block", NOT widen the scope to
# every agent file on disk.
it_should_stay_silent_when_the_transcript_is_missing() {
  run_hook '{"session_id":"s","stop_hook_active":false}'
  assert_eq "should stay silent when the transcript is missing" "" "$HOOK_OUT"
}

it_should_stay_silent_when_the_session_touched_no_agent_file() {
  local d="$work_dir/case-scope"
  write_agent "$d/agents" touched broken
  mkdir -p "$d/docs"
  printf 'not an agent file\n' > "$d/docs/README.md"
  local t; t=$(write_transcript "$d/transcript.jsonl" "$d/docs/README.md")
  run_hook "{\"session_id\":\"s\",\"stop_hook_active\":false,\"transcript_path\":\"$t\"}"

  assert_eq "should stay silent when the session touched no agent file" "" "$HOOK_OUT"
}

it_should_block_when_an_agent_file_this_session_edited_breaks_the_contract
it_should_not_block_on_a_broken_agent_file_this_session_never_touched
it_should_name_each_offending_path_once_with_its_reasons_grouped
it_should_stay_silent_when_the_edited_agent_file_satisfies_the_contract
it_should_stay_silent_when_its_own_block_caused_this_stop
it_should_stay_silent_when_the_transcript_is_missing
it_should_stay_silent_when_the_session_touched_no_agent_file

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
