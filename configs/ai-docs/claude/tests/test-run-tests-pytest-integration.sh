#!/usr/bin/env bash

# test-run-tests-pytest-integration.sh - covers folding
# `pytest` into ./run-tests.sh as an additional suite.
#
# The goal: `./run-tests.sh` alone becomes the honest
# "is the repo green" answer, instead of requiring a
# second `pytest` invocation the script's own exit code
# doesn't reflect.

# Usage:
#   bash test-run-tests-pytest-integration.sh

# No bats dependency by design — same precedent as these sibling
# suites under configs/ai-docs/claude/:
#
# - scripts/tests/test-statusline-tier.sh
# - scripts/tests/test-resolve-base-ref.sh

# Every fixture below builds its own throwaway sandbox
# directory holding a COPY of the real run-tests.sh plus
# a copy of the real pytest.ini, then populates only the
# fake suites each case needs.
#
# run-tests.sh anchors its four globs on its own script
# location, so copying it into an isolated sandbox is
# what keeps these fixtures from ever touching the real,
# shared test trees or the real repo's own suites.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"
run_tests_src="$repo_root/run-tests.sh"
pytest_ini_src="$repo_root/pytest.ini"

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

# fresh_sandbox - a scratch repo-root standing in for the
# real one.
#
# A copy of run-tests.sh keeps its self-anchored globs
# resolving inside the sandbox, never the real repo.
#
# A copy of pytest.ini keeps pytest's collection rules
# matching production, alongside the four empty suite
# trees run-tests.sh globs over.
fresh_sandbox() {
  local sandbox
  sandbox="$(mktemp -d "${TMPDIR:-/tmp}/run-tests-pytest-fold.XXXXXX")"
  cp "$run_tests_src" "$sandbox/run-tests.sh"
  cp "$pytest_ini_src" "$sandbox/pytest.ini"
  mkdir -p \
    "$sandbox/configs/ai-docs/claude/tests" \
    "$sandbox/configs/ai-docs/claude/scripts/tests" \
    "$sandbox/configs/ai-docs/claude/hooks/tests" \
    "$sandbox/configs/ai-docs/claude/skills/fake-skill/scripts/tests"
  printf '%s\n' "$sandbox"
}

# add_bash_suite - drops a fake suite under the sandbox's
# `tests/` tree that exits with $2 (0 = pass, non-zero = fail).
add_bash_suite() {
  local sandbox="$1" exit_code="$2"
  cat > "$sandbox/configs/ai-docs/claude/tests/test-fake-bash-suite.sh" <<EOF
#!/usr/bin/env bash
exit $exit_code
EOF
}

# add_python_test - drops a fake pytest test at the sandbox root
# that passes when $2 is "pass", fails when $2 is "fail".
add_python_test() {
  local sandbox="$1" outcome="$2"
  if [ "$outcome" = "pass" ]; then
    cat > "$sandbox/test_fake_fixture.py" <<'EOF'
def test_sandbox_fixture_passes():
    assert True
EOF
  else
    cat > "$sandbox/test_fake_fixture.py" <<'EOF'
def test_sandbox_fixture_fails():
    assert False, "sandbox regression fixture"
EOF
  fi
}

# run_sandboxed - runs the sandboxed run-tests.sh with an
# optional PATH override (used to simulate pytest being
# absent), and echoes "<exit status>\x1e<combined output>"
# so a single fixture can capture both halves at once.
#
# \x1e (record separator) is used instead of a newline or
# pipe because the captured output legitimately contains
# both.
run_sandboxed() {
  local sandbox="$1" path_override="${2:-}"
  local out status
  if [ -n "$path_override" ]; then
    out="$(cd "$sandbox" && PATH="$path_override" bash ./run-tests.sh 2>&1)"
  else
    out="$(cd "$sandbox" && bash ./run-tests.sh 2>&1)"
  fi
  status=$?
  printf '%s\x1e%s' "$status" "$out"
}

sandboxed_exit_status() {
  # `cut` splits per line, so it would only honor the separator
  # on the multi-line output's first line and pass every later
  # line through whole. Bash parameter expansion isn't line-
  # based, so it splits on the first \x1e wherever it falls.
  printf '%s' "${1%%$'\x1e'*}"
}

sandboxed_output() {
  printf '%s' "${1#*$'\x1e'}"
}

it_should_fail_the_overall_run_when_the_pytest_step_reports_a_failure() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_python_test "$sandbox" "fail"

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsPytestFold > failing suite > should exit non-zero when the folded-in pytest step has a failing test" \
    "1" "$status"
  assert_contains \
    "RunTestsPytestFold > failing suite > should list the pytest step as FAIL in the PASS/FAIL summary" \
    "$output" "FAIL  pytest"
  assert_contains \
    "RunTestsPytestFold > failing suite > should replay the failing python assertion, not just a bare FAIL line" \
    "$output" "sandbox regression fixture"

  rm -rf "$sandbox"
}

it_should_fail_loudly_when_pytest_is_not_installed() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_python_test "$sandbox" "pass"

  # A PATH holding only the OS base dirs has no pytest on this
  # machine (the real one lives under ~/.local/bin), which is
  # what simulates "pytest not installed" without needing to
  # actually uninstall it.
  result="$(run_sandboxed "$sandbox" "/usr/bin:/bin")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsPytestFold > missing pytest > should exit non-zero rather than silently reading as a pass" \
    "1" "$status"
  assert_contains \
    "RunTestsPytestFold > missing pytest > should name pytest as not installed rather than reporting a bare FAIL" \
    "$output" "pytest: command not found"

  rm -rf "$sandbox"
}

it_should_still_report_the_pytest_step_after_an_earlier_bash_suite_fails() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_bash_suite "$sandbox" "1"
  add_python_test "$sandbox" "pass"

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsPytestFold > bash failure keeps going > should exit non-zero because the bash suite failed" \
    "1" "$status"
  assert_contains \
    "RunTestsPytestFold > bash failure keeps going > should still report the failing bash suite" \
    "$output" "FAIL  configs/ai-docs/claude/tests/test-fake-bash-suite.sh"
  assert_contains \
    "RunTestsPytestFold > bash failure keeps going > should still run and report the pytest step rather than aborting" \
    "$output" "PASS  pytest"
  assert_contains \
    "RunTestsPytestFold > bash failure keeps going > should count both the failed bash suite and the passing pytest step" \
    "$output" "1 passed, 1 failed"

  rm -rf "$sandbox"
}

it_should_fail_the_overall_run_when_the_pytest_step_reports_a_failure
it_should_fail_loudly_when_pytest_is_not_installed
it_should_still_report_the_pytest_step_after_an_earlier_bash_suite_fails

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
