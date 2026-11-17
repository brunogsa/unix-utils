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
scratch_dir=""

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
    printf '{"name": "old-name"}\n' > config.json
    printf '{"cache": "old-dir"}\n' > build/settings.json
    git add src/index.ts .gitignore README.md config.json
    git commit -q -m "init"
  )
  printf '### 1. [Task] Offloaded task\n' > "$outside_dir/batch.md"
  printf '{"name": "old-name"}\n' > "$outside_dir/config.json"

  # Scratch under /tmp, where a Bash write is never guarded and
  # the PostToolUse checker skips the file, so its content
  # reaches a copy unchecked unless the guard checks it.
  scratch_dir=$(mktemp -d /tmp/claude-bash-write-guard-scratch.XXXXXX)
  printf 'This paragraph was typed by hand and\nhard-wrapped across two lines.\n' > "$scratch_dir/batch.md"
  printf 'This paragraph was typed by hand and\nhard-wrapped across two lines.\n' > "$scratch_dir/draft"
  mkdir -p "$scratch_dir/notes"
  printf 'This paragraph was typed by hand and\nhard-wrapped across two lines.\n' > "$scratch_dir/notes/batch.md"
  printf '{"name": "old-name"}\n' > "$scratch_dir/config.json"
  printf '### 1. [metrics] Function over its size limit\n- The function spans\n80 lines.\n- Split it in two.\n' \
    > "$scratch_dir/findings.md"
}

