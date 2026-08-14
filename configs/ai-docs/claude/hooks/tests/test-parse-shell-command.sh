#!/usr/bin/env bash
# Plain-bash test file for lib/parse-shell-command.sh.
#
# Usage:
#   bash test-parse-shell-command.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design — matches
# the sibling hook suites in this directory.
#
# The parsing logic itself lives in a Python module
# (lib/parse-shell-command.py), since both guards run
# it via `python3 - <<'PYEOF'`, not as bash functions.
#
# See that file's header comment for the loader
# mechanism each guard uses.
#
# This suite exercises the module the same way: loaded
# via importlib.util from a fixed path, never by
# duplicating its logic.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_PATH="$script_dir/lib/parse-shell-command.py"

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs
# actual, prints ok/not-ok.
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

# run_py - loads the shared module the same way the
# guards do (importlib.util.spec_from_file_location, not
# a bare `import`, since the module's filename is
# hyphenated).
#
# Prints the value of a Python expression given on
# stdin, so callers just supply one expression.
run_py() {
  local expr="$1"
  LIB_PATH="$LIB_PATH" EXPR="$expr" python3 - <<'PYEOF'
import importlib.util
import os

spec = importlib.util.spec_from_file_location('parse_shell_command', os.environ['LIB_PATH'])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
strip_heredoc_bodies = module.strip_heredoc_bodies
split_into_pipelines = module.split_into_pipelines

# eval() is safe here: EXPR is never external input, only a fixed
# literal string this same test file passes to itself.
print(eval(os.environ['EXPR']))
PYEOF
}

it_should_strip_a_single_heredoc_body_between_opener_and_delimiter() {
  local actual
  actual=$(run_py "repr(strip_heredoc_bodies(\"echo hi\n<<'EOF'\nsecret rm -rf /\nEOF\necho bye\"))")
  assert_eq "should strip a single heredoc body, keeping its opener and delimiter lines" \
    "\"echo hi\n<<'EOF'\nEOF\necho bye\"" "$actual"
}

it_should_strip_bodies_of_multiple_heredocs_in_the_same_command() {
  local actual
  actual=$(run_py "repr(strip_heredoc_bodies(\"cat <<'A'\nbody one\nA\necho mid\ncat <<'B'\nbody two\nB\"))")
  assert_eq "should strip the body of every heredoc when a command carries more than one" \
    "\"cat <<'A'\nA\necho mid\ncat <<'B'\nB\"" "$actual"
}

it_should_not_split_a_double_quoted_argument_that_contains_a_pipe_and_a_semicolon() {
  local actual
  actual=$(run_py 'split_into_pipelines("grep -rn \"rm -rf; keep|going\" .")')
  assert_eq "should keep a double-quoted argument containing both ; and | as one unsplit stage" \
    "[['grep -rn \"rm -rf; keep|going\" .']]" "$actual"
}

it_should_leave_empty_input_unstripped_and_unsplit() {
  local strip_actual split_actual
  strip_actual=$(run_py "repr(strip_heredoc_bodies(''))")
  split_actual=$(run_py "split_into_pipelines('')")
  assert_eq "should return an empty string for empty input to strip_heredoc_bodies" "''" "$strip_actual"
  assert_eq "should return one empty stage for empty input to split_into_pipelines" "[['']]" "$split_actual"
}

it_should_drop_a_heredoc_body_up_to_end_of_input_when_its_delimiter_never_appears() {
  local actual
  actual=$(run_py "repr(strip_heredoc_bodies(\"echo hi\ncat <<'EOF'\nnever closes\nstill going\"))")
  assert_eq "should keep the unterminated heredoc's opener line but drop every line after it when the delimiter never appears" \
    "\"echo hi\ncat <<'EOF'\"" "$actual"
}

it_should_strip_a_single_heredoc_body_between_opener_and_delimiter
it_should_strip_bodies_of_multiple_heredocs_in_the_same_command
it_should_not_split_a_double_quoted_argument_that_contains_a_pipe_and_a_semicolon
it_should_leave_empty_input_unstripped_and_unsplit
it_should_drop_a_heredoc_body_up_to_end_of_input_when_its_delimiter_never_appears

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
