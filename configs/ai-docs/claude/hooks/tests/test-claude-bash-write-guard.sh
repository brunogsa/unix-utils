#!/usr/bin/env bash
# Plain-bash test file for claude-bash-write-guard.sh.
#
# Usage:
#   bash test-claude-bash-write-guard.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design - the sibling
# hook tests set that precedent.
#
# The fixture repo lives under $HOME, not under mktemp's
# default base, because the guard deliberately allows every
# path under /tmp and /private/tmp.
#
# Linux mktemp -d lands in /tmp, so a fixture there could
# never reach a block decision at all, and every block
# assertion would pass vacuously on Linux while really
# testing something on macOS.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-bash-write-guard.sh"

pass_count=0
fail_count=0

bash_bin="$(command -v bash)"

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

fixture_base=""
sandbox_dir=""
outside_dir=""

setup_fixtures() {
  fixture_base=$(mktemp -d "$HOME/.claude-bash-write-guard-test.XXXXXX")
  sandbox_dir="$fixture_base/repo"
  outside_dir="$fixture_base/plain"
  mkdir -p "$sandbox_dir/src" "$sandbox_dir/docs" "$sandbox_dir/build" "$outside_dir"
  (
    cd "$sandbox_dir" || exit 1
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test"
    printf 'export const x = 1;\n' > src/index.ts
    printf 'build/\n' > .gitignore
    printf '# Readme\n' > README.md
    git add src/index.ts .gitignore README.md
    git commit -q -m "init"
  )
}

teardown_fixtures() {
  [ -n "$fixture_base" ] && rm -rf "$fixture_base"
}

# run_hook - invokes the guard cwd'd into the sandbox repo
# with the given command string wrapped into the PreToolUse
# JSON shape.
#
# Captures the exit code into HOOK_EXIT (0 = allowed,
# 2 = blocked).
run_hook() {
  run_hook_in "$sandbox_dir" "$1"
}

# run_hook_in - same as run_hook, for a caller that needs a
# cwd other than the sandbox repo.
run_hook_in() {
  local dir="$1" command="$2" stdin_json
  stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  (
    cd "$dir" || exit 1
    printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  )
  HOOK_EXIT=$?
}

it_should_block_a_heredoc_authoring_a_markdown_file_in_the_repo() {
  run_hook "$(printf 'cat > notes.md <<%s\nsome prose\nEOF\n' "'EOF'")"
  assert_eq "should block a heredoc authoring a markdown file inside the repo" "2" "$HOOK_EXIT"
}

it_should_block_a_redirect_creating_a_typescript_file_in_the_repo() {
  run_hook "printf 'export const y = 2;' > src/new.ts"
  assert_eq "should block a redirect creating a typescript file inside the repo" "2" "$HOOK_EXIT"
}

it_should_block_an_append_redirect_onto_a_tracked_markdown_file() {
  run_hook "echo 'one more line' >> README.md"
  assert_eq "should block an append redirect onto a tracked markdown file" "2" "$HOOK_EXIT"
}