teardown_fixtures() {
  [ -n "$fixture_base" ] && rm -rf "$fixture_base"
  [ -n "$scratch_dir" ] && rm -rf "$scratch_dir"
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

it_should_block_a_redirect_onto_a_yaml_file_the_comment_checker_handles() {
  run_hook "printf 'retries: 3' > config.yaml"
  assert_eq "should block a redirect onto a yaml file, which the prose-format hook routes to the comment checker" "2" "$HOOK_EXIT"
}

# run_guard_copy_without_extension_list - runs a copy of the
# guard from a hooks dir that lacks the shared extension list,
# capturing HOOK_EXIT and HOOK_STDERR.
#
# The copy keeps lib/parse-shell-command.py: without it the
# python import dies first, which proves nothing about the list.
run_guard_copy_without_extension_list() {
  local copy_dir="$fixture_base/hooks-without-extension-list" stdin_json
  mkdir -p "$copy_dir/lib"
  cp "$SCRIPT" "$copy_dir/"
  cp "$script_dir/lib/parse-shell-command.py" "$copy_dir/lib/"
  stdin_json=$(jq -n --arg c "$1" '{tool_input: {command: $c}}')
  HOOK_STDERR=$(
    cd "$sandbox_dir" || exit 1
    printf '%s' "$stdin_json" | "$bash_bin" "$copy_dir/claude-bash-write-guard.sh" 2>&1 >/dev/null
  )
  HOOK_EXIT=$?
}

it_should_block_any_extension_when_the_shared_extension_list_is_missing() {
  run_guard_copy_without_extension_list "printf '{}' > data.json"
  assert_eq "should block even a json redirect when the shared extension list cannot be read" "2" "$HOOK_EXIT"
}

it_should_block_a_cat_copy_when_the_shared_extension_list_is_missing() {
  run_guard_copy_without_extension_list "cat $outside_dir/batch.md >> README.md"
  assert_eq "should block a cat copy it cannot format-check because the shared extension list is missing" "2" "$HOOK_EXIT"
}

it_should_name_the_missing_extension_list_when_it_blocks_for_lack_of_it() {
  run_guard_copy_without_extension_list "printf '{}' > data.json"
  local named="no"
  case "$HOOK_STDERR" in
    *prose-format-extensions.sh*) named="yes" ;;
  esac
  assert_eq "should name the missing extension list file in the denial" "yes" "$named"
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

it_should_allow_appending_a_scratch_file_onto_a_tracked_markdown_file_with_cat() {
  run_hook "cat $outside_dir/batch.md >> README.md"
  assert_eq "should allow appending an existing scratch file onto a tracked markdown file with cat" "0" "$HOOK_EXIT"
}

it_should_allow_concatenating_several_existing_files_into_a_markdown_file_in_the_repo() {
  run_hook "cat README.md $outside_dir/batch.md > docs/combined.md"
  assert_eq "should allow concatenating several existing files into a markdown file inside the repo" "0" "$HOOK_EXIT"
}

it_should_allow_cp_copying_an_existing_file_into_the_repo() {
  run_hook "cp $outside_dir/batch.md docs/copy.md"
  assert_eq "should allow cp copying an existing file into the repo" "0" "$HOOK_EXIT"
}

it_should_block_a_heredoc_appended_onto_a_tracked_markdown_file_with_cat() {
  run_hook "$(printf 'cat >> README.md <<%s\n### 1. [Task] typed\nEOF\n' "'EOF'")"
  assert_eq "should block a heredoc appended onto a tracked markdown file with cat" "2" "$HOOK_EXIT"
}

it_should_block_cat_appending_text_piped_in_from_a_generator() {
  run_hook "echo 'typed line' | cat >> README.md"
  assert_eq "should block cat appending text piped in from echo onto a tracked markdown file" "2" "$HOOK_EXIT"
}

it_should_block_cat_appending_its_standard_input_named_as_a_dash() {
  run_hook "cat $outside_dir/batch.md - >> README.md"
  assert_eq "should block cat appending standard input named as a dash, even beside an existing file" "2" "$HOOK_EXIT"
}

it_should_block_cat_appending_a_source_file_that_does_not_exist() {
  run_hook "cat $outside_dir/missing.md >> README.md"
  assert_eq "should block cat appending a source file that does not exist" "2" "$HOOK_EXIT"
}

it_should_block_cat_appending_a_source_named_by_command_substitution() {
  run_hook 'cat "$(ls docs)" >> README.md'
  assert_eq "should block cat appending a source the guard cannot resolve to a literal existing file" "2" "$HOOK_EXIT"
}

it_should_block_cat_with_a_flag_that_rewrites_the_copied_content() {
  run_hook "cat -n $outside_dir/batch.md >> README.md"
  assert_eq "should block cat with a flag such as -n, which adds text the source file never held" "2" "$HOOK_EXIT"
}

it_should_block_a_copy_run_through_a_local_script_named_cat() {
  printf '#!/bin/sh\necho typed text\n' > "$outside_dir/cat"
  run_hook_in "$outside_dir" "./cat batch.md >> $sandbox_dir/README.md"
  rm -f "$outside_dir/cat"
  assert_eq "should block a copy run through a local script named cat, which can write any text" "2" "$HOOK_EXIT"
}

it_should_block_a_copy_through_cat_with_a_rewritten_search_path() {
  run_hook "PATH=/tmp:\$PATH cat $outside_dir/batch.md >> README.md"
  assert_eq "should block a cat copy run with a rewritten PATH, which can pick any program named cat" "2" "$HOOK_EXIT"
}

it_should_block_copying_a_scratch_file_whose_text_breaks_the_destinations_format_rules() {
  run_hook "cat $scratch_dir/batch.md >> README.md"
  assert_eq "should block copying a /tmp scratch file whose prose breaks the markdown format rules" "2" "$HOOK_EXIT"
}

# write-atomically.py writes its stdin to the path it is given,
# so a cat piped into it is a cat copy onto that path, as in
# quality-gate's verdict assembly.
it_should_block_cat_piping_a_hard_wrapped_finding_file_into_write_atomically_onto_a_repo_markdown_file() {
  run_hook "cat README.md $scratch_dir/findings.md | $HOME/.claude/scripts/write-atomically.py docs/verdict.md"
  assert_eq "should block cat piping a /tmp finding file with hard-wrapped, gap-less bullets into write-atomically.py onto a markdown file inside the repo" "2" "$HOOK_EXIT"
}

it_should_allow_cat_piping_files_that_pass_the_format_rules_into_write_atomically() {
  run_hook "cat README.md $outside_dir/batch.md | $HOME/.claude/scripts/write-atomically.py docs/verdict.md"
  assert_eq "should allow cat piping files that pass the markdown format rules into write-atomically.py onto a markdown file inside the repo" "0" "$HOOK_EXIT"
}

it_should_allow_write_atomically_restoring_a_file_from_a_stdin_redirect() {
  run_hook "$HOME/.claude/scripts/write-atomically.py README.md < $outside_dir/batch.md"
  assert_eq "should allow write-atomically.py writing a repo markdown file from a stdin redirect, which it does not check" "0" "$HOOK_EXIT"
}

# why: tasklist.md holds verbatim TaskGet text no edit may fix,
# so the prose hook exempts it by basename; a cat copy onto it
# must get the same exemption a Write does. The block test
# above is the counterpart: the same text onto README.md.
it_should_allow_copying_a_scratch_file_that_breaks_the_format_rules_onto_a_tasklist() {
  run_hook "cat $scratch_dir/batch.md >> docs/tasklist.md"
  assert_eq "should allow copying a /tmp scratch file whose prose breaks the markdown format rules onto tasklist.md, which the format rules exempt" "0" "$HOOK_EXIT"
}

# File-copy cases: cp, mv and install land a source's text in
# their destination unchanged, the same as a cat copy, so the
# same source check applies.
it_should_block_cp_copying_a_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file() {
  run_hook "cp $scratch_dir/batch.md README.md"
  assert_eq "should block cp copying a /tmp scratch file whose prose breaks the markdown format rules over a tracked markdown file" "2" "$HOOK_EXIT"
}

it_should_block_mv_moving_a_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file() {
  run_hook "mv $scratch_dir/batch.md README.md"
  assert_eq "should block mv moving a /tmp scratch file whose prose breaks the markdown format rules over a tracked markdown file" "2" "$HOOK_EXIT"
}

# why: a rename inside the repo needs no text rewrite, and
# `git mv` is the form the guard never blocks.
it_should_suggest_git_mv_when_it_blocks_an_in_repo_mv_of_a_markdown_file_that_breaks_the_format_rules() {
  printf 'This paragraph was typed by hand and\nhard-wrapped across two lines.\n' > "$sandbox_dir/docs/wrapped.md"
  run_hook_capturing_stderr "mv docs/wrapped.md docs/renamed.md"
  rm -f "$sandbox_dir/docs/wrapped.md"
  assert_eq "should block mv renaming a repo markdown file whose prose breaks the format rules" "2" "$HOOK_EXIT"
  local names_git_mv="no"
  case "$HOOK_STDERR" in
    *'git mv'*) names_git_mv="yes" ;;
  esac
  assert_eq "should suggest git mv when it blocks mv renaming a repo markdown file whose prose breaks the format rules" "yes" "$names_git_mv"
}

