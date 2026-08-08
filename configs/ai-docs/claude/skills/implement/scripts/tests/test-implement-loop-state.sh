#!/usr/bin/env bash
# test-implement-loop-state.sh - plain-bash test file for implement-loop-state.sh.
#
# Usage:
#   bash test-implement-loop-state.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design — three small scripts don't justify a new cross-platform
# test-runner dependency in install.sh.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/implement-loop-state.sh"

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

# run_script - invokes the verdict script against a state-file fixture,
# capturing stdout, stderr, and exit code into VERDICT_OUT/VERDICT_ERR/VERDICT_EXIT.
run_script() {
  local state_file="$1"
  local err_file="$work_dir/stderr.txt"
  VERDICT_OUT=$(bash "$SCRIPT" "$state_file" 2>"$err_file")
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

action_of() { printf '%s' "$VERDICT_OUT" | jq -r '.action'; }
task_of() { printf '%s' "$VERDICT_OUT" | jq -r '.task'; }

# write_fixture - writes the given JSON body to a fresh file under work_dir,
# returns its path via stdout.
write_fixture() {
  local name="$1" body="$2"
  local path="$work_dir/$name.json"
  printf '%s' "$body" > "$path"
  printf '%s' "$path"
}

it_should_verdict_next_task_when_current_task_passed_and_pending_tasks_remain() {
  local fixture
  fixture=$(write_fixture "next-task" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "pending"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict next-task when the current task passed and pending tasks remain (action)" "next-task" "$(action_of)"
  assert_eq "should verdict next-task when the current task passed and pending tasks remain (task)" "2" "$(task_of)"
}

it_should_skip_a_lower_id_task_whose_dependency_is_not_yet_done() {
  local fixture
  # Chain T3 -> T5 -> T4 (T4 depends on T5, T5 depends on T3). T3 just
  # passed; T4 has the lowest pending id but its dependency (T5) hasn't run
  # yet, so the DAG-eligible pick must be T5, not T4.
  fixture=$(write_fixture "dag-eligible" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "3", "status": "done", "depends_on": []},
      {"id": "4", "status": "pending", "depends_on": ["5"]},
      {"id": "5", "status": "pending", "depends_on": ["3"]}
    ],
    "attempts": [{"task": "3", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should pick the DAG-eligible task 5, not the lower-id but not-yet-eligible task 4 (action)" "next-task" "$(action_of)"
  assert_eq "should pick the DAG-eligible task 5, not the lower-id but not-yet-eligible task 4 (task)" "5" "$(task_of)"
}

it_should_treat_a_depends_on_id_absent_from_this_units_tasks_as_already_satisfied() {
  local fixture
  # PR-label mode: this unit's own tasks[] only has 4 and 6. Task 4 depends
  # on task 2, which belongs to an earlier, already-completed PR and so
  # never appears in this unit's tasks[] at all — that absence must count
  # as satisfied, not as a missing/unmet dependency.
  fixture=$(write_fixture "dag-cross-pr-satisfied" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "pr_label": "PR-2", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "4", "status": "pending", "depends_on": ["2"]},
      {"id": "6", "status": "done", "depends_on": []}
    ],
    "attempts": [{"task": "6", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should treat a depends_on id absent from this unit's own tasks as satisfied (action)" "next-task" "$(action_of)"
  assert_eq "should treat a depends_on id absent from this unit's own tasks as satisfied (task)" "4" "$(task_of)"
}

it_should_verdict_halted_when_pending_tasks_remain_but_none_have_dependencies_satisfied() {
  local fixture
  # Task 3 just passed. Task 5 depends on task 4, which is blocked (should
  # have been chain-aborted upstream but wasn't, in this fixture) — no
  # remaining task is DAG-eligible, so this must halt for the human rather
  # than dispatch an ineligible task or fail the script itself.
  fixture=$(write_fixture "dag-deadlock" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "3", "status": "done", "depends_on": []},
      {"id": "4", "status": "blocked", "depends_on": []},
      {"id": "5", "status": "pending", "depends_on": ["4"]}
    ],
    "attempts": [{"task": "3", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict halted when pending tasks remain but none have dependencies satisfied (action)" "halted" "$(action_of)"
}

it_should_verdict_gates_when_every_task_in_the_batch_is_done() {
  local fixture
  fixture=$(write_fixture "gates" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "done"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"},
      {"task": "2", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:10:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict gates when every task in the batch is done" "gates" "$(action_of)"
}

it_should_verdict_halted_when_current_task_passed_and_no_remaining_task_but_one_is_blocked() {
  local fixture
  fixture=$(write_fixture "halted-blocked" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "blocked"}],
    "attempts": [
      {"task": "2", "n": 1, "result": "blocked", "signature": "staging DB credentials are missing from the vault", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict halted when the current task passed, nothing remains, but a task is blocked" "halted" "$(action_of)"
}

it_should_verdict_retry_when_a_task_failed_with_fewer_than_4_attempts_and_no_stuck_streak() {
  local fixture
  fixture=$(write_fixture "retry" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "AssertionError expected 1 got 2", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "TypeError cannot read property foo", "at": "2026-07-10T10:02:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict retry when a task failed with fewer than 4 attempts and no stuck streak (action)" "retry" "$(action_of)"
  assert_eq "should verdict retry when a task failed with fewer than 4 attempts and no stuck streak (task)" "1" "$(task_of)"
}

it_should_verdict_stuck_on_the_very_first_blocked_attempt_instead_of_retrying() {
  local fixture
  fixture=$(write_fixture "blocked-first-attempt" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}, {"id": "2", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "blocked", "signature": "staging DB credentials are missing from the vault", "at": "2026-07-10T10:01:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict stuck on the very first blocked attempt instead of retrying (action)" "stuck" "$(action_of)"
  assert_eq "should verdict stuck on the very first blocked attempt instead of retrying (task)" "1" "$(task_of)"
}

it_should_verdict_stuck_when_a_task_records_its_4th_failed_attempt() {
  local fixture
  fixture=$(write_fixture "stuck-4th" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "error variant A", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "error variant B", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "error variant C", "at": "2026-07-10T10:03:00Z"},
      {"task": "1", "n": 4, "result": "fail", "signature": "error variant D", "at": "2026-07-10T10:04:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict stuck when a task records its 4th failed attempt (not on the 3rd)" "stuck" "$(action_of)"
  assert_eq "should verdict stuck when a task records its 4th failed attempt (task)" "1" "$(task_of)"
}

it_should_verdict_stuck_when_3_consecutive_identical_signatures_occur_before_the_attempt_cap() {
  local fixture
  fixture=$(write_fixture "stuck-consecutive" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "connection refused", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "connection refused", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "connection refused", "at": "2026-07-10T10:03:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict stuck when 3 consecutive identical signatures occur before the attempt cap (only 3 attempts)" "stuck" "$(action_of)"
}

it_should_not_verdict_stuck_when_identical_signatures_are_interrupted_by_a_different_one() {
  local fixture
  fixture=$(write_fixture "not-stuck-interrupted" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "connection refused", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "unrelated null pointer", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "connection refused", "at": "2026-07-10T10:03:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should not verdict stuck when identical signatures are interrupted by a different one" "retry" "$(action_of)"
}

it_should_treat_signatures_as_identical_when_they_differ_only_by_digits_paths_or_whitespace() {
  local fixture
  fixture=$(write_fixture "normalize-identical" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "Error at /src/foo.ts:12: assertion failed", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "error   at /tmp/bar42.ts:99:   assertion   failed", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "ERROR AT /Users/x/baz7.ts:7: assertion failed", "at": "2026-07-10T10:03:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should treat signatures as identical when they differ only by digits, paths, or whitespace" "stuck" "$(action_of)"
}

it_should_count_a_timeout_signature_attempt_as_a_failed_attempt() {
  local fixture
  fixture=$(write_fixture "timeout-counts" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "error variant A", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "error variant B", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "error variant C", "at": "2026-07-10T10:03:00Z"},
      {"task": "1", "n": 4, "result": "timeout", "signature": "timeout", "at": "2026-07-10T10:04:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should count a timeout-signature attempt as a failed attempt" "stuck" "$(action_of)"
}

it_should_verdict_halt_budget_when_total_dispatches_reach_4x_task_count_plus_the_gate_allowance() {
  local fixture
  # 2 tasks -> threshold = 4*2 + 4 = 12. 2 attempts (both pass) + 10 gate_dispatches = 12.
  fixture=$(write_fixture "halt-budget" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "gates",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "done"}],
    "attempts": [
      {"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"},
      {"task": "2", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:10:00Z"}
    ],
    "gate_dispatches": 10,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict halt-budget when total dispatches reach 4x task count plus the gate allowance" "halt-budget" "$(action_of)"
}

it_should_exit_non_zero_when_phase_is_anything_other_than_tasks() {
  local fixture
  fixture=$(write_fixture "non-tasks-phase" '{
    "version": 1, "session_id": "s1", "slug": "implement-loop", "phase": "tails",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 1,
    "tails": {"refactor_report": "/tmp/refactor.md", "auto_review_report": "/tmp/auto-review.md"},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should exit non-zero when phase is anything other than tasks (exit code)" "1" "$VERDICT_EXIT"
}

it_should_exit_non_zero_with_a_clear_message_when_the_state_file_is_missing_or_invalid_json() {
  local missing_fixture="$work_dir/does-not-exist.json"
  run_script "$missing_fixture"
  assert_eq "should exit non-zero with a clear message when the state file is missing (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should exit non-zero with a clear message when the state file is missing (message present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should exit non-zero with a clear message when the state file is missing (message present)\n'
  fi

  local invalid_fixture
  invalid_fixture=$(write_fixture "invalid" '{not valid json')
  run_script "$invalid_fixture"
  assert_eq "should exit non-zero with a clear message when the state file is invalid JSON (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should exit non-zero with a clear message when the state file is invalid JSON (message present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should exit non-zero with a clear message when the state file is invalid JSON (message present)\n'
  fi
}

it_should_verdict_next_task_when_current_task_passed_and_pending_tasks_remain
it_should_skip_a_lower_id_task_whose_dependency_is_not_yet_done
it_should_treat_a_depends_on_id_absent_from_this_units_tasks_as_already_satisfied
it_should_verdict_halted_when_pending_tasks_remain_but_none_have_dependencies_satisfied
it_should_verdict_gates_when_every_task_in_the_batch_is_done
it_should_verdict_halted_when_current_task_passed_and_no_remaining_task_but_one_is_blocked
it_should_verdict_retry_when_a_task_failed_with_fewer_than_4_attempts_and_no_stuck_streak
it_should_verdict_stuck_on_the_very_first_blocked_attempt_instead_of_retrying
it_should_verdict_stuck_when_a_task_records_its_4th_failed_attempt
it_should_verdict_stuck_when_3_consecutive_identical_signatures_occur_before_the_attempt_cap
it_should_not_verdict_stuck_when_identical_signatures_are_interrupted_by_a_different_one
it_should_treat_signatures_as_identical_when_they_differ_only_by_digits_paths_or_whitespace
it_should_count_a_timeout_signature_attempt_as_a_failed_attempt
it_should_verdict_halt_budget_when_total_dispatches_reach_4x_task_count_plus_the_gate_allowance
it_should_exit_non_zero_when_phase_is_anything_other_than_tasks
it_should_exit_non_zero_with_a_clear_message_when_the_state_file_is_missing_or_invalid_json

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
