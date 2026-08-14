#!/usr/bin/env bash

# test-run-tests-lock.sh - covers the single-run lock in
# ./run-tests.sh: only one full-suite run may execute at a time
# on this machine.

# Usage:
#   bash test-run-tests-lock.sh

# Why the lock exists: five Claude Code sessions sharing one
# checkout launched five concurrent `bash ./run-tests.sh`
# processes (the oldest 7m54s in).
#
# They starved each other for CPU and three callers gave up
# waiting, so the serialization belongs in the script rather
# than in every caller's memory.

# No bats dependency by design — same precedent as the sibling
# suites under configs/ai-docs/claude/:
#
# - tests/test-run-tests-pytest-integration.sh
# - scripts/tests/test-statusline-tier.sh

# Every fixture builds a throwaway sandbox holding a COPY of the
# real run-tests.sh, a stub `pytest`, and a single fast fake
# suite as the run's body.
#
# The real four-tree suite is never invoked: running it here
# would take minutes and recreate the very contention this lock
# exists to remove.

# run-tests.sh keys its lock on its own script directory, so
# each sandbox takes a lock of its own and these fixtures can
# never block — or be blocked by — a real run in this checkout.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"
run_tests_src="$repo_root/run-tests.sh"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual,
# prints ok/not-ok.
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

# assert_contains - inline assert helper: fails unless $haystack
# contains the literal substring $needle.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected to contain: %s\n  actual:\n%s\n' "$description" "$needle" "$haystack"
  fi
}

# fresh_sandbox - a scratch repo-root standing in for the real
# one.
#
# It holds a copy of run-tests.sh, whose globs anchor on their
# own script location and so resolve inside the sandbox rather
# than in the real test trees, a stub pytest that exits 0 in
# milliseconds, and a private TMPDIR the lock lands in.
fresh_sandbox() {
  local sandbox
  sandbox="$(mktemp -d "${TMPDIR:-/tmp}/run-tests-lock.XXXXXX")"
  cp "$run_tests_src" "$sandbox/run-tests.sh"
  mkdir -p \
    "$sandbox/bin" \
    "$sandbox/tmp" \
    "$sandbox/configs/ai-docs/claude/tests" \
    "$sandbox/configs/ai-docs/claude/scripts/tests" \
    "$sandbox/configs/ai-docs/claude/hooks/tests" \
    "$sandbox/configs/ai-docs/claude/skills/fake-skill/scripts/tests"

  # Stubbed so the fixture measures the lock, not pytest's
  # multi-second collection of the real python suites.
  cat > "$sandbox/bin/pytest" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
  chmod +x "$sandbox/bin/pytest"

  printf '%s\n' "$sandbox"
}

# add_body_suite - the run's whole body: one fake suite that
# records every entry, holds for $hold_seconds, and exits
# $exit_code.
#
# The mkdir probe is the overlap detector: mkdir is atomic, so a
# second body running at the same time as the first cannot
# create the marker and records the overlap instead.
add_body_suite() {
  local sandbox="$1" exit_code="$2" hold_seconds="$3"
  cat > "$sandbox/configs/ai-docs/claude/tests/test-lock-body-probe.sh" <<EOF
#!/usr/bin/env bash
if ! mkdir "$sandbox/in-suite-body" 2>/dev/null; then
  printf 'overlap\n' >> "$sandbox/overlap.log"
fi
printf 'ran\n' >> "$sandbox/body-runs.log"
sleep $hold_seconds
rmdir "$sandbox/in-suite-body" 2>/dev/null
exit $exit_code
EOF
}

# start_run - launches the sandboxed run-tests.sh in the
# background and publishes its pid in $run_pid.
#
# `exec` matters: without it $! names the wrapping subshell, and
# the SIGINT/SIGTERM fixtures below would signal that wrapper
# instead of the script under test.
#
# A global rather than a captured stdout, because a background
# job started inside $(...) is a child of that subshell and
# `wait` here could never reap it.
run_pid=0
start_run() {
  local sandbox="$1" out_file="$2"
  (
    cd "$sandbox" && exec env \
      TMPDIR="$sandbox/tmp" \
      PATH="$sandbox/bin:$PATH" \
      bash ./run-tests.sh
  ) > "$out_file" 2>&1 &
  run_pid=$!
}

# wait_for_run - reaps $1 and publishes its exit status in
# $wait_status, giving up after $2 polls of 0.05s.
#
# The bound is what keeps a locking bug from hanging this suite
# forever: a run that never returns is reported as status 124,
# which fails its fixture like any other wrong exit code.
wait_status=0
wait_for_run() {
  local pid="$1" limit_polls="$2" waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$limit_polls" ]; then
      kill -9 "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      wait_status=124
      return 0
    fi
    sleep 0.05
    waited=$((waited + 1))
  done
  wait "$pid" 2>/dev/null
  wait_status=$?
}

