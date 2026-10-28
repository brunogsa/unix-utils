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
  printf '{"name": "old-name"}\n' > "$scratch_dir/config.json"
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

# why: tasklist.md holds verbatim TaskGet text no edit may fix,
# so the prose hook exempts it by basename; a cat copy onto it
# must get the same exemption a Write does. The block test
# above is the counterpart: the same text onto README.md.
it_should_allow_copying_a_scratch_file_that_breaks_the_format_rules_onto_a_tasklist() {
  run_hook "cat $scratch_dir/batch.md >> docs/tasklist.md"
  assert_eq "should allow copying a /tmp scratch file whose prose breaks the markdown format rules onto tasklist.md, which the format rules exempt" "0" "$HOOK_EXIT"
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

it_should_allow_a_python_write_whose_target_path_is_built_at_runtime() {
  run_hook "python3 -c \"import os; open(os.path.join('src', 'new.ts'), 'w').write('x')\""
  assert_eq "should allow a python write whose path is computed at runtime, since the guard cannot read it off the script" "0" "$HOOK_EXIT"
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
it_should_allow_copying_a_scratch_file_that_breaks_the_format_rules_onto_a_tasklist
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
it_should_allow_a_python_write_whose_target_path_is_built_at_runtime

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
