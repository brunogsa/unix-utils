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
exhausted_of() { printf '%s' "$VERDICT_OUT" | jq -r '.exhausted'; }
in_progress_of() { printf '%s' "$VERDICT_OUT" | jq -r '.in_progress'; }
tasks_of() { printf '%s' "$VERDICT_OUT" | jq -rc '.tasks'; }

# run_script_flag - invokes the verdict script with a query flag
# (--budget, --next-eligible or --eligible-set) against a
# state-file fixture, capturing stdout/stderr/exit code the
# same way run_script does.
run_script_flag() {
  local flag="$1" state_file="$2"
  local err_file="$work_dir/stderr.txt"
  VERDICT_OUT=$(bash "$SCRIPT" "$flag" "$state_file" 2>"$err_file")
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "pr_label": "PR-2", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "gates",
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
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tails",
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

it_should_report_budget_not_exhausted_at_phase_tails_when_dispatches_are_under_threshold() {
  local fixture
  # 1 task -> threshold = 4*1 + 2 = 6. 1 attempt + 2 gate_dispatches = 3 < 6.
  fixture=$(write_fixture "budget-tails-under" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tails",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 2,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--budget" "$fixture"
  assert_eq "should report budget not exhausted at phase tails when dispatches are under threshold (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should report budget not exhausted at phase tails when dispatches are under threshold" "false" "$(exhausted_of)"
}

it_should_report_budget_exhausted_at_phase_tails_when_dispatches_reach_threshold() {
  local fixture
  # 1 task -> threshold = 4*1 + 2 = 6. 1 attempt + 5 gate_dispatches = 6 >= 6.
  fixture=$(write_fixture "budget-tails-over" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tails",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 5,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--budget" "$fixture"
  assert_eq "should report budget exhausted at phase tails when dispatches reach threshold (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should report budget exhausted at phase tails when dispatches reach threshold" "true" "$(exhausted_of)"
}

it_should_report_budget_not_exhausted_at_phase_gates_when_dispatches_are_under_threshold() {
  local fixture
  # Same threshold math as the phase-tails case above, at phase gates instead.
  fixture=$(write_fixture "budget-gates-under" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "gates",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 2,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--budget" "$fixture"
  assert_eq "should report budget not exhausted at phase gates when dispatches are under threshold (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should report budget not exhausted at phase gates when dispatches are under threshold" "false" "$(exhausted_of)"
}

it_should_report_budget_exhausted_at_phase_gates_when_dispatches_reach_threshold() {
  local fixture
  fixture=$(write_fixture "budget-gates-over" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "gates",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 5,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--budget" "$fixture"
  assert_eq "should report budget exhausted at phase gates when dispatches reach threshold (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should report budget exhausted at phase gates when dispatches reach threshold" "true" "$(exhausted_of)"
}

it_should_pick_the_unmet_dependency_itself_over_the_task_still_waiting_on_it() {
  local fixture
  # Task 4 depends on task 5, which hasn't run yet: 4's dependency is
  # unmet, so --next-eligible must skip past it to 5, the task that
  # actually unblocks the chain.
  fixture=$(write_fixture "next-eligible-unmet-dep" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "4", "status": "pending", "depends_on": ["5"]},
      {"id": "5", "status": "pending", "depends_on": []}
    ],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should pick the unmet dependency itself over the task still waiting on it (exit code)" "0" "$VERDICT_EXIT"
  assert_eq "should pick the unmet dependency itself over the task still waiting on it" "5" "$(task_of)"
}

it_should_pick_a_pending_task_once_its_dependency_is_done() {
  local fixture
  fixture=$(write_fixture "next-eligible-met-dep" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "3", "status": "done", "depends_on": []},
      {"id": "4", "status": "pending", "depends_on": ["3"]}
    ],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should pick a pending task once its dependency is done" "4" "$(task_of)"
}

it_should_report_none_eligible_when_the_only_path_to_a_pending_task_is_a_blocked_dependency() {
  local fixture
  # Task 2's only dependency, task 1, is blocked rather than done -- task 2
  # can never become eligible through it, and task 1 itself is excluded as
  # terminal, so no candidate is runnable.
  fixture=$(write_fixture "next-eligible-blocked-dep" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "1", "status": "blocked", "depends_on": []},
      {"id": "2", "status": "pending", "depends_on": ["1"]}
    ],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should report none eligible when the only path to a pending task is a blocked dependency" "none" "$(task_of)"
}

it_should_report_none_eligible_when_no_task_is_pending() {
  local fixture
  fixture=$(write_fixture "next-eligible-nothing-pending" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "done"}, {"id": "2", "status": "blocked"}],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should report none eligible when no task is pending" "none" "$(task_of)"
}

it_should_break_ties_by_lowest_numeric_id_not_lexical_order() {
  local fixture
  # "10" sorts before "2" lexically but not numerically -- this pins the
  # eligibility pick to sort_by(.id | tonumber), not string order.
  fixture=$(write_fixture "next-eligible-numeric-tiebreak" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "10", "status": "pending", "depends_on": []},
      {"id": "2", "status": "pending", "depends_on": []},
      {"id": "5", "status": "pending", "depends_on": []}
    ],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should break ties by lowest numeric id, not lexical order" "2" "$(task_of)"
}

