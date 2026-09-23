#!/usr/bin/env bash

# test-run-tests-headroom-gate.sh - covers the pre-flight
# headroom gate in ./run-tests.sh: before any suite runs, the
# script asks check-machine-headroom.sh whether this machine
# has CPU/RAM/disk room, and refuses to start when it doesn't.

# Usage:
#   bash test-run-tests-headroom-gate.sh

# Replaces test-run-tests-lock.sh. The single-run mkdir
# lock it covered is gone: a profiled full run averages
# ~0.47 cores on a 12-core machine, so the starvation five
# sessions once caused came from their own separate load.

# Not from light test runs contending with each other. Two
# runs can now overlap; nothing here asserts they can't.

# No bats dependency by design - same precedent as the sibling
# suites under configs/ai-docs/claude/:
#
# - tests/test-run-tests-pytest-integration.sh
# - scripts/tests/test-statusline-tier.sh

# Every fixture builds a throwaway sandbox holding a COPY of the
# real run-tests.sh, a stub `pytest`, a stub headroom-gate
# script this fixture controls, and a single fast fake suite as
# the run's body.
#
# The real gate script is never invoked: these fixtures assert
# on run-tests.sh's reaction to GO/NO-GO/UNKNOWN/missing, not on
# whether this machine actually has headroom right now.

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
# than in the real test trees, and a stub pytest that exits 0
# in milliseconds.
#
# No gate script is placed here - each test adds its own via
# add_gate_stub, or leaves it absent to cover the missing-gate
# case.
fresh_sandbox() {
  local sandbox
  sandbox="$(mktemp -d "${TMPDIR:-/tmp}/run-tests-headroom.XXXXXX")"
  cp "$run_tests_src" "$sandbox/run-tests.sh"
  mkdir -p \
    "$sandbox/bin" \
    "$sandbox/configs/ai-docs/claude/scripts" \
    "$sandbox/configs/ai-docs/claude/tests" \
    "$sandbox/configs/ai-docs/claude/scripts/tests" \
    "$sandbox/configs/ai-docs/claude/hooks/tests" \
    "$sandbox/configs/ai-docs/claude/skills/fake-skill/scripts/tests"

  cat > "$sandbox/bin/pytest" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
  chmod +x "$sandbox/bin/pytest"

  printf '%s\n' "$sandbox"
}

# add_gate_stub - drops a stub check-machine-headroom.sh at the
# path run-tests.sh resolves relative to its own directory.
#
# It records every invocation to gate-calls.log, so a fixture
# can prove the gate was consulted at all, not just that its
# verdict was honored.
add_gate_stub() {
  local sandbox="$1" exit_code="$2" stdout_line="$3"
  cat > "$sandbox/configs/ai-docs/claude/scripts/check-machine-headroom.sh" <<EOF
#!/usr/bin/env bash
printf 'called\n' >> "$sandbox/gate-calls.log"
printf '%s\n' "$stdout_line"
exit $exit_code
EOF
  chmod +x "$sandbox/configs/ai-docs/claude/scripts/check-machine-headroom.sh"
}

# add_body_suite - the run's whole body: one fake suite that
# records its own run and exits $exit_code.
add_body_suite() {
  local sandbox="$1" exit_code="$2"
  cat > "$sandbox/configs/ai-docs/claude/tests/test-gate-body-probe.sh" <<EOF
#!/usr/bin/env bash
printf 'ran\n' >> "$sandbox/body-runs.log"
exit $exit_code
EOF
}

# run_sandboxed - runs the sandboxed run-tests.sh and echoes
# "<exit status>\x1e<combined output>" so a single fixture can
# capture both halves at once.
run_sandboxed() {
  local sandbox="$1"
  local out status
  out="$(cd "$sandbox" && PATH="$sandbox/bin:$PATH" bash ./run-tests.sh 2>&1)"
  status=$?
  printf '%s\x1e%s' "$status" "$out"
}

sandboxed_exit_status() {
  printf '%s' "${1%%$'\x1e'*}"
}

sandboxed_output() {
  printf '%s' "${1#*$'\x1e'}"
}