# reap_run - the unbounded counterpart of wait_for_run, for a
# run this suite has already SIGKILLed.
#
# That process is guaranteed to die, so waiting on it can never
# hang, and polling `kill -0` on an unreaped zombie would stall
# until the bound expired instead.
reap_run() {
  wait "$1" 2>/dev/null
  wait_status=$?
}

# wait_for_lock - blocks until the sandboxed run has actually
# taken its lock, so the fixtures never race on a fixed sleep.
# Returns non-zero if it never appears.
wait_for_lock() {
  local sandbox="$1" waited=0
  while [ "$waited" -lt 100 ]; do
    lock_present "$sandbox" && return 0
    sleep 0.05
    waited=$((waited + 1))
  done
  return 1
}

# wait_for_body_start - blocks until the sandboxed run has
# actually entered its fake suite.
#
# The concurrency fixture starts its second run off this rather
# than off the lock appearing, so the second run provably
# arrives while the first is mid-body — with or without a lock
# in place.
wait_for_body_start() {
  local sandbox="$1" waited=0
  while [ "$waited" -lt 100 ]; do
    [ -f "$sandbox/body-runs.log" ] && return 0
    sleep 0.05
    waited=$((waited + 1))
  done
  return 1
}

# lock_present - true while any lock directory exists in the
# sandbox's private TMPDIR. Globbed rather than spelled out, so
# the fixtures stay blind to how run-tests.sh names the lock.
lock_present() {
  local sandbox="$1" candidate
  for candidate in "$sandbox/tmp"/run-tests-*.lock; do
    [ -d "$candidate" ] && return 0
  done
  return 1
}

# lock_released_within - polls for the lock to disappear, up to
# $2 tenths of a second. Polling rather than asserting once,
# because a signalled run only reaches its trap after the suite
# it had already started returns.
lock_released_within() {
  local sandbox="$1" limit_tenths="$2" waited=0
  while [ "$waited" -lt "$limit_tenths" ]; do
    lock_present "$sandbox" || return 0
    sleep 0.1
    waited=$((waited + 1))
  done
  return 1
}

it_should_keep_a_second_run_out_of_the_suite_body_until_the_first_finishes() {
  local sandbox output_b
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 0 0.5

  start_run "$sandbox" "$sandbox/run-a.out"
  local first_pid=$run_pid
  wait_for_body_start "$sandbox"

  start_run "$sandbox" "$sandbox/run-b.out"
  local second_pid=$run_pid

  wait_for_run "$first_pid" 150
  local first_status=$wait_status
  wait_for_run "$second_pid" 150
  local second_status=$wait_status
  output_b="$(cat "$sandbox/run-b.out")"

  assert_eq \
    "RunTestsLock > concurrent runs > should never let two runs execute the suite body at the same time" \
    "no overlap" \
    "$([ -f "$sandbox/overlap.log" ] && printf 'overlap' || printf 'no overlap')"
  assert_eq \
    "RunTestsLock > concurrent runs > should still run the second run's suites once the first releases the lock" \
    "2" \
    "$(wc -l < "$sandbox/body-runs.log" | tr -d ' ')"
  assert_contains \
    "RunTestsLock > concurrent runs > should tell the caller another run is in progress rather than sitting silently idle" \
    "$output_b" "another run is in progress"
  assert_eq \
    "RunTestsLock > concurrent runs > should pass the first run" \
    "0" "$first_status"
  assert_eq \
    "RunTestsLock > concurrent runs > should pass the second run once it stops waiting" \
    "0" "$second_status"

  rm -rf "$sandbox"
}

it_should_release_the_lock_after_a_passing_run() {
  local sandbox held
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 0 0.3

  start_run "$sandbox" "$sandbox/run.out"

  # Observed mid-run, because "no lock afterwards" is also what
  # a run that never took one looks like.
  held="$(wait_for_lock "$sandbox" && printf 'held' || printf 'never held')"
  wait_for_run "$run_pid" 150

  assert_eq \
    "RunTestsLock > passing run > should exit zero" \
    "0" "$wait_status"
  assert_eq \
    "RunTestsLock > passing run > should hold the lock while the suites are running" \
    "held" "$held"
  assert_eq \
    "RunTestsLock > passing run > should leave no lock behind for the next run to wait on" \
    "released" \
    "$(lock_present "$sandbox" && printf 'still held' || printf 'released')"

  rm -rf "$sandbox"
}