it_should_treat_a_next_eligible_depends_on_id_absent_from_this_units_tasks_as_satisfied() {
  local fixture
  # Task 4 depends on task 2, which belongs to an earlier PR and never
  # appears in this unit's own tasks[] -- that absence must count as
  # satisfied, same rule the no-flag "pass" branch already applies.
  fixture=$(write_fixture "next-eligible-cross-pr-satisfied" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "pr_label": "PR-2", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "4", "status": "pending", "depends_on": ["2"]}],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should treat a --next-eligible depends_on id absent from this unit's tasks as satisfied" "4" "$(task_of)"
}

it_should_omit_an_in_progress_task_from_the_eligible_set_even_when_its_dependencies_are_done() {
  local fixture

  # Task 2 is already dispatched. Its dependencies are
  # satisfied, so only the "in_progress" status keeps it out
  # of the set -- and that exclusion is the only thing
  # stopping a second dispatch into a second worktree.
  fixture=$(write_fixture "eligible-set-omits-in-progress" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "1", "status": "done", "depends_on": []},
      {"id": "2", "status": "in_progress", "depends_on": ["1"]},
      {"id": "3", "status": "pending", "depends_on": []},
      {"id": "4", "status": "pending", "depends_on": ["1"]}
    ],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--eligible-set" "$fixture"
  assert_eq "should omit the already-dispatched task 2 from the eligible set (tasks)" '["3","4"]' "$(tasks_of)"
  assert_eq "should omit the already-dispatched task 2 from the eligible set (in_progress)" "1" "$(in_progress_of)"
}

it_should_verdict_wait_when_the_current_task_passed_and_only_live_sibling_tasks_remain() {
  local fixture

  # A wave with nothing downstream of it: task 1 just
  # passed, tasks 2 and 3 are still running, and no task
  # depends on either.
  #
  # Before the "wait" verdict existed, eligible_count==0
  # here fell straight to "halted" without ever consulting
  # in_progress_count, stopping a whole healthy wave for the
  # human while its live siblings were still working.
  fixture=$(write_fixture "wave-with-no-downstream-task" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "1", "status": "done", "depends_on": []},
      {"id": "2", "status": "in_progress", "depends_on": []},
      {"id": "3", "status": "in_progress", "depends_on": []}
    ],
    "attempts": [{"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict wait when the current task passed and only live sibling tasks remain (action)" "wait" "$(action_of)"
  assert_eq "should verdict wait when the current task passed and only live sibling tasks remain (in_progress named in reason)" "true" \
    "$(printf '%s' "$VERDICT_OUT" | jq -r '.reason | contains("2")')"
}

it_should_verdict_wait_not_halted_when_a_live_sibling_remains_alongside_a_genuinely_blocked_task() {
  local fixture

  # Task 1 just passed. Task 2 is a live sibling still
  # running; task 3 is genuinely blocked (needs a human) and
  # unrelated to task 2. Because "remaining" already drops
  # blocked tasks, task 3 never reaches the blocked_count
  # halt check on this pass -- the verdict must still wait
  # on task 2 rather than halting early on task 3's presence.
  fixture=$(write_fixture "wait-with-blocked-sibling" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "1", "status": "done", "depends_on": []},
      {"id": "2", "status": "in_progress", "depends_on": []},
      {"id": "3", "status": "blocked", "depends_on": []}
    ],
    "attempts": [
      {"task": "3", "n": 1, "result": "blocked", "signature": "staging DB credentials are missing from the vault", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 1, "result": "pass", "signature": "", "at": "2026-07-10T10:05:00Z"}
    ],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script "$fixture"
  assert_eq "should verdict wait, not halted, when a live sibling remains alongside a genuinely blocked task" "wait" "$(action_of)"
}

it_should_report_in_progress_alongside_a_next_eligible_task_of_none() {
  local fixture

  # Task 2's only dependency is the live task 1, so nothing
  # is dispatchable. "none" here means wait for task 1, not
  # halt -- the non-zero in_progress tells the two apart,
  # and failure-and-halt.md's stuck path reads it.
  fixture=$(write_fixture "next-eligible-none-with-live-sibling" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "1", "status": "in_progress", "depends_on": []},
      {"id": "2", "status": "pending", "depends_on": ["1"]}
    ],
    "attempts": [],
    "gate_dispatches": 0,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should report no eligible task while its only dependency is live (task)" "none" "$(task_of)"
  assert_eq "should report no eligible task while its only dependency is live (in_progress)" "1" "$(in_progress_of)"
}

