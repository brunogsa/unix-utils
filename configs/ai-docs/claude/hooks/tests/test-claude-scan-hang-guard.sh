#!/usr/bin/env bash
# Plain-bash test file for claude-scan-hang-guard.sh.
#
# Usage:
#   bash test-claude-scan-hang-guard.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design — matches
# the sibling hook suites in this directory.
#
# The five blocked commands below are verbatim from the
# incident that motivated the guard: two Bash calls that
# stranded two shell trees for ~35 minutes each until
# they were killed by hand.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-scan-hang-guard.sh"

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

# assert_contains - asserts the denial message carries a
# given substring, so the caller is told what to do
# instead of merely being refused.
assert_contains() {
  local description="$1" needle="$2" haystack="$3"
  case "$haystack" in
    *"$needle"*)
      pass_count=$((pass_count + 1))
      printf 'ok - %s\n' "$description"
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - %s\n  expected to contain: %s\n  actual:   %s\n' "$description" "$needle" "$haystack"
      ;;
  esac
}

bash_bin="$(command -v bash)"

# run_hook - invokes the hook with the given command
# string, wrapped into the PreToolUse JSON shape.
# Captures exit code into HOOK_EXIT (0 = allowed, 2 =
# blocked) and stderr into HOOK_STDERR.
run_hook() {
  local command="$1" stdin_json
  stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  HOOK_STDERR=$(printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null)
  HOOK_EXIT=$?
}

# run_hook_raw - feeds an arbitrary stdin payload, for
# the malformed-payload cases the JSON wrapper above
# cannot express.
run_hook_raw() {
  local payload="$1"
  printf '%s' "$payload" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  HOOK_EXIT=$?
}

it_should_block_strings_piped_into_grep_for_assignment_names() {
  local cmd
  cmd=$(cat <<'EOF'
strings -a "$b" 2>/dev/null | grep -o 'UxT *= *[0-9.]*\|jxT *= *[0-9.]*\|HJm *= *[0-9.]*\|HOl *= *[0-9.]*\|NJm *= *[0-9.]*' | sort -u | head
EOF
)
  run_hook "$cmd"
  assert_eq "should block strings piped straight into grep while scanning a 100MB binary" "2" "$HOOK_EXIT"
}

it_should_block_strings_piped_into_grep_for_a_var_declaration() {
  local cmd
  cmd=$(cat <<'EOF'
strings -a "$b" 2>/dev/null | grep -o 'var [A-Za-z$]*JmT\?[^;]\{0,40\}UxT[^;]\{0,120\}' | head -2
EOF
)
  run_hook "$cmd"
  assert_eq "should block strings piped straight into grep with a three-quantifier pattern" "2" "$HOOK_EXIT"
}

it_should_block_strings_piped_into_grep_with_a_fixed_width_lookbehind() {
  local cmd
  cmd=$(cat <<'EOF'
strings -a "$b" 2>/dev/null | grep -o '.\{160\}UxT=[^;]\{0,60\}' | head -2
EOF
)
  run_hook "$cmd"
  assert_eq "should block strings piped straight into grep with a fixed-width leading context" "2" "$HOOK_EXIT"
}

it_should_block_a_grep_over_a_saved_file_with_three_quantifiers() {
  local cmd
  cmd=$(cat <<'EOF'
grep -o '.\{0,30\}UxT=[0-9]*,\?[^;]\{0,40\}' "$f" | head -2
EOF
)
  run_hook "$cmd"
  assert_eq "should block a grep whose pattern multiplies three bounded quantifiers" "2" "$HOOK_EXIT"
}

it_should_block_a_second_grep_over_a_saved_file_with_three_quantifiers() {
  local cmd
  cmd=$(cat <<'EOF'
grep -o '.\{0,40\}jxT=[0-9]*[^;]\{0,30\}' "$f" | head -2
EOF
)
  run_hook "$cmd"
  assert_eq "should block a second grep whose pattern multiplies three bounded quantifiers" "2" "$HOOK_EXIT"
}

it_should_allow_a_grep_with_a_single_bounded_quantifier() {
  local cmd
  cmd=$(cat <<'EOF'
grep -o '.\{0,30\}foo' file.txt
EOF
)
  run_hook "$cmd"
  assert_eq "should allow a grep carrying a single bounded quantifier" "0" "$HOOK_EXIT"
}

it_should_allow_strings_redirected_to_a_file() {
  run_hook 'strings -a bin > /tmp/dump.txt'
  assert_eq "should allow strings redirected into a file instead of piped into a filter" "0" "$HOOK_EXIT"
}

it_should_allow_a_grep_with_no_quantifiers() {
  run_hook "grep -c 'pattern' file.txt"
  assert_eq "should allow a grep whose pattern carries no quantifiers" "0" "$HOOK_EXIT"
}

it_should_allow_an_ordinary_pipeline_into_grep() {
  run_hook 'git log -n 10 | grep foo'
  assert_eq "should allow an ordinary command piped into grep, since only named producers are unbounded" "0" "$HOOK_EXIT"
}

it_should_allow_a_payload_whose_command_field_is_absent() {
  run_hook_raw '{"tool_input":{}}'
  assert_eq "should allow a payload whose command field is absent" "0" "$HOOK_EXIT"
}

it_should_allow_a_payload_that_is_not_json_at_all() {
  run_hook_raw 'not json at all'
  assert_eq "should allow a payload that is not JSON at all" "0" "$HOOK_EXIT"
}

it_should_allow_a_heredoc_that_only_quotes_a_hung_command() {
  local cmd
  cmd=$(cat <<'OUTER'
git commit -F - <<'EOF'
The incident command was: strings -a bin | grep -o 'x'
EOF
OUTER
)
  run_hook "$cmd"
  assert_eq "should allow a heredoc whose payload merely quotes a hung command" "0" "$HOOK_EXIT"
}

it_should_name_the_redirect_alternative_when_blocking_a_piped_producer() {
  run_hook "strings -a bin | grep -c foo"
  assert_contains "should name the redirect-then-filter alternative when blocking a piped producer" "redirect" "$HOOK_STDERR"
}

it_should_name_the_python_alternative_when_blocking_a_multiplying_pattern() {
  local cmd
  cmd=$(cat <<'EOF'
grep -o '.\{0,40\}jxT=[0-9]*[^;]\{0,30\}' saved.txt
EOF
)
  run_hook "$cmd"
  assert_contains "should name the re.finditer alternative when blocking a multiplying pattern" "re.finditer" "$HOOK_STDERR"
}

it_should_block_strings_piped_into_grep_for_assignment_names
it_should_block_strings_piped_into_grep_for_a_var_declaration
it_should_block_strings_piped_into_grep_with_a_fixed_width_lookbehind
it_should_block_a_grep_over_a_saved_file_with_three_quantifiers
it_should_block_a_second_grep_over_a_saved_file_with_three_quantifiers
it_should_allow_a_grep_with_a_single_bounded_quantifier
it_should_allow_strings_redirected_to_a_file
it_should_allow_a_grep_with_no_quantifiers
it_should_allow_an_ordinary_pipeline_into_grep
it_should_allow_a_payload_whose_command_field_is_absent
it_should_allow_a_payload_that_is_not_json_at_all
it_should_allow_a_heredoc_that_only_quotes_a_hung_command
it_should_name_the_redirect_alternative_when_blocking_a_piped_producer
it_should_name_the_python_alternative_when_blocking_a_multiplying_pattern

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
