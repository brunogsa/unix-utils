#!/usr/bin/env bash

# test-run-tests-node-integration.sh - covers folding
# node:test suites into ./run-tests.sh as additional
# suites, discovered by glob.
#
# The goal: `./run-tests.sh` alone stays the honest
# "is the repo green" answer once a tree also holds
# node:test suites, instead of leaving them to a second
# `node --test` invocation nobody is enforcing.

# Usage:
#   bash test-run-tests-node-integration.sh

# No bats dependency by design - same precedent as the
# sibling fold-in suite test-run-tests-pytest-integration.sh.

# Every fixture below builds its own throwaway sandbox
# directory holding a COPY of the real run-tests.sh plus
# a copy of the real pytest.ini, then populates only the
# fake suites each case needs.
#
# run-tests.sh anchors its globs on its own script
# location, so copying it into an isolated sandbox keeps
# these fixtures off the real, shared test trees.
#
# It also keeps them from recursing into the outer
# ./run-tests.sh that is running this very suite.
#
# Each sandbox also gets one passing python test: a bare
# `pytest` collecting nothing exits 5, which would fail
# the sandbox run for a reason that has nothing to do
# with the node leg under test.

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
  sandbox="$(mktemp -d "${TMPDIR:-/tmp}/run-tests-node-fold.XXXXXX")"
  cp "$run_tests_src" "$sandbox/run-tests.sh"
  cp "$pytest_ini_src" "$sandbox/pytest.ini"
  mkdir -p \
    "$sandbox/configs/ai-docs/claude/scripts" \
    "$sandbox/configs/ai-docs/claude/tests" \
    "$sandbox/configs/ai-docs/claude/scripts/tests" \
    "$sandbox/configs/ai-docs/claude/hooks/tests" \
    "$sandbox/configs/ai-docs/claude/skills/fake-skill/scripts/tests"

  # A GO stub at the path run-tests.sh resolves its gate to,
  # so this fold-in suite stays green whatever this machine's
  # real load is - including a busy outer run loading it.
  cat > "$sandbox/configs/ai-docs/claude/scripts/check-machine-headroom.sh" <<'STUB'
#!/usr/bin/env bash
printf 'HEADROOM=GO cores=8 load1=0.10 ratio=0.01 max_ratio=0.70 mem_avail_mb=4000 min_avail_mb=1536 disk_free_mb=100000 min_disk_mb=5120\n'
exit 0
STUB
  chmod +x "$sandbox/configs/ai-docs/claude/scripts/check-machine-headroom.sh"

  add_python_test "$sandbox"

  printf '%s\n' "$sandbox"
}

# add_python_test - drops a passing pytest test at the sandbox
# root, so the folded-in pytest leg has something to collect.
add_python_test() {
  local sandbox="$1"
  cat > "$sandbox/test_fake_fixture.py" <<'EOF'
def test_sandbox_fixture_passes():
    assert True
EOF
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

# add_node_suite - drops a node:test file at $2 (relative to
# the sandbox) that passes when $3 is "pass", fails with a
# recognizable assertion message when $3 is "fail".
add_node_suite() {
  local sandbox="$1" relative_path="$2" outcome="$3"
  if [ "$outcome" = "pass" ]; then
    cat > "$sandbox/$relative_path" <<'EOF'
const test = require('node:test');
const assert = require('node:assert');

test('sandbox node fixture passes', () => {
  assert.strictEqual(1 + 1, 2);
});
EOF
  else
    cat > "$sandbox/$relative_path" <<'EOF'
const test = require('node:test');
const assert = require('node:assert');

test('sandbox node fixture fails', () => {
  assert.fail('sandbox node regression fixture');
});
EOF
  fi
}

# stripped_path_bin - a bin/ directory holding only the
# externals run-tests.sh itself needs, so pointing PATH at
# it hides `node` without uninstalling anything.
#
# A plain PATH=/usr/bin:/bin would not work cross-platform:
# node lives in /usr/local/bin on this machine but in
# /usr/bin under a Linux apt install, where that override
# would still find it.
stripped_path_bin() {
  local sandbox="$1" tool resolved
  mkdir -p "$sandbox/bin"
  for tool in env bash dirname mktemp rm cat; do
    resolved="$(command -v "$tool")"
    [ -n "$resolved" ] && ln -sf "$resolved" "$sandbox/bin/$tool"
  done
  printf '%s\n' "$sandbox/bin"
}

# run_sandboxed - runs the sandboxed run-tests.sh with an
# optional PATH override (used to simulate node being
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

it_should_run_a_node_suite_in_every_tree_a_bash_suite_can_live_in() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/tests/fake-top.test.js" "pass"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/scripts/tests/fake-scripts.test.js" "pass"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/hooks/tests/fake-hooks.test.js" "pass"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/skills/fake-skill/scripts/tests/fake-skill.test.js" "pass"

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsNodeFold > discovery > should exit zero when every discovered node suite passes" \
    "0" "$status"
  assert_contains \
    "RunTestsNodeFold > discovery > should run a node suite sitting in the top-level tests tree" \
    "$output" "PASS  configs/ai-docs/claude/tests/fake-top.test.js"
  assert_contains \
    "RunTestsNodeFold > discovery > should run a node suite sitting in the scripts tests tree" \
    "$output" "PASS  configs/ai-docs/claude/scripts/tests/fake-scripts.test.js"
  assert_contains \
    "RunTestsNodeFold > discovery > should run a node suite sitting in the hooks tests tree" \
    "$output" "PASS  configs/ai-docs/claude/hooks/tests/fake-hooks.test.js"
  assert_contains \
    "RunTestsNodeFold > discovery > should run a node suite sitting in a skill's scripts tests tree" \
    "$output" "PASS  configs/ai-docs/claude/skills/fake-skill/scripts/tests/fake-skill.test.js"
  assert_contains \
    "RunTestsNodeFold > discovery > should count all four node suites alongside the pytest step" \
    "$output" "5 passed, 0 failed"

  rm -rf "$sandbox"
}