it_should_report_none_eligible_once_the_batch_dispatch_budget_is_spent() {
  local fixture
  # 1 task -> threshold = 4*1 + 2 = 6. 4 attempts + 2 gate_dispatches = 6 >=
  # 6. Task 1 is otherwise DAG-eligible (pending, no depends_on) -- an
  # exhausted budget must still answer "none", the same way --eligible-set
  # answers an empty set, so a caller of --next-eligible never dispatches
  # past the cap that stops a runaway loop.
  fixture=$(write_fixture "next-eligible-budget-spent" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [{"id": "1", "status": "pending", "depends_on": []}],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "a", "at": "2026-07-10T10:00:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "b", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "c", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 4, "result": "fail", "signature": "d", "at": "2026-07-10T10:03:00Z"}
    ],
    "gate_dispatches": 2,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--next-eligible" "$fixture"
  assert_eq "should report none eligible once the batch dispatch budget is spent (task)" "none" "$(task_of)"
  assert_eq "should report none eligible once the batch dispatch budget is spent (reason names the budget)" "true" \
    "$(printf '%s' "$VERDICT_OUT" | jq -r '.reason | contains("budget")')"
}

it_should_return_an_empty_eligible_set_once_the_batch_budget_is_spent() {
  local fixture

  # 2 tasks -> threshold 4x2 + 2 = 10. At 10 dispatches
  # --eligible-set must name nothing, or a wave of retries
  # would run past the cap that stops a runaway loop.
  #
  # The plain verdict's halt-budget backstop never runs when
  # the orchestrator decides dispatch from this mode alone.
  fixture=$(write_fixture "eligible-set-budget-spent" '{
    "version": 3, "session_id": "s1", "slug": "implement-loop", "phase": "tasks",
    "batch_base_sha": "abc",
    "tasks": [
      {"id": "1", "status": "pending", "depends_on": []},
      {"id": "2", "status": "pending", "depends_on": []}
    ],
    "attempts": [
      {"task": "1", "n": 1, "result": "fail", "signature": "a", "at": "2026-07-10T10:00:00Z"},
      {"task": "1", "n": 2, "result": "fail", "signature": "b", "at": "2026-07-10T10:01:00Z"},
      {"task": "1", "n": 3, "result": "fail", "signature": "c", "at": "2026-07-10T10:02:00Z"},
      {"task": "1", "n": 4, "result": "fail", "signature": "d", "at": "2026-07-10T10:03:00Z"},
      {"task": "2", "n": 1, "result": "fail", "signature": "e", "at": "2026-07-10T10:04:00Z"},
      {"task": "2", "n": 2, "result": "fail", "signature": "f", "at": "2026-07-10T10:05:00Z"},
      {"task": "2", "n": 3, "result": "fail", "signature": "g", "at": "2026-07-10T10:06:00Z"},
      {"task": "2", "n": 4, "result": "fail", "signature": "h", "at": "2026-07-10T10:07:00Z"}
    ],
    "gate_dispatches": 2,
    "tails": {"refactor_report": "", "auto_review_report": ""},
    "worktree": {"created": false, "path": "", "branch": ""}, "pr": {"wanted": false}
  }')
  run_script_flag "--eligible-set" "$fixture"
  assert_eq "should return an empty eligible set once the batch budget is spent (tasks)" "[]" "$(tasks_of)"
  assert_eq "should return an empty eligible set once the batch budget is spent (exhausted)" "true" "$(exhausted_of)"
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
it_should_report_budget_not_exhausted_at_phase_tails_when_dispatches_are_under_threshold
it_should_report_budget_exhausted_at_phase_tails_when_dispatches_reach_threshold
it_should_report_budget_not_exhausted_at_phase_gates_when_dispatches_are_under_threshold
it_should_report_budget_exhausted_at_phase_gates_when_dispatches_reach_threshold
it_should_pick_the_unmet_dependency_itself_over_the_task_still_waiting_on_it
it_should_pick_a_pending_task_once_its_dependency_is_done
it_should_report_none_eligible_when_the_only_path_to_a_pending_task_is_a_blocked_dependency
it_should_report_none_eligible_when_no_task_is_pending
it_should_break_ties_by_lowest_numeric_id_not_lexical_order
it_should_treat_a_next_eligible_depends_on_id_absent_from_this_units_tasks_as_satisfied
it_should_omit_an_in_progress_task_from_the_eligible_set_even_when_its_dependencies_are_done
it_should_verdict_wait_when_the_current_task_passed_and_only_live_sibling_tasks_remain
it_should_verdict_wait_not_halted_when_a_live_sibling_remains_alongside_a_genuinely_blocked_task
it_should_report_in_progress_alongside_a_next_eligible_task_of_none
it_should_report_none_eligible_once_the_batch_dispatch_budget_is_spent
it_should_return_an_empty_eligible_set_once_the_batch_budget_is_spent

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