it_should_block_install_copying_a_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file() {
  run_hook "install $scratch_dir/batch.md README.md"
  assert_eq "should block install copying a /tmp scratch file whose prose breaks the markdown format rules over a tracked markdown file" "2" "$HOOK_EXIT"
}

it_should_block_cp_copying_a_scratch_file_that_breaks_the_format_rules_into_a_repo_directory() {
  run_hook "cp $scratch_dir/batch.md docs"
  assert_eq "should block cp copying a /tmp scratch file whose prose breaks the markdown format rules into a repo directory, which writes docs/batch.md" "2" "$HOOK_EXIT"
}

it_should_block_cp_copying_a_scratch_file_that_breaks_the_format_rules_into_a_target_directory_named_by_t() {
  run_hook "cp -t docs $scratch_dir/batch.md"
  assert_eq "should block cp -t docs copying a /tmp scratch file whose prose breaks the markdown format rules into the repo" "2" "$HOOK_EXIT"
}

# why: `644` is the mode, not a second source, so the copy
# still lands on README.md and the extensionless draft must be
# checked as README.md.
it_should_block_install_with_a_mode_copying_an_extensionless_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file() {
  run_hook "install -m 644 $scratch_dir/draft README.md"
  assert_eq "should block install -m 644 copying an extensionless /tmp scratch file whose prose breaks the markdown format rules over a tracked markdown file" "2" "$HOOK_EXIT"
}

# why: a directory copy writes files the guard cannot list one
# by one, so any directory landing in the repo blocks.
it_should_block_cp_recursively_copying_a_scratch_directory_into_a_repo_directory() {
  run_hook "cp -r $scratch_dir/notes docs"
  assert_eq "should block cp -r copying a /tmp scratch directory of markdown files into a repo directory" "2" "$HOOK_EXIT"
}

it_should_block_mv_moving_a_scratch_directory_into_the_repo() {
  run_hook "mv $scratch_dir/notes docs/notes"
  assert_eq "should block mv moving a /tmp scratch directory of markdown files into the repo, which needs no recursive flag" "2" "$HOOK_EXIT"
}

it_should_block_cp_archive_copying_a_source_named_by_a_variable_into_a_repo_directory() {
  run_hook "cp -a \$NOTES_DIR docs"
  assert_eq "should block cp -a copying a source named by a shell variable into a repo directory, since it may be a directory" "2" "$HOOK_EXIT"
}

# why: the guard runs before the command, so a directory an
# earlier mkdir in the same command creates reads as missing.
it_should_block_cp_copying_two_scratch_files_into_a_repo_directory_the_same_command_creates() {
  run_hook "mkdir docs/new && cp $scratch_dir/batch.md $scratch_dir/draft docs/new"
  assert_eq "should block cp copying two /tmp scratch files, one breaking the markdown format rules, into a repo directory an earlier mkdir in the same command creates" "2" "$HOOK_EXIT"
}

it_should_block_install_whose_unknown_flag_argument_could_be_a_second_source_over_a_tracked_markdown_file() {
  run_hook "install -B .bak $scratch_dir/draft README.md"
  assert_eq "should block install -B .bak copying an extensionless /tmp scratch file whose prose breaks the markdown format rules over a tracked markdown file, though .bak reads as a second source" "2" "$HOOK_EXIT"
}

# why: macOS cp reads -S as a flag with no argument, so the
# next token is a source there, while GNU cp takes it as -S's
# backup suffix.
it_should_block_cp_with_s_copying_a_scratch_file_that_breaks_the_format_rules_over_a_repo_markdown_file() {
  run_hook "cp -S $scratch_dir/batch.md docs/README.md"
  assert_eq "should block cp -S copying a /tmp scratch file whose prose breaks the markdown format rules over a repo markdown file, as macOS cp does" "2" "$HOOK_EXIT"
}

it_should_allow_cp_with_a_gnu_backup_suffix_copying_a_file_that_passes_the_format_rules_into_a_repo_directory() {
  run_hook "cp -S .bak $outside_dir/batch.md docs/"
  assert_eq "should allow cp -S .bak copying a file whose prose passes the markdown format rules into a repo directory, when no file is named .bak" "0" "$HOOK_EXIT"
}

it_should_block_cp_recursively_copying_a_scratch_directory_the_same_command_creates_into_a_repo_directory() {
  run_hook "mkdir $scratch_dir/fresh && cp -r $scratch_dir/fresh docs/"
  assert_eq "should block cp -r copying a /tmp scratch directory an earlier mkdir in the same command creates into a repo directory" "2" "$HOOK_EXIT"
}

it_should_allow_install_with_a_mode_copying_a_file_that_passes_the_format_rules_over_a_tracked_markdown_file() {
  run_hook "install -m 644 $outside_dir/batch.md README.md"
  assert_eq "should allow install -m 644 copying a file whose prose passes the markdown format rules over a tracked markdown file" "0" "$HOOK_EXIT"
}

it_should_allow_mv_moving_a_file_that_passes_the_format_rules_over_a_tracked_markdown_file() {
  run_hook "mv $outside_dir/batch.md README.md"
  assert_eq "should allow mv moving a file whose prose passes the markdown format rules over a tracked markdown file" "0" "$HOOK_EXIT"
}

