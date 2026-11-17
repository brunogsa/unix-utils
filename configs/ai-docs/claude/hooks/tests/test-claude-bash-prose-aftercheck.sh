#!/usr/bin/env bash
# Plain-bash test file for claude-bash-prose-aftercheck.sh.
#
# Usage:
#   bash test-claude-bash-prose-aftercheck.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# Each test drives the hook the way Claude Code does: the
# PreToolUse --mark step, then the Bash command itself, then
# the PostToolUse step, all with one tool_use_id.
#
# Every test gets its own fixture repo under a private
# TMPDIR, which also holds the markers, so no test sees
# another's files.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-bash-prose-aftercheck.sh"
SETTINGS="$script_dir/../settings.json"

pass_count=0
fail_count=0

TMPDIR=$(mktemp -d)
export TMPDIR
trap 'rm -rf "$TMPDIR"' EXIT

bash_bin="$(command -v bash)"

# Prose the markdown checker reports: one paragraph split
# across two physical lines, a hard-wrap finding.
HARD_WRAPPED_PROSE=$'This paragraph was typed by hand and\nhard-wrapped across two lines.\n'

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

assert_contains() {
  local description="$1" needle="$2" actual="$3"
  if [[ "$actual" == *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected to contain: %s\n  actual:   %s\n' "$description" "$needle" "$actual"
  fi
}

# new_fixture - a fresh repo with one committed README.md, an
# ignored build/ and an empty docs/, plus a scratch dir
# outside it holding a hard-wrapped a.md.
#
# Sets repo_dir and scratch_dir.
new_fixture() {
  local base
  base=$(mktemp -d "$TMPDIR/fixture.XXXXXX")
  repo_dir="$base/repo"
  scratch_dir="$base/scratch"
  mkdir -p "$repo_dir/docs" "$repo_dir/build" "$scratch_dir"
  (
    cd "$repo_dir" || exit 1
    git init -q
    git config user.email "test@example.com"
    git config user.name "Test"
    printf '# Readme\n' > README.md
    printf 'build/\n' > .gitignore
    git add README.md .gitignore
    git commit -q -m "init"
  )
  printf '%s' "$HARD_WRAPPED_PROSE" > "$scratch_dir/a.md"
}

# run_marker / run_aftercheck - one hook step cwd'd into the
# given dir, for a Bash payload with the given tool_use_id.
#
# run_aftercheck sets AFTER_EXIT and AFTER_STDERR.
run_marker() {
  local dir="$1" id="$2"
  (
    cd "$dir" || exit 1
    jq -n --arg id "$id" '{tool_name:"Bash",tool_use_id:$id}' \
      | "$bash_bin" "$SCRIPT" --mark >/dev/null 2>&1
  )
}

run_aftercheck() {
  local dir="$1" id="$2"
  AFTER_STDERR=$(
    cd "$dir" || exit 1
    jq -n --arg id "$id" '{tool_name:"Bash",tool_use_id:$id}' \
      | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null
  )
  AFTER_EXIT=$?
}

# run_command_with_hooks - mark, run the command, then run
# the after-check, all in dir under the same tool_use_id.
call_count=0
run_command_with_hooks() {
  local dir="$1" command="$2" id
  call_count=$((call_count + 1))
  id="toolu_01AfterCheck$call_count"
  run_marker "$dir" "$id"
  (cd "$dir" && "$bash_bin" -c "$command") >/dev/null 2>&1
  run_aftercheck "$dir" "$id"
}

# --- reports what a Bash command landed -------------------

it_should_report_a_markdown_file_copied_into_a_directory_the_same_command_created() {
  new_fixture
  run_command_with_hooks "$repo_dir" "mkdir docs/new && cp $scratch_dir/a.md docs/new"
  assert_eq "should exit non-zero after mkdir docs/new && cp lands a hard-wrapped a.md in the repo" "2" "$AFTER_EXIT"
  assert_contains "should name a.md on stderr after mkdir docs/new && cp lands it" "a.md" "$AFTER_STDERR"
  assert_contains "should name the hard-wrap finding on stderr after mkdir docs/new && cp lands a.md" "hard-wrap" "$AFTER_STDERR"
}

# why: mv keeps a file's mtime, so only its ctime shows the
# move; b.md is written before the marker for that reason.
it_should_report_a_markdown_file_moved_in_inside_a_directory_the_same_command_created() {
  new_fixture
  printf '%s' "$HARD_WRAPPED_PROSE" > "$scratch_dir/b.md"
  run_command_with_hooks "$repo_dir" "mkdir $scratch_dir/d && mv $scratch_dir/b.md $scratch_dir/d/ && mv $scratch_dir/d docs/"
  assert_eq "should exit non-zero after a scratch directory made by the same command is moved into docs/ holding a hard-wrapped b.md" "2" "$AFTER_EXIT"
  assert_contains "should name b.md on stderr after its directory is moved into docs/" "b.md" "$AFTER_STDERR"
  assert_contains "should name the hard-wrap finding on stderr after b.md is moved into docs/" "hard-wrap" "$AFTER_STDERR"
}

it_should_report_a_markdown_file_written_from_a_heredoc() {
  new_fixture
  run_command_with_hooks "$repo_dir" "cat > docs/x.md <<'EOF'
${HARD_WRAPPED_PROSE}EOF"
  assert_eq "should exit non-zero after cat writes a hard-wrapped docs/x.md from a heredoc" "2" "$AFTER_EXIT"
  assert_contains "should name x.md on stderr after the heredoc writes it" "x.md" "$AFTER_STDERR"
  assert_contains "should name the hard-wrap finding on stderr after the heredoc writes x.md" "hard-wrap" "$AFTER_STDERR"
}

it_should_mark_every_bash_call_before_it_runs() {
  local commands
  commands=$(jq -r '.hooks.PreToolUse[] | select(.matcher == "Bash") | .hooks[].command' "$SETTINGS")
  assert_contains "should run the after-check's --mark step in the PreToolUse Bash hooks" "bash ~/.claude/hooks/claude-bash-prose-aftercheck.sh --mark" "$commands"
}

it_should_run_the_after_check_once_every_bash_call_succeeds() {
  local commands
  commands=$(jq -r '.hooks.PostToolUse[] | select(.matcher == "Bash") | .hooks[].command' "$SETTINGS")
  assert_eq "should run the after-check as the PostToolUse Bash hook" "bash ~/.claude/hooks/claude-bash-prose-aftercheck.sh" "$commands"
}

# why: a non-zero exit fires PostToolUseFailure instead of
# PostToolUse, so one trailing `false` must not hide a write.
it_should_report_a_markdown_file_written_by_a_command_that_then_exits_non_zero() {
  local id="toolu_01AfterCheckFailed"
  new_fixture
  run_marker "$repo_dir" "$id"
  (cd "$repo_dir" && "$bash_bin" -c "cp $scratch_dir/a.md docs/x.md; false") >/dev/null 2>&1
  AFTER_STDERR=$(
    cd "$repo_dir" || exit 1
    jq -n --arg id "$id" '{hook_event_name:"PostToolUseFailure",tool_name:"Bash",tool_input:{command:"cp a.md docs/x.md; false"},tool_use_id:$id,error:"Exit code 1",is_interrupt:false}' \
      | "$bash_bin" "$SCRIPT" 2>&1 >/dev/null
  )
  AFTER_EXIT=$?
  assert_eq "should exit non-zero when a failing command left a hard-wrapped docs/x.md behind" "2" "$AFTER_EXIT"
  assert_contains "should name x.md on stderr when a failing command left it behind" "x.md" "$AFTER_STDERR"
  assert_eq "should remove the call's marker after checking a failed command" "no" "$([ -e "$TMPDIR/claude-bash-prose-aftercheck/$id" ] && echo yes || echo no)"
}

it_should_run_the_after_check_once_every_bash_call_fails() {
  local commands
  commands=$(jq -r '.hooks.PostToolUseFailure[]? | select(.matcher == "Bash") | .hooks[].command' "$SETTINGS")
  assert_eq "should run the after-check as the PostToolUseFailure Bash hook" "bash ~/.claude/hooks/claude-bash-prose-aftercheck.sh" "$commands"
}

it_should_report_a_markdown_file_copied_into_a_directory_the_same_command_created
it_should_report_a_markdown_file_moved_in_inside_a_directory_the_same_command_created
it_should_report_a_markdown_file_written_from_a_heredoc
it_should_mark_every_bash_call_before_it_runs
it_should_run_the_after_check_once_every_bash_call_succeeds
it_should_report_a_markdown_file_written_by_a_command_that_then_exits_non_zero
it_should_run_the_after_check_once_every_bash_call_fails

# --- stays silent when nothing it should check changed ----

it_should_stay_silent_when_the_command_changes_no_work_tree_file() {
  new_fixture
  run_command_with_hooks "$repo_dir" "printf 'done\n' > $scratch_dir/out.txt"
  assert_eq "should exit 0 when the command writes only outside the work tree" "0" "$AFTER_EXIT"
  assert_eq "should print nothing when the command writes only outside the work tree" "" "$AFTER_STDERR"
}

it_should_stay_silent_about_a_dirty_file_the_command_did_not_touch() {
  new_fixture
  printf '%s' "$HARD_WRAPPED_PROSE" > "$repo_dir/docs/old.md"
  run_command_with_hooks "$repo_dir" "printf 'done\n' > $scratch_dir/out.txt"
  assert_eq "should exit 0 when a hard-wrapped untracked docs/old.md was already there before the command" "0" "$AFTER_EXIT"
  assert_eq "should print nothing about a hard-wrapped docs/old.md that was already there before the command" "" "$AFTER_STDERR"
}

it_should_stay_silent_when_no_marker_was_recorded_for_the_call() {
  new_fixture
  (cd "$repo_dir" && cp "$scratch_dir/a.md" docs/a.md)
  run_aftercheck "$repo_dir" "toolu_01NeverMarked"
  assert_eq "should exit 0 when the PreToolUse step left no marker for this tool_use_id" "0" "$AFTER_EXIT"
  assert_eq "should print nothing when the PreToolUse step left no marker for this tool_use_id" "" "$AFTER_STDERR"
}

it_should_stay_silent_when_the_cwd_is_not_a_git_work_tree() {
  local plain_dir
  plain_dir=$(mktemp -d "$TMPDIR/plain.XXXXXX")
  new_fixture
  run_command_with_hooks "$plain_dir" "cp $scratch_dir/a.md notes.md"
  assert_eq "should exit 0 when the cwd sits outside every git work tree" "0" "$AFTER_EXIT"
  assert_eq "should print nothing when the cwd sits outside every git work tree" "" "$AFTER_STDERR"
}

it_should_stay_silent_when_the_changed_file_is_git_ignored() {
  new_fixture
  run_command_with_hooks "$repo_dir" "cp $scratch_dir/a.md build/a.md"
  assert_eq "should exit 0 when the hard-wrapped file lands in the git-ignored build/" "0" "$AFTER_EXIT"
  assert_eq "should print nothing when the hard-wrapped file lands in the git-ignored build/" "" "$AFTER_STDERR"
}

it_should_stay_silent_when_the_command_changes_no_work_tree_file
it_should_stay_silent_about_a_dirty_file_the_command_did_not_touch
it_should_stay_silent_when_no_marker_was_recorded_for_the_call
it_should_stay_silent_when_the_cwd_is_not_a_git_work_tree
it_should_stay_silent_when_the_changed_file_is_git_ignored

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