gate_call_count() {
  local sandbox="$1"
  [ -f "$sandbox/gate-calls.log" ] && wc -l < "$sandbox/gate-calls.log" | tr -d ' ' || printf '0'
}

body_ran() {
  local sandbox="$1"
  [ -f "$sandbox/body-runs.log" ] && printf 'ran' || printf 'did not run'
}

it_should_run_the_suites_when_the_gate_reports_go() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_gate_stub "$sandbox" 0 "HEADROOM=GO cores=8 load1=1.00 ratio=0.12 max_ratio=0.70 mem_avail_mb=4000 min_avail_mb=1536 disk_free_mb=100000 min_disk_mb=5120"
  add_body_suite "$sandbox" 0

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsHeadroomGate > GO > should exit zero when the suites all pass" \
    "0" "$status"
  assert_eq \
    "RunTestsHeadroomGate > GO > should consult the gate exactly once before running any suite" \
    "1" "$(gate_call_count "$sandbox")"
  assert_eq \
    "RunTestsHeadroomGate > GO > should run the suite body" \
    "ran" "$(body_ran "$sandbox")"
  assert_contains \
    "RunTestsHeadroomGate > GO > should report the passing suite" \
    "$output" "PASS  configs/ai-docs/claude/tests/test-gate-body-probe.sh"

  rm -rf "$sandbox"
}

it_should_refuse_to_run_when_the_gate_reports_no_go() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_gate_stub "$sandbox" 1 'HEADROOM=NO-GO cores=4 load1=5.10 ratio=1.28 max_ratio=0.70 mem_avail_mb=500 min_avail_mb=1536 disk_free_mb=900 min_disk_mb=5120 reason="load ratio 1.28 exceeds max 0.70"'
  add_body_suite "$sandbox" 0

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsHeadroomGate > NO-GO > should exit 2 so callers can tell not-run apart from red" \
    "2" "$status"
  assert_contains \
    "RunTestsHeadroomGate > NO-GO > should say outright that the suites did not run" \
    "$output" "did NOT run"
  assert_contains \
    "RunTestsHeadroomGate > NO-GO > should print the gate's own stdout line" \
    "$output" "HEADROOM=NO-GO"
  assert_eq \
    "RunTestsHeadroomGate > NO-GO > should not execute a single suite" \
    "did not run" "$(body_ran "$sandbox")"

  rm -rf "$sandbox"
}

it_should_refuse_to_run_when_the_gate_is_unknown() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_gate_stub "$sandbox" 2 'HEADROOM=UNKNOWN reason="neither /proc/loadavg nor sysctl found; cannot measure machine load"'
  add_body_suite "$sandbox" 0

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsHeadroomGate > UNKNOWN > should exit 2 rather than guess whether the machine has headroom" \
    "2" "$status"
  assert_contains \
    "RunTestsHeadroomGate > UNKNOWN > should say outright that the suites did not run" \
    "$output" "did NOT run"
  assert_eq \
    "RunTestsHeadroomGate > UNKNOWN > should not execute a single suite" \
    "did not run" "$(body_ran "$sandbox")"

  rm -rf "$sandbox"
}

it_should_refuse_to_run_when_the_gate_script_is_missing() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_body_suite "$sandbox" 0

  # No add_gate_stub call: the gate script never exists at
  # the path run-tests.sh resolves relative to its own dir.

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsHeadroomGate > missing gate script > should exit 2 rather than run unguarded" \
    "2" "$status"
  assert_contains \
    "RunTestsHeadroomGate > missing gate script > should say outright that the suites did not run" \
    "$output" "did NOT run"
  assert_eq \
    "RunTestsHeadroomGate > missing gate script > should not execute a single suite" \
    "did not run" "$(body_ran "$sandbox")"

  rm -rf "$sandbox"
}

it_should_run_the_suites_when_the_gate_reports_go
it_should_refuse_to_run_when_the_gate_reports_no_go
it_should_refuse_to_run_when_the_gate_is_unknown
it_should_refuse_to_run_when_the_gate_script_is_missing

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