it_should_allow_install_copying_a_file_that_passes_the_format_rules_into_the_repo() {
  run_hook "install $outside_dir/batch.md docs/installed.md"
  assert_eq "should allow install copying a file whose prose passes the markdown format rules into the repo" "0" "$HOOK_EXIT"
}

it_should_allow_cp_copying_a_scratch_file_that_breaks_the_format_rules_into_tmp() {
  run_hook "cp $scratch_dir/batch.md $scratch_dir/copy.md"
  assert_eq "should allow cp copying a /tmp scratch file whose prose breaks the markdown format rules to another path under /tmp" "0" "$HOOK_EXIT"
}

it_should_allow_cp_copying_a_scratch_file_that_breaks_the_format_rules_outside_any_git_work_tree() {
  run_hook "cp $scratch_dir/batch.md $outside_dir/copy.md"
  assert_eq "should allow cp copying a /tmp scratch file whose prose breaks the markdown format rules to a path outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_allow_cp_copying_a_scratch_file_that_breaks_the_format_rules_onto_a_gitignored_path() {
  run_hook "cp $scratch_dir/batch.md build/copy.md"
  assert_eq "should allow cp copying a /tmp scratch file whose prose breaks the markdown format rules onto a git-ignored path" "0" "$HOOK_EXIT"
}

it_should_allow_cp_recursively_copying_a_scratch_directory_onto_a_gitignored_path() {
  run_hook "cp -r $scratch_dir/notes build/"
  assert_eq "should allow cp -r copying a /tmp scratch directory of markdown files onto a git-ignored path" "0" "$HOOK_EXIT"
}

it_should_allow_cp_recursively_copying_a_scratch_directory_into_tmp() {
  run_hook "cp -R $scratch_dir/notes $scratch_dir/notes-copy"
  assert_eq "should allow cp -R copying a /tmp scratch directory of markdown files to another path under /tmp" "0" "$HOOK_EXIT"
}

it_should_allow_git_mv_renaming_a_tracked_markdown_file() {
  run_hook "git mv README.md docs/README.md"
  assert_eq "should allow git mv renaming a tracked markdown file, which is no cp, mv or install" "0" "$HOOK_EXIT"
}

# Script-shape cases: an in-place edit that is not one literal
# replace-all over the whole file is blocked on any extension,
# since Edit (replace_all, or a widened old_string) can always
# make the same change with a diff and a mismatch error.
#
# config.json carries an extension the prose checkers ignore,
# so these outcomes come from the script shape alone.

# run_hook_capturing_stderr - same as run_hook, also capturing
# the guard's denial text into HOOK_STDERR.
run_hook_capturing_stderr() {
  local stdin_json
  stdin_json=$(jq -n --arg c "$1" '{tool_input: {command: $c}}')
  HOOK_STDERR=$(
    cd "$sandbox_dir" || exit 1
    printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null
  )
  HOOK_EXIT=$?
}

