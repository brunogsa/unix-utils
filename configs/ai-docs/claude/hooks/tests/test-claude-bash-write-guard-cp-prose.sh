#!/usr/bin/env bash
# Plain-bash test file for claude-bash-write-guard.sh: a `cp`
# onto a markdown file versus a `cp` onto a code file.
#
# Usage:
#   bash test-claude-bash-write-guard-cp-prose.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# A Write of a markdown file that breaks the format rules is
# only reported, never blocked, so a `cp` onto a markdown file
# must not be stricter than the tool the guard points to.
#
# The harness mirrors test-claude-bash-write-guard.sh. The
# fixture repo lives under $HOME, because the guard allows
# every path under /tmp and /private/tmp.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-bash-write-guard.sh"

pass_count=0
fail_count=0

bash_bin="$(command -v bash)"

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

fixture_base=""
sandbox_dir=""
scratch_dir=""

setup_fixtures() {
  fixture_base=$(mktemp -d "$HOME/.claude-bash-write-guard-cp-prose-test.XXXXXX")
  sandbox_dir="$fixture_base/repo"
  mkdir -p "$sandbox_dir/src" "$sandbox_dir/docs"
  (
    cd "$sandbox_dir" || exit 1
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test"
    printf '# Readme\n' > README.md
    printf 'x = 1\n' > src/settings.py
    git add README.md src/settings.py
    git commit -q -m "init"
  )

  # Scratch under /tmp, which a Bash write never guards, holding
  # text that breaks each destination's format checker.
  scratch_dir=$(mktemp -d /tmp/claude-bash-write-guard-cp-prose-scratch.XXXXXX)
  printf '### 1. Review guide\n- The prototype spans\n80 lines.\n- Copy it in.\n' > "$scratch_dir/review-guide.md"
  printf '# This comment line is deliberately far longer than the comment-format width cap so the checker has something concrete to report.\nx = 1\n' \
    > "$scratch_dir/settings.py"
}

teardown_fixtures() {
  [ -n "$fixture_base" ] && rm -rf "$fixture_base"
  [ -n "$scratch_dir" ] && rm -rf "$scratch_dir"
}

# run_hook - runs the guard cwd'd into the sandbox repo on the
# given command, capturing HOOK_EXIT (0 allows, 2 blocks) and
# HOOK_STDERR.
run_hook() {
  local stdin_json
  stdin_json=$(jq -n --arg c "$1" '{tool_input: {command: $c}}')
  HOOK_STDERR=$(
    cd "$sandbox_dir" || exit 1
    printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null
  )
  HOOK_EXIT=$?
}

it_should_allow_cp_copying_a_scratch_file_that_breaks_the_markdown_format_rules_onto_a_new_repo_markdown_file() {
  run_hook "cp $scratch_dir/review-guide.md docs/review-guide.md"
  assert_eq "should allow cp copying a /tmp scratch file with hard-wrapped, gap-less bullets onto a new markdown file in the repo, as a Write of it would be" "0" "$HOOK_EXIT"
}

# why: the reported copy named its scratchpad source through a
# variable; onto markdown no source check is owed, so a source
# the guard cannot read is no reason to block.
it_should_allow_cp_copying_a_source_named_by_a_shell_variable_onto_a_new_repo_markdown_file() {
  run_hook "cp \$SCRATCHPAD/review-guide.md docs/review-guide.md"
  assert_eq "should allow cp copying a source named by a shell variable onto a new markdown file in the repo" "0" "$HOOK_EXIT"
}

it_should_block_a_copy_run_through_a_local_script_named_cp_onto_a_repo_markdown_file() {
  run_hook "./cp $scratch_dir/review-guide.md docs/review-guide.md"
  assert_eq "should block a copy onto a repo markdown file run through a local script named cp, which can write any text" "2" "$HOOK_EXIT"
}

# run_guard_copy_without_extension_list - runs a copy of the
# guard from a hooks dir that lacks the shared extension list.
#
# The copy keeps lib/parse-shell-command.py: without it the
# python import dies first, which proves nothing about the list.
run_guard_copy_without_extension_list() {
  local copy_dir="$fixture_base/hooks-without-extension-list" stdin_json
  mkdir -p "$copy_dir/lib"
  cp "$SCRIPT" "$copy_dir/"
  cp "$script_dir/lib/parse-shell-command.py" "$copy_dir/lib/"
  stdin_json=$(jq -n --arg c "$1" '{tool_input: {command: $c}}')
  (
    cd "$sandbox_dir" || exit 1
    printf '%s' "$stdin_json" | "$bash_bin" "$copy_dir/claude-bash-write-guard.sh" >/dev/null 2>&1
  )
  HOOK_EXIT=$?
}

# why: with the list unreadable the guard cannot tell markdown
# from code, so it fails closed on a cp onto markdown too.
it_should_block_cp_onto_a_repo_markdown_file_when_the_shared_extension_list_is_missing() {
  run_guard_copy_without_extension_list "cp $scratch_dir/review-guide.md docs/review-guide.md"
  assert_eq "should block cp onto a repo markdown file when the shared extension list cannot be read" "2" "$HOOK_EXIT"
}

it_should_block_cp_copying_a_scratch_file_that_breaks_the_comment_format_rules_over_a_tracked_python_file() {
  run_hook "cp $scratch_dir/settings.py src/settings.py"
  assert_eq "should block cp copying a /tmp scratch python file whose comment breaks the comment format rules over a tracked python file" "2" "$HOOK_EXIT"
}

it_should_block_cp_copying_a_scratch_python_file_that_breaks_the_comment_format_rules_into_a_target_directory_named_by_t() {
  run_hook "cp -t src $scratch_dir/settings.py"
  assert_eq "should block cp -t src copying a /tmp scratch python file whose comment breaks the comment format rules into the repo" "2" "$HOOK_EXIT"
}

setup_fixtures
trap teardown_fixtures EXIT

it_should_allow_cp_copying_a_scratch_file_that_breaks_the_markdown_format_rules_onto_a_new_repo_markdown_file
it_should_allow_cp_copying_a_source_named_by_a_shell_variable_onto_a_new_repo_markdown_file
it_should_block_a_copy_run_through_a_local_script_named_cp_onto_a_repo_markdown_file
it_should_block_cp_onto_a_repo_markdown_file_when_the_shared_extension_list_is_missing
it_should_block_cp_copying_a_scratch_file_that_breaks_the_comment_format_rules_over_a_tracked_python_file
it_should_block_cp_copying_a_scratch_python_file_that_breaks_the_comment_format_rules_into_a_target_directory_named_by_t

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