it_should_block_a_tee_writing_a_markdown_file_in_the_repo() {
  run_hook "echo hello | tee docs/out.md"
  assert_eq "should block a tee writing a markdown file inside the repo" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_sed_on_a_tracked_source_file() {
  run_hook "sed -i '' 's/const/let/' src/index.ts"
  assert_eq "should block an in-place sed on a tracked source file" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_sed_using_the_attached_backup_suffix_form() {
  run_hook "sed -i.bak 's/const/let/' src/index.ts"
  assert_eq "should block an in-place sed written as -i.bak" "2" "$HOOK_EXIT"
}

it_should_allow_reading_a_repo_file() {
  run_hook "cat src/index.ts"
  assert_eq "should allow a command that only reads a repo file" "0" "$HOOK_EXIT"
}

it_should_allow_a_redirect_into_tmp() {
  run_hook "printf 'scratch' > /tmp/claude-bash-write-guard-scratch.md"
  assert_eq "should allow a redirect into /tmp, where scratch belongs" "0" "$HOOK_EXIT"
}

it_should_allow_a_redirect_onto_an_extension_the_prose_checkers_ignore() {
  run_hook "printf '{}' > data.json"
  assert_eq "should allow a redirect onto an extension the prose checkers ignore" "0" "$HOOK_EXIT"
}

it_should_allow_a_redirect_onto_a_gitignored_path() {
  run_hook "printf 'compiled' > build/bundle.js"
  assert_eq "should allow a redirect onto a git-ignored path" "0" "$HOOK_EXIT"
}

it_should_allow_git_checkout_restoring_a_tracked_source_file() {
  run_hook "git checkout -- src/index.ts"
  assert_eq "should allow git checkout restoring a tracked source file" "0" "$HOOK_EXIT"
}

it_should_allow_git_stash_even_though_it_rewrites_the_work_tree() {
  run_hook "git stash"
  assert_eq "should allow git stash even though it rewrites the work tree" "0" "$HOOK_EXIT"
}

it_should_allow_a_test_run_whose_output_is_saved_outside_the_repo() {
  run_hook "./run-tests.sh > /tmp/claude-bash-write-guard-out.txt 2>&1"
  assert_eq "should allow a test run whose output is saved outside the repo" "0" "$HOOK_EXIT"
}

it_should_allow_a_redirect_whose_target_is_an_unresolved_variable() {
  run_hook 'printf "notes" > "$dir/notes.md"'
  assert_eq "should allow a redirect whose target is an unresolved variable" "0" "$HOOK_EXIT"
}

it_should_allow_a_redirect_into_dev_null() {
  run_hook "ls src > /dev/null 2>&1"
  assert_eq "should allow a redirect into /dev/null" "0" "$HOOK_EXIT"
}

it_should_allow_a_write_outside_any_git_work_tree() {
  run_hook_in "$outside_dir" "printf 'loose' > loose.md"
  assert_eq "should allow a write to a path outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_allow_a_search_whose_pattern_merely_contains_a_redirect_arrow() {
  run_hook 'grep -rn "write > notes.md" src'
  assert_eq "should allow a search whose quoted pattern merely contains a redirect arrow" "0" "$HOOK_EXIT"
}

it_should_allow_a_write_after_a_cd_whose_destination_cannot_be_resolved() {
  # Once a cd target is unknown, every later relative path in
  # the command is unknown too - resolving it against the old
  # cwd invents a repo path the command never writes.
  run_hook 'cd "$scratch"; printf wall > wall.md'
  assert_eq "should allow a relative write after a cd into an unresolved directory" "0" "$HOOK_EXIT"
}

it_should_allow_a_read_only_sed_with_no_in_place_flag() {
  run_hook "sed -n '1,5p' src/index.ts"
  assert_eq "should allow a read-only sed with no in-place flag" "0" "$HOOK_EXIT"
}

# run_hook_with_home - same as run_hook, with HOME pointed at
# the given directory so a leading `~` has a known expansion.
run_hook_with_home() {
  local home_dir="$1" command="$2" stdin_json
  stdin_json=$(jq -n --arg c "$command" '{tool_input: {command: $c}}')
  (
    cd "$sandbox_dir" || exit 1
    printf '%s' "$stdin_json" | HOME="$home_dir" "$bash_bin" "$SCRIPT" >/dev/null 2>&1
  )
  HOOK_EXIT=$?
}

it_should_allow_a_redirect_to_a_tilde_path_whose_home_is_outside_any_git_work_tree() {
  run_hook_with_home "$outside_dir" "printf 'probe' > ~/probe.md"
  assert_eq "should allow a redirect to ~/probe.md when the home directory is outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_allow_an_append_redirect_to_a_tilde_path_whose_home_is_outside_any_git_work_tree() {
  run_hook_with_home "$outside_dir" "printf 'probe' >> ~/probe.md"
  assert_eq "should allow an append redirect to ~/probe.md when the home directory is outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_allow_a_tee_to_a_tilde_path_whose_home_is_outside_any_git_work_tree() {
  run_hook_with_home "$outside_dir" "echo probe | tee ~/probe.md"
  assert_eq "should allow a tee to ~/probe.md when the home directory is outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_allow_an_in_place_sed_on_a_tilde_path_whose_home_is_outside_any_git_work_tree() {
  printf 'const a = 1;\n' > "$outside_dir/existing.ts"
  run_hook_with_home "$outside_dir" "sed -i.bak 's/const/let/' ~/existing.ts"
  assert_eq "should allow an in-place sed on ~/existing.ts when the home directory is outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_block_an_in_place_sed_on_a_tilde_path_whose_home_is_inside_a_git_work_tree() {
  run_hook_with_home "$sandbox_dir" "sed -i.bak 's/const/let/' ~/src/index.ts"
  assert_eq "should block an in-place sed on ~/src/index.ts when the home directory is inside a git work tree" "2" "$HOOK_EXIT"
}

it_should_block_a_redirect_to_a_tilde_path_whose_home_is_inside_a_git_work_tree() {
  run_hook_with_home "$sandbox_dir" "printf 'probe' > ~/probe.md"
  assert_eq "should block a redirect to ~/probe.md when the home directory is inside a git work tree" "2" "$HOOK_EXIT"
}

it_should_block_a_redirect_to_another_users_home_path_because_it_cannot_be_expanded() {
  # Conservative direction: ~someone resolves from the
  # password database, so the guard keeps treating it as a
  # cwd-relative path.
  run_hook_with_home "$outside_dir" "printf 'probe' > ~someone/probe.md"
  assert_eq "should block a redirect to ~someone/probe.md because another user's home is not expanded" "2" "$HOOK_EXIT"
}

setup_fixtures
trap teardown_fixtures EXIT

it_should_block_a_heredoc_authoring_a_markdown_file_in_the_repo
it_should_block_a_redirect_creating_a_typescript_file_in_the_repo
it_should_block_an_append_redirect_onto_a_tracked_markdown_file
it_should_block_a_tee_writing_a_markdown_file_in_the_repo
it_should_block_an_in_place_sed_on_a_tracked_source_file
it_should_block_an_in_place_sed_using_the_attached_backup_suffix_form
it_should_allow_reading_a_repo_file
it_should_allow_a_redirect_into_tmp
it_should_allow_a_redirect_onto_an_extension_the_prose_checkers_ignore
it_should_allow_a_redirect_onto_a_gitignored_path
it_should_allow_git_checkout_restoring_a_tracked_source_file
it_should_allow_git_stash_even_though_it_rewrites_the_work_tree
it_should_allow_a_test_run_whose_output_is_saved_outside_the_repo
it_should_allow_a_redirect_whose_target_is_an_unresolved_variable
it_should_allow_a_redirect_into_dev_null
it_should_allow_a_write_outside_any_git_work_tree
it_should_allow_a_search_whose_pattern_merely_contains_a_redirect_arrow
it_should_allow_a_write_after_a_cd_whose_destination_cannot_be_resolved
it_should_allow_a_read_only_sed_with_no_in_place_flag
it_should_allow_a_redirect_to_a_tilde_path_whose_home_is_outside_any_git_work_tree
it_should_allow_an_append_redirect_to_a_tilde_path_whose_home_is_outside_any_git_work_tree
it_should_allow_a_tee_to_a_tilde_path_whose_home_is_outside_any_git_work_tree
it_should_allow_an_in_place_sed_on_a_tilde_path_whose_home_is_outside_any_git_work_tree
it_should_block_an_in_place_sed_on_a_tilde_path_whose_home_is_inside_a_git_work_tree
it_should_block_a_redirect_to_a_tilde_path_whose_home_is_inside_a_git_work_tree
it_should_block_a_redirect_to_another_users_home_path_because_it_cannot_be_expanded

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