it_should_block_an_in_place_perl_whose_flag_cluster_starts_with_a_slurp_digit() {
  run_hook "perl -0pi -e 's/old-name/new-name/g' README.md"
  assert_eq "should block an in-place perl written as -0pi on a tracked markdown file" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_sed_limited_to_a_line_range() {
  run_hook "sed -i '' '195,418s/old-name/new-name/' config.json"
  assert_eq "should block an in-place sed limited to a line range, even on an extension the prose checkers ignore" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_perl_limited_to_a_line_range() {
  run_hook "perl -i -pe '195..418 and s/old-name/new-name/' config.json"
  assert_eq "should block an in-place perl limited to a line range" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_perl_whose_substitution_runs_under_a_condition() {
  run_hook "perl -0pi -e 'if (\$. >= 195 && \$. <= 418) { s/old-name/new-name/ }' config.json"
  assert_eq "should block an in-place perl whose substitution runs only when a line-number condition holds" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_perl_running_several_statements() {
  run_hook "perl -pi -e 's/old-name/new-name/g; s/old-dir/new-dir/g' config.json"
  assert_eq "should block an in-place perl running several statements in one script" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_sed_given_several_scripts() {
  run_hook "sed -i '' -e 's/old-name/new-name/g' -e 's/old-dir/new-dir/g' config.json"
  assert_eq "should block an in-place sed given several -e scripts" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_perl_substitution_that_evaluates_code() {
  run_hook "perl -pi -e 's/(\\d+)/\$1+1/ge' config.json"
  assert_eq "should block an in-place perl substitution whose /e flag evaluates the replacement as code" "2" "$HOOK_EXIT"
}

it_should_block_an_in_place_sed_whose_pattern_is_a_regex_rather_than_literal_text() {
  run_hook "sed -i '' 's/^{.*\$/{}/g' config.json"
  assert_eq "should block an in-place sed whose pattern uses regex anchors and wildcards instead of literal text" "2" "$HOOK_EXIT"
}

it_should_block_a_line_range_in_place_sed_on_a_gitignored_file() {
  run_hook "sed -i '' '1,2s/old-dir/new-dir/' build/settings.json"
  assert_eq "should block a line-range in-place sed on a git-ignored file inside the repo" "2" "$HOOK_EXIT"
}

it_should_tell_the_agent_to_use_the_edit_tool_when_it_blocks_a_line_range_edit() {
  run_hook_capturing_stderr "sed -i '' '195,418s/old-name/new-name/' config.json"
  local names_edit="no"
  case "$HOOK_STDERR" in
    *replace_all*old_string*) names_edit="yes" ;;
  esac
  assert_eq "should tell the agent to use Edit with replace_all, or an old_string widened to be unique" "yes" "$names_edit"
}

it_should_allow_an_in_place_sed_replacing_one_literal_text_across_the_whole_file() {
  run_hook "sed -i '' 's/old-name/new-name/g' config.json"
  assert_eq "should allow an in-place BSD sed replacing one literal text across the whole json file" "0" "$HOOK_EXIT"
}

it_should_allow_an_in_place_gnu_sed_replacing_one_literal_text_across_the_whole_file() {
  run_hook "gsed -i 's/old-name/new-name/g' config.json"
  assert_eq "should allow an in-place GNU sed, which takes no backup-suffix argument, replacing one literal text across the whole json file" "0" "$HOOK_EXIT"
}

it_should_allow_an_in_place_sed_whose_switch_cluster_ends_in_the_in_place_flag() {
  run_hook "sed -Ei '' 's/old-name/new-name/g' config.json"
  assert_eq "should allow an in-place BSD sed written as -Ei with an empty backup suffix, replacing one literal text across the whole file" "0" "$HOOK_EXIT"
}

it_should_allow_an_in_place_perl_replacing_one_literal_text_across_the_whole_file() {
  run_hook "perl -pi -e 's/old-name/new-name/g' config.json"
  assert_eq "should allow an in-place perl replacing one literal text across the whole json file" "0" "$HOOK_EXIT"
}

it_should_allow_a_line_range_in_place_sed_on_a_scratch_file() {
  run_hook "sed -i '' '1,2s/old-name/new-name/' $scratch_dir/config.json"
  assert_eq "should allow a line-range in-place sed on a /tmp scratch file" "0" "$HOOK_EXIT"
}

it_should_allow_a_line_range_in_place_sed_on_a_file_outside_any_git_work_tree() {
  run_hook "sed -i '' '1,2s/old-name/new-name/' $outside_dir/config.json"
  assert_eq "should allow a line-range in-place sed on a file outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_opening_a_repo_source_file_for_writing() {
  run_hook "python3 -c \"open('src/new.ts', 'w').write('export const y = 2;')\""
  assert_eq "should block a python one-liner that opens a repo typescript file for writing" "2" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_appending_to_a_tracked_markdown_file() {
  run_hook "python3 -c \"open('README.md', mode='a').write('one more line')\""
  assert_eq "should block a python one-liner that opens a tracked markdown file for appending" "2" "$HOOK_EXIT"
}

it_should_block_a_python_heredoc_script_rewriting_a_repo_file_named_by_a_variable() {
  run_hook "$(printf "python3 - <<'EOF'\np = 'src/index.ts'\ns = open(p).read()\nopen(p, 'w').write(s.replace('const', 'let'))\nEOF\n")"
  assert_eq "should block a python heredoc script that reads a repo file through a variable and writes it back" "2" "$HOOK_EXIT"
}

it_should_allow_a_python_one_liner_that_only_reads_a_repo_source_file() {
  run_hook "python3 -c \"print(open('src/index.ts').read(), open('src/index.ts', 'r').read())\""
  assert_eq "should allow a python one-liner that opens a repo file only for reading" "0" "$HOOK_EXIT"
}

it_should_block_a_python_write_whose_target_path_is_built_at_runtime() {
  run_hook "python3 -c \"import os; open(os.path.join('src', 'new.ts'), 'w').write('x')\""
  assert_eq "should block a python write whose path is computed at runtime, since the guard cannot rule out a guarded file" "2" "$HOOK_EXIT"
}

it_should_block_a_python_pathlib_write_text_onto_a_repo_source_file() {
  run_hook "python3 -c \"import pathlib; pathlib.Path('src/new.ts').write_text('export const y = 2;')\""
  assert_eq "should block a python pathlib write_text onto a repo typescript file" "2" "$HOOK_EXIT"
}

it_should_block_a_python_path_write_bytes_onto_a_repo_markdown_file_after_importing_path() {
  run_hook "python3 -c \"from pathlib import Path; Path('docs/new.md').write_bytes(b'# Title')\""
  assert_eq "should block a python Path write_bytes, imported from pathlib, onto a repo markdown file" "2" "$HOOK_EXIT"
}

it_should_block_a_node_one_liner_writing_a_repo_source_file() {
  run_hook "node -e \"require('fs').writeFileSync('src/new.ts', 'export const y = 2;')\""
  assert_eq "should block a node one-liner whose fs writeFileSync targets a repo typescript file" "2" "$HOOK_EXIT"
}

it_should_block_a_node_one_liner_appending_to_a_tracked_markdown_file() {
  run_hook "node -e \"const fs = require('fs'); fs.appendFileSync('README.md', 'one more line')\""
  assert_eq "should block a node one-liner whose fs appendFileSync targets a tracked markdown file" "2" "$HOOK_EXIT"
}

it_should_allow_a_python_write_into_a_scratch_directory() {
  run_hook "python3 -c \"open('$scratch_dir/new.ts', 'w').write('x')\""
  assert_eq "should allow a python write onto a typescript file under /tmp scratch" "0" "$HOOK_EXIT"
}

it_should_allow_a_python_write_onto_a_file_outside_any_git_work_tree() {
  run_hook "python3 -c \"import pathlib; pathlib.Path('$outside_dir/new.md').write_text('x')\""
  assert_eq "should allow a python write onto a markdown file outside any git work tree" "0" "$HOOK_EXIT"
}

it_should_allow_a_python_write_onto_a_gitignored_path() {
  run_hook "python3 -c \"open('build/bundle.js', 'w').write('compiled')\""
  assert_eq "should allow a python write onto a git-ignored path inside the repo" "0" "$HOOK_EXIT"
}

it_should_allow_a_python_write_onto_an_extension_the_prose_checkers_ignore() {
  run_hook "python3 -c \"open('config.json', 'w').write('{}')\""
  assert_eq "should allow a python write onto a json file, which no prose checker handles" "0" "$HOOK_EXIT"
}

it_should_allow_a_node_write_into_a_scratch_directory() {
  run_hook "node -e \"require('fs').writeFileSync('$scratch_dir/new.ts', 'x')\""
  assert_eq "should allow a node write onto a typescript file under /tmp scratch" "0" "$HOOK_EXIT"
}

it_should_allow_a_python_script_that_only_reads_and_prints_a_repo_file() {
  run_hook "python3 -c \"import json; print(json.load(open('config.json')))\""
  assert_eq "should allow a python script that only loads a repo json file and prints it" "0" "$HOOK_EXIT"
}

it_should_tell_the_agent_to_use_the_edit_or_write_tool_when_it_blocks_an_interpreter_write() {
  run_hook_capturing_stderr "python3 -c \"open('src/new.ts', 'w').write('x')\""
  local names_tools="no"
  case "$HOOK_STDERR" in
    *Edit\ or\ Write*) names_tools="yes" ;;
  esac
  assert_eq "should name the Edit or Write tool when it blocks a python write to a repo file" "yes" "$names_tools"
}

# The 2026-11-17 bypass: a subagent rewrote tracked markdown
# files with `cd ~/<repo>/<dir> && python3 - <<'E'`, the path
# held in a variable and relative to that `cd`.
it_should_block_a_python_heredoc_rewriting_a_markdown_file_named_by_a_variable_after_a_home_relative_cd() {
  local home_relative_docs="~/${fixture_base#"$HOME"/}/repo/docs"
  run_hook "$(printf "cd %s && python3 - <<'E'\np='SKILL.md'; s=open(p).read()\ns=s.replace(\"a\",\"b\",1)\nopen(p,'w').write(s)\nE\n" "$home_relative_docs")"
  assert_eq "should block a python heredoc that rewrites a markdown file named by a variable, after a cd into a home-relative repo directory" "2" "$HOOK_EXIT"
}

it_should_block_a_python_heredoc_writing_a_markdown_file_after_a_cd_into_a_directory_it_cannot_resolve() {
  run_hook "$(printf "cd \"\$SKILL_DIR\" && python3 - <<'E'\nq='references/scout-leg.md'; t=open(q).read()\nopen(q,'w').write(t)\nE\n")"
  assert_eq "should block a python heredoc writing a relative markdown path after a cd whose directory the guard cannot resolve" "2" "$HOOK_EXIT"
}

it_should_allow_a_python_heredoc_writing_a_json_file_after_a_cd_into_a_directory_it_cannot_resolve() {
  run_hook "$(printf "cd \"\$SKILL_DIR\" && python3 - <<'E'\nopen('settings.json','w').write('{}')\nE\n")"
  assert_eq "should allow a python heredoc writing a json file, which no prose checker handles, after a cd the guard cannot resolve" "0" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_writing_a_markdown_file_named_by_a_variable() {
  run_hook "python3 -c \"p='docs/notes.md'; open(p,'w').write('# Notes')\""
  assert_eq "should block a python one-liner that writes a repo markdown file named by a variable" "2" "$HOOK_EXIT"
}

it_should_block_a_python_pathlib_write_text_onto_a_path_taken_from_the_command_line() {
  run_hook "python3 -c \"import pathlib, sys; p = sys.argv[1]; pathlib.Path(p).write_text('# Notes')\" docs/notes.md"
  assert_eq "should block a python pathlib write_text whose path comes from a command-line argument the guard cannot read" "2" "$HOOK_EXIT"
}

it_should_block_a_python_open_for_writing_whose_mode_is_not_a_literal() {
  run_hook "python3 -c \"import sys; m = sys.argv[1]; open('README.md', m).write('x')\" w"
  assert_eq "should block a python open of a tracked markdown file whose mode the guard cannot read, since it may write" "2" "$HOOK_EXIT"
}

it_should_block_a_python_write_after_the_program_changes_its_own_directory() {
  run_hook "python3 -c \"import os; os.chdir('docs'); open('notes.md', 'w').write('# Notes')\""
  assert_eq "should block a python write that follows a chdir inside the program, since its directory is unknown" "2" "$HOOK_EXIT"
}

it_should_allow_a_python_write_into_a_scratch_directory_after_the_program_changes_its_own_directory() {
  run_hook "python3 -c \"import os; os.chdir('docs'); open('$scratch_dir/notes.md', 'w').write('# Notes')\""
  assert_eq "should allow a python write onto an absolute /tmp scratch path even after a chdir inside the program" "0" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_whose_target_path_is_a_shell_variable() {
  run_hook "python3 -c \"open('\$TARGET', 'w').write('x')\""
  assert_eq "should block a python one-liner whose path is a shell variable the guard cannot expand" "2" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_whose_file_extension_is_a_shell_variable() {
  run_hook "python3 -c \"open('SKILL.\${E}', 'w').write('x')\""
  assert_eq "should block a python write to SKILL.\${E}, since the shell may expand the extension into md" "2" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_whose_file_extension_is_a_command_substitution() {
  run_hook "python3 -c \"open('notes.\`echo md\`', 'w').write('x')\""
  assert_eq "should block a python write to a file name ending in a backtick command substitution" "2" "$HOOK_EXIT"
}

it_should_block_a_python_one_liner_whose_whole_path_is_a_command_substitution_printing_a_markdown_path() {
  run_hook "python3 -c \"open('\$(printf docs/SKILL.md)', 'w').write('x')\""
  assert_eq "should block a python write to a \$(...) substitution, even when its text shows a slash and an extension" "2" "$HOOK_EXIT"
}

it_should_allow_a_python_one_liner_writing_a_json_file_under_a_shell_variable_directory() {
  run_hook "python3 -c \"open('\$TMPDIR/out.json', 'w').write('{}')\""
  assert_eq "should allow a python write to a literal .json file name under a shell-variable directory" "0" "$HOOK_EXIT"
}

it_should_block_a_node_write_whose_target_path_is_a_variable() {
  run_hook "node -e \"const fs = require('fs'); const p = process.argv[1]; fs.writeFileSync(p, '# Notes')\" docs/notes.md"
  assert_eq "should block a node writeFileSync whose path is a variable the guard cannot read" "2" "$HOOK_EXIT"
}

it_should_allow_a_python_heredoc_that_only_reads_a_markdown_file_named_by_a_variable_after_a_home_relative_cd() {
  local home_relative_repo="~/${fixture_base#"$HOME"/}/repo"
  run_hook "$(printf "cd %s && python3 - <<'E'\np='README.md'; s=open(p).read()\nprint(s.count('Readme'))\nE\n" "$home_relative_repo")"
  assert_eq "should allow a python heredoc that only reads a markdown file named by a variable, after a home-relative cd" "0" "$HOOK_EXIT"
}

it_should_tell_the_agent_to_use_the_edit_or_write_tool_when_it_blocks_a_write_to_an_unreadable_path() {
  run_hook_capturing_stderr "python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\" docs/notes.md"
  local names_tools="no"
  case "$HOOK_STDERR" in
    *Edit\ or\ Write*) names_tools="yes" ;;
  esac
  assert_eq "should name the Edit or Write tool when it blocks a python write whose path it cannot read" "yes" "$names_tools"
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
it_should_block_a_redirect_onto_a_yaml_file_the_comment_checker_handles
it_should_block_any_extension_when_the_shared_extension_list_is_missing
it_should_block_a_cat_copy_when_the_shared_extension_list_is_missing
it_should_name_the_missing_extension_list_when_it_blocks_for_lack_of_it
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
it_should_allow_appending_a_scratch_file_onto_a_tracked_markdown_file_with_cat
it_should_allow_concatenating_several_existing_files_into_a_markdown_file_in_the_repo
it_should_allow_cp_copying_an_existing_file_into_the_repo
it_should_block_a_heredoc_appended_onto_a_tracked_markdown_file_with_cat
it_should_block_cat_appending_text_piped_in_from_a_generator
it_should_block_cat_appending_its_standard_input_named_as_a_dash
it_should_block_cat_appending_a_source_file_that_does_not_exist
it_should_block_cat_appending_a_source_named_by_command_substitution
it_should_block_cat_with_a_flag_that_rewrites_the_copied_content
it_should_block_a_copy_run_through_a_local_script_named_cat
it_should_block_a_copy_through_cat_with_a_rewritten_search_path
it_should_block_copying_a_scratch_file_whose_text_breaks_the_destinations_format_rules
it_should_block_cat_piping_a_hard_wrapped_finding_file_into_write_atomically_onto_a_repo_markdown_file
it_should_allow_cat_piping_files_that_pass_the_format_rules_into_write_atomically
it_should_allow_write_atomically_restoring_a_file_from_a_stdin_redirect
it_should_allow_copying_a_scratch_file_that_breaks_the_format_rules_onto_a_tasklist
it_should_block_cp_copying_a_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file
it_should_block_mv_moving_a_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file
it_should_suggest_git_mv_when_it_blocks_an_in_repo_mv_of_a_markdown_file_that_breaks_the_format_rules
it_should_block_install_copying_a_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file
it_should_block_cp_copying_a_scratch_file_that_breaks_the_format_rules_into_a_repo_directory
it_should_block_cp_copying_a_scratch_file_that_breaks_the_format_rules_into_a_target_directory_named_by_t
it_should_block_install_with_a_mode_copying_an_extensionless_scratch_file_that_breaks_the_format_rules_over_a_tracked_markdown_file
it_should_allow_install_with_a_mode_copying_a_file_that_passes_the_format_rules_over_a_tracked_markdown_file
it_should_block_cp_recursively_copying_a_scratch_directory_into_a_repo_directory
it_should_block_mv_moving_a_scratch_directory_into_the_repo
it_should_block_cp_archive_copying_a_source_named_by_a_variable_into_a_repo_directory
it_should_block_cp_copying_two_scratch_files_into_a_repo_directory_the_same_command_creates
it_should_block_install_whose_unknown_flag_argument_could_be_a_second_source_over_a_tracked_markdown_file
it_should_block_cp_recursively_copying_a_scratch_directory_the_same_command_creates_into_a_repo_directory
it_should_block_cp_with_s_copying_a_scratch_file_that_breaks_the_format_rules_over_a_repo_markdown_file
it_should_allow_cp_with_a_gnu_backup_suffix_copying_a_file_that_passes_the_format_rules_into_a_repo_directory
it_should_allow_mv_moving_a_file_that_passes_the_format_rules_over_a_tracked_markdown_file
it_should_allow_install_copying_a_file_that_passes_the_format_rules_into_the_repo
it_should_allow_cp_copying_a_scratch_file_that_breaks_the_format_rules_into_tmp
it_should_allow_cp_copying_a_scratch_file_that_breaks_the_format_rules_outside_any_git_work_tree
it_should_allow_cp_copying_a_scratch_file_that_breaks_the_format_rules_onto_a_gitignored_path
it_should_allow_cp_recursively_copying_a_scratch_directory_onto_a_gitignored_path
it_should_allow_cp_recursively_copying_a_scratch_directory_into_tmp
it_should_allow_git_mv_renaming_a_tracked_markdown_file
it_should_block_an_in_place_perl_whose_flag_cluster_starts_with_a_slurp_digit
it_should_block_an_in_place_sed_limited_to_a_line_range
it_should_block_an_in_place_perl_limited_to_a_line_range
it_should_block_an_in_place_perl_whose_substitution_runs_under_a_condition
it_should_block_an_in_place_perl_running_several_statements
it_should_block_an_in_place_sed_given_several_scripts
it_should_block_an_in_place_perl_substitution_that_evaluates_code
it_should_block_an_in_place_sed_whose_pattern_is_a_regex_rather_than_literal_text
it_should_block_a_line_range_in_place_sed_on_a_gitignored_file
it_should_tell_the_agent_to_use_the_edit_tool_when_it_blocks_a_line_range_edit
it_should_allow_an_in_place_sed_replacing_one_literal_text_across_the_whole_file
it_should_allow_an_in_place_gnu_sed_replacing_one_literal_text_across_the_whole_file
it_should_allow_an_in_place_sed_whose_switch_cluster_ends_in_the_in_place_flag
it_should_allow_an_in_place_perl_replacing_one_literal_text_across_the_whole_file
it_should_allow_a_line_range_in_place_sed_on_a_scratch_file
it_should_allow_a_line_range_in_place_sed_on_a_file_outside_any_git_work_tree
it_should_block_a_python_one_liner_opening_a_repo_source_file_for_writing
it_should_block_a_python_one_liner_appending_to_a_tracked_markdown_file
it_should_block_a_python_heredoc_script_rewriting_a_repo_file_named_by_a_variable
it_should_allow_a_python_one_liner_that_only_reads_a_repo_source_file
it_should_block_a_python_write_whose_target_path_is_built_at_runtime
it_should_block_a_python_pathlib_write_text_onto_a_repo_source_file
it_should_block_a_python_path_write_bytes_onto_a_repo_markdown_file_after_importing_path
it_should_block_a_node_one_liner_writing_a_repo_source_file
it_should_block_a_node_one_liner_appending_to_a_tracked_markdown_file
it_should_allow_a_python_write_into_a_scratch_directory
it_should_allow_a_python_write_onto_a_file_outside_any_git_work_tree
it_should_allow_a_python_write_onto_a_gitignored_path
it_should_allow_a_python_write_onto_an_extension_the_prose_checkers_ignore
it_should_allow_a_node_write_into_a_scratch_directory
it_should_allow_a_python_script_that_only_reads_and_prints_a_repo_file
it_should_tell_the_agent_to_use_the_edit_or_write_tool_when_it_blocks_an_interpreter_write
it_should_block_a_python_heredoc_rewriting_a_markdown_file_named_by_a_variable_after_a_home_relative_cd
it_should_block_a_python_heredoc_writing_a_markdown_file_after_a_cd_into_a_directory_it_cannot_resolve
it_should_allow_a_python_heredoc_writing_a_json_file_after_a_cd_into_a_directory_it_cannot_resolve
it_should_block_a_python_one_liner_writing_a_markdown_file_named_by_a_variable
it_should_block_a_python_pathlib_write_text_onto_a_path_taken_from_the_command_line
it_should_block_a_python_open_for_writing_whose_mode_is_not_a_literal
it_should_block_a_python_write_after_the_program_changes_its_own_directory
it_should_allow_a_python_write_into_a_scratch_directory_after_the_program_changes_its_own_directory
it_should_block_a_python_one_liner_whose_target_path_is_a_shell_variable
it_should_block_a_python_one_liner_whose_file_extension_is_a_shell_variable
it_should_block_a_python_one_liner_whose_file_extension_is_a_command_substitution
it_should_block_a_python_one_liner_whose_whole_path_is_a_command_substitution_printing_a_markdown_path
it_should_allow_a_python_one_liner_writing_a_json_file_under_a_shell_variable_directory
it_should_block_a_node_write_whose_target_path_is_a_variable
it_should_allow_a_python_heredoc_that_only_reads_a_markdown_file_named_by_a_variable_after_a_home_relative_cd
it_should_tell_the_agent_to_use_the_edit_or_write_tool_when_it_blocks_a_write_to_an_unreadable_path

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