it_should_fail_the_overall_run_when_a_node_suite_reports_a_failure() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/skills/fake-skill/scripts/tests/fake-skill.test.js" "fail"

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsNodeFold > failing suite > should exit non-zero when a folded-in node suite has a failing test" \
    "1" "$status"
  assert_contains \
    "RunTestsNodeFold > failing suite > should name the failing node suite by a path a human can re-run by hand" \
    "$output" "FAIL  configs/ai-docs/claude/skills/fake-skill/scripts/tests/fake-skill.test.js"
  assert_contains \
    "RunTestsNodeFold > failing suite > should replay the failing node assertion, not just a bare FAIL line" \
    "$output" "sandbox node regression fixture"

  rm -rf "$sandbox"
}

it_should_fail_loudly_when_node_is_not_installed() {
  local sandbox result status output stripped_bin
  sandbox="$(fresh_sandbox)"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/hooks/tests/fake-hooks.test.js" "pass"
  stripped_bin="$(stripped_path_bin "$sandbox")"

  result="$(run_sandboxed "$sandbox" "$stripped_bin")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsNodeFold > missing node > should exit non-zero rather than silently reading as a pass" \
    "1" "$status"
  assert_contains \
    "RunTestsNodeFold > missing node > should name node as not installed rather than reporting a bare FAIL" \
    "$output" "node: command not found"

  rm -rf "$sandbox"
}

it_should_stay_green_when_no_node_suite_exists_at_all() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsNodeFold > no node suites > should exit zero because an unmatched glob is an empty leg, not an error" \
    "0" "$status"
  assert_contains \
    "RunTestsNodeFold > no node suites > should count only the pytest step when no node suite is discovered" \
    "$output" "1 passed, 0 failed"

  rm -rf "$sandbox"
}

it_should_still_report_the_node_suite_after_an_earlier_bash_suite_fails() {
  local sandbox result status output
  sandbox="$(fresh_sandbox)"
  add_bash_suite "$sandbox" "1"
  add_node_suite "$sandbox" \
    "configs/ai-docs/claude/hooks/tests/fake-hooks.test.js" "pass"

  result="$(run_sandboxed "$sandbox")"
  status="$(sandboxed_exit_status "$result")"
  output="$(sandboxed_output "$result")"

  assert_eq \
    "RunTestsNodeFold > bash failure keeps going > should exit non-zero because the bash suite failed" \
    "1" "$status"
  assert_contains \
    "RunTestsNodeFold > bash failure keeps going > should still run and report the node suite rather than aborting" \
    "$output" "PASS  configs/ai-docs/claude/hooks/tests/fake-hooks.test.js"
  assert_contains \
    "RunTestsNodeFold > bash failure keeps going > should count the failed bash suite, the node suite and pytest" \
    "$output" "2 passed, 1 failed"

  rm -rf "$sandbox"
}

it_should_run_a_node_suite_in_every_tree_a_bash_suite_can_live_in
it_should_fail_the_overall_run_when_a_node_suite_reports_a_failure
it_should_fail_loudly_when_node_is_not_installed
it_should_stay_green_when_no_node_suite_exists_at_all
it_should_still_report_the_node_suite_after_an_earlier_bash_suite_fails

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
