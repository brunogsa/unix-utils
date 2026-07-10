#!/usr/bin/env bash
# test-implement-loop-metrics.sh - plain-bash test file for implement-loop-metrics.sh.
#
# Usage:
#   bash test-implement-loop-metrics.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design (see plan_implement-loop.md, Reusage report) — three small scripts
# don't justify a new cross-platform test-runner dependency in install.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/implement-loop-metrics.sh"

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

# run_script - invokes the metrics script, capturing stdout/stderr/exit code
# into METRICS_OUT/METRICS_ERR/METRICS_EXIT.
run_script() {
  local err_file="$work_dir/stderr.txt"
  METRICS_OUT=$(bash "$SCRIPT" "$@" 2>"$err_file")
  METRICS_EXIT=$?
  METRICS_ERR=$(cat "$err_file")
}

write_fixture() {
  local name="$1" body="$2"
  local path="$work_dir/$name.json"
  printf '%s' "$body" > "$path"
  printf '%s' "$path"
}

it_should_sum_subagent_tokens_across_attempts_and_tails_from_the_state_file() {
  local fixture
  fixture=$(write_fixture "sum-tokens" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "presented",
    "batch_base_sha": "abc", "started_at": "", "presented_at": "",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "done"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "x", "tokens": 1000, "at": "t1"},
      {"task": "1", "n": 2, "result": "pass", "signature": "", "tokens": 500, "at": "t2"},
      {"task": "2", "n": 1, "result": "pass", "signature": "", "tokens": 2000, "at": "t3"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "r.md", "auto_review_report": "a.md", "tokens": {"gate": 100, "refactor": 200, "auto_review": 300, "pr": 0}},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  local per_task_1 per_task_2 subagent_total
  per_task_1=$(printf '%s' "$METRICS_OUT" | jq -r '.tokens.per_task."1"')
  per_task_2=$(printf '%s' "$METRICS_OUT" | jq -r '.tokens.per_task."2"')
  subagent_total=$(printf '%s' "$METRICS_OUT" | jq -r '.tokens.subagent_total')
  assert_eq "should sum subagent tokens across attempts and tails from the state file (task 1 total)" "1500" "$per_task_1"
  assert_eq "should sum subagent tokens across attempts and tails from the state file (task 2 total)" "2000" "$per_task_2"
  assert_eq "should sum subagent tokens across attempts and tails from the state file (subagent_total incl. tails)" "4100" "$subagent_total"
}

it_should_compute_wall_clock_duration_from_the_started_and_presented_timestamps() {
  local fixture
  fixture=$(write_fixture "duration" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "presented",
    "batch_base_sha": "abc", "started_at": "2026-07-10T10:00:00Z", "presented_at": "2026-07-10T11:30:00Z",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "tokens": 0, "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": "", "tokens": {"gate": 0, "refactor": 0, "auto_review": 0, "pr": 0}},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  local duration
  duration=$(printf '%s' "$METRICS_OUT" | jq -r '.duration_seconds')
  assert_eq "should compute wall-clock duration from the started and presented timestamps" "5400" "$duration"
}

it_should_add_orchestrator_tokens_when_a_session_transcript_path_is_provided() {
  local fixture transcript
  fixture=$(write_fixture "with-transcript" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "presented",
    "batch_base_sha": "abc", "started_at": "", "presented_at": "",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "tokens": 1000, "at": "t1"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": "", "tokens": {"gate": 0, "refactor": 0, "auto_review": 0, "pr": 0}},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')

  transcript="$work_dir/transcript.jsonl"
  {
    printf '%s\n' '{"type": "assistant", "message": {"usage": {"input_tokens": 100, "output_tokens": 50, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 5}}}'
    printf '%s\n' '{"type": "assistant", "message": {"usage": {"input_tokens": 100, "output_tokens": 50, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 5}}}'
  } > "$transcript"

  run_script "$fixture"
  local orchestrator_total_without
  orchestrator_total_without=$(printf '%s' "$METRICS_OUT" | jq -r '.tokens.orchestrator_total')
  assert_eq "should add orchestrator tokens when a session transcript path is provided (0 without transcript)" "0" "$orchestrator_total_without"

  run_script "$fixture" "$transcript"
  local orchestrator_total_with total
  orchestrator_total_with=$(printf '%s' "$METRICS_OUT" | jq -r '.tokens.orchestrator_total')
  total=$(printf '%s' "$METRICS_OUT" | jq -r '.tokens.total')
  assert_eq "should add orchestrator tokens when a session transcript path is provided (summed from usage entries)" "330" "$orchestrator_total_with"
  assert_eq "should add orchestrator tokens when a session transcript path is provided (total includes it)" "1330" "$total"
}

it_should_list_tasks_whose_summed_attempt_tokens_exceed_the_soft_200k_budget() {
  local fixture
  fixture=$(write_fixture "over-budget" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "presented",
    "batch_base_sha": "abc", "started_at": "", "presented_at": "",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "done"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "pass", "signature": "", "tokens": 250000, "at": "t1"},
      {"task": "2", "n": 1, "result": "pass", "signature": "", "tokens": 150000, "at": "t2"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": "", "tokens": {"gate": 0, "refactor": 0, "auto_review": 0, "pr": 0}},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  local over_budget
  over_budget=$(printf '%s' "$METRICS_OUT" | jq -c '.over_budget_tasks')
  assert_eq "should list tasks whose summed attempt tokens exceed the soft 200k budget" '["1"]' "$over_budget"
}

it_should_exit_non_zero_with_a_clear_message_when_the_state_file_is_missing_or_invalid_json() {
  local missing_fixture="$work_dir/does-not-exist.json"
  run_script "$missing_fixture"
  assert_eq "should exit non-zero with a clear message when the state file is missing (exit code)" "1" "$METRICS_EXIT"
  if [ -n "$METRICS_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should exit non-zero with a clear message when the state file is missing (message present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should exit non-zero with a clear message when the state file is missing (message present)\n'
  fi

  local invalid_fixture
  invalid_fixture=$(write_fixture "invalid" '{not valid json')
  run_script "$invalid_fixture"
  assert_eq "should exit non-zero with a clear message when the state file is invalid JSON (exit code)" "1" "$METRICS_EXIT"
  if [ -n "$METRICS_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should exit non-zero with a clear message when the state file is invalid JSON (message present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should exit non-zero with a clear message when the state file is invalid JSON (message present)\n'
  fi
}

it_should_sum_subagent_tokens_across_attempts_and_tails_from_the_state_file
it_should_compute_wall_clock_duration_from_the_started_and_presented_timestamps
it_should_add_orchestrator_tokens_when_a_session_transcript_path_is_provided
it_should_list_tasks_whose_summed_attempt_tokens_exceed_the_soft_200k_budget
it_should_exit_non_zero_with_a_clear_message_when_the_state_file_is_missing_or_invalid_json

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