it_should_release_the_lock_after_a_run_a_failing_suite_made_exit_non_zero() {
  local sandbox output held
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 1 0.3

  start_run "$sandbox" "$sandbox/run.out"
  held="$(wait_for_lock "$sandbox" && printf 'held' || printf 'never held')"
  wait_for_run "$run_pid" 150
  output="$(cat "$sandbox/run.out")"

  assert_eq \
    "RunTestsLock > failing suite > should hold the lock while the failing suite is running" \
    "held" "$held"

  assert_eq \
    "RunTestsLock > failing suite > should still exit non-zero so the lock never masks a red suite" \
    "1" "$wait_status"
  assert_contains \
    "RunTestsLock > failing suite > should still report the failing suite by name" \
    "$output" "FAIL  configs/ai-docs/claude/tests/test-lock-body-probe.sh"
  assert_eq \
    "RunTestsLock > failing suite > should release the lock even though the run ended in failure" \
    "released" \
    "$(lock_present "$sandbox" && printf 'still held' || printf 'released')"

  rm -rf "$sandbox"
}

# $1 names the signal, so SIGINT and SIGTERM share one body: the
# behaviour asserted (an interrupted run must not wedge every
# later run) is identical for both.
assert_lock_released_after_signal() {
  local signal="$1" sandbox held
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 0 0.4

  start_run "$sandbox" "$sandbox/run.out"
  held="$(wait_for_lock "$sandbox" && printf 'held' || printf 'never held')"
  kill -"$signal" "$run_pid" 2>/dev/null
  wait_for_run "$run_pid" 150

  assert_eq \
    "RunTestsLock > interrupted run > should hold the lock up to the moment SIG$signal arrives" \
    "held" "$held"
  assert_eq \
    "RunTestsLock > interrupted run > should release the lock when the run is stopped with SIG$signal" \
    "released" \
    "$(lock_released_within "$sandbox" 30 && printf 'released' || printf 'still held')"

  rm -rf "$sandbox"
}

it_should_release_the_lock_when_the_run_is_interrupted() {
  assert_lock_released_after_signal "INT"
  assert_lock_released_after_signal "TERM"
}

it_should_break_a_lock_whose_owning_process_is_gone() {
  local sandbox output
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 0 2

  # SIGKILL runs no trap, which is exactly how a killed session
  # leaves a lock held by a pid that no longer exists.
  start_run "$sandbox" "$sandbox/killed.out"
  wait_for_lock "$sandbox"
  kill -9 "$run_pid" 2>/dev/null
  reap_run "$run_pid"

  start_run "$sandbox" "$sandbox/run.out"
  wait_for_run "$run_pid" 150
  output="$(cat "$sandbox/run.out")"

  assert_eq \
    "RunTestsLock > stale lock > should run to completion instead of waiting forever on a dead owner" \
    "0" "$wait_status"

  # Read off this run's own report rather than the shared
  # body marker: SIGKILL leaves the first run's fake suite
  # orphaned, and its marker line lands whenever the OS
  # gets round to it.
  assert_contains \
    "RunTestsLock > stale lock > should actually run the suites after breaking the stale lock" \
    "$output" "PASS  configs/ai-docs/claude/tests/test-lock-body-probe.sh"
  assert_contains \
    "RunTestsLock > stale lock > should say the lock was stale rather than breaking it silently" \
    "$output" "stale lock"

  rm -rf "$sandbox"
}

it_should_refuse_to_report_success_when_it_cannot_take_a_lock_at_all() {
  local sandbox output
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 0 0

  # root ignores the permission bits, so the only way to make
  # the lock unusable there is not available — and reporting a
  # failure for an unrunnable case would be noise.
  if [ "$(id -u)" = "0" ]; then
    printf 'skip - RunTestsLock > unusable lock path > needs a non-root user to make TMPDIR unwritable\n'
    rm -rf "$sandbox"
    return 0
  fi

  chmod 000 "$sandbox/tmp"
  start_run "$sandbox" "$sandbox/run.out"
  wait_for_run "$run_pid" 150
  output="$(cat "$sandbox/run.out")"
  chmod 755 "$sandbox/tmp"

  assert_eq \
    "RunTestsLock > unusable lock path > should exit non-zero rather than report a green nobody ran" \
    "yes" \
    "$([ "$wait_status" -ne 0 ] && printf 'yes' || printf 'no')"
  assert_contains \
    "RunTestsLock > unusable lock path > should say outright that the suite did not run" \
    "$output" "did NOT run"
  assert_eq \
    "RunTestsLock > unusable lock path > should not execute a single suite when it gave up on the lock" \
    "no suite ran" \
    "$([ -f "$sandbox/body-runs.log" ] && printf 'a suite ran' || printf 'no suite ran')"

  rm -rf "$sandbox"
}

it_should_keep_a_second_run_out_of_the_suite_body_until_the_first_finishes
it_should_release_the_lock_after_a_passing_run
it_should_release_the_lock_after_a_run_a_failing_suite_made_exit_non_zero
it_should_release_the_lock_when_the_run_is_interrupted
it_should_break_a_lock_whose_owning_process_is_gone
it_should_refuse_to_report_success_when_it_cannot_take_a_lock_at_all

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
