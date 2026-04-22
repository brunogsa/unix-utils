#!/usr/bin/env bash
# Tests for show-file-in-nvim-via-tmux. Run from anywhere; cwd is restored.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

SCRIPT="./scripts/show-file-in-nvim-via-tmux.sh"
PASSED=0
FAILED=0

FIXTURE=$(mktemp)
echo "test fixture" > "$FIXTURE"
trap 'rm -f "$FIXTURE"' EXIT

# run "name" "command" expected_exit "regex pattern in combined output"
run() {
  local name="$1" cmd="$2" expected_exit="$3" pattern="$4"
  local output exit_code
  output=$(eval "$cmd" 2>&1) || exit_code=$?
  exit_code=${exit_code:-0}
  if [[ "$exit_code" -eq "$expected_exit" ]] && echo "$output" | grep -qE "$pattern"; then
    echo "PASS: $name"
    PASSED=$((PASSED + 1))
  else
    echo "FAIL: $name"
    echo "  expected exit=$expected_exit got=$exit_code"
    echo "  expected pattern: $pattern"
    echo "  output: $output"
    FAILED=$((FAILED + 1))
  fi
}

run "exits 0 with Usage on --help" \
    "$SCRIPT --help" \
    0 \
    "Usage:"

run "--help output includes at least 4 examples" \
    "$SCRIPT --help | grep -c 'show-file-in-nvim-via-tmux '" \
    0 \
    "^[4-9]|^[1-9][0-9]+"

run "exits non-zero with stderr on missing args" \
    "$SCRIPT" \
    1 \
    "Missing"

run "exits non-zero with stderr on missing file" \
    "$SCRIPT vertical" \
    1 \
    "Missing <file>"

run "exits non-zero with stderr on missing line" \
    "$SCRIPT vertical $FIXTURE" \
    1 \
    "Missing <line>"

run "exits non-zero on non-numeric line" \
    "$SCRIPT vertical $FIXTURE abc" \
    1 \
    "positive integer"

run "exits non-zero on invalid mode" \
    "$SCRIPT bogus $FIXTURE 5" \
    1 \
    "Invalid mode"

run "exits non-zero on invalid pane number" \
    "$SCRIPT pane:abc $FIXTURE 5" \
    1 \
    "Invalid pane number"

run "exits non-zero on nonexistent file" \
    "$SCRIPT vertical /nonexistent/path.md 5" \
    1 \
    "File not found"

run "exits non-zero and prints fallback nvim command on stdout when TMUX unset" \
    "env -u TMUX $SCRIPT vertical $FIXTURE 5" \
    2 \
    "nvim \+5"

echo ""
echo "Passed: $PASSED, Failed: $FAILED"
[[ "$FAILED" -eq 0 ]]
