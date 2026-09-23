#!/usr/bin/env bash
# test-check-density.sh - plain-bash test file for
# check-density.sh's pre-existing whole-file behavior and its
# new --changed-only flag.
#
# This script had zero test coverage before this file existed.
#
# Usage:
#   bash test-check-density.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching this skill area's other
# test suites (test-check-bullet-gap-fix.sh,
# test-get-changed-lines.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-density.sh"

# pwd -P resolves /var -> /private/var on macOS, matching
# test-get-changed-lines.sh's own reasoning:
# get-changed-lines.sh anchors on `git rev-parse
# --show-toplevel`, always returning physical paths.
work_dir=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

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
  local description="$1" needle="$2" haystack="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected to contain: %s\n  actual: %s\n' \
      "$description" "$needle" "$haystack"
  fi
}

# repeat_char - prints CHAR repeated COUNT times, no separator.
repeat_char() {
  local char="$1" count="$2"
  printf "${char}%.0s" $(seq 1 "$count")
}

# 600 chars, 1 word - trips only the prose char cap (512), never
# the prose word cap (64).
LONG_A_LINE=$(repeat_char a 600)
LONG_B_LINE=$(repeat_char b 600)
# 60 chars, 1 word - under both the prose (512/64) and bullet
# (256/32) default caps.
SIXTY_X_LINE=$(repeat_char x 60)
# 70 "word " units = 350 chars, 70 words - trips only the prose
# word cap (64), stays under the prose char cap (512).
LONG_WORDCOUNT_LINE=$(printf 'word %.0s' $(seq 1 70))
# 40 "abcdefgh " units = 360 chars, 40 words - between the
# bullet cap (256 chars/32 words) and the prose cap (512
# chars/64 words) on both dimensions at once: flags as a bullet,
# stays clean as prose.
BETWEEN_CAPS_LINE=$(printf 'abcdefgh %.0s' $(seq 1 40))
# 80 "abcdefgh " units = 720 chars, 80 words - over the prose
# cap (512 chars/64 words) on both dimensions at once.
OVER_PROSE_CAP_LINE=$(printf 'abcdefgh %.0s' $(seq 1 80))

# new_fixture - writes $2 into a fresh tmp file under a plain
# (non-git) directory, sets FIXTURE to its path.
# Used by the baseline whole-file tests, which never invoke
# get-changed-lines.sh so cwd/git state is irrelevant to them.
new_fixture() {
  local name="$1" content="$2"
  local dir="$work_dir/plain"
  mkdir -p "$dir"
  FIXTURE="$dir/$name"
  printf '%s' "$content" > "$FIXTURE"
}

# new_repo - creates an empty git repo under work_dir and prints
# its path.
#
# Identity is set locally so the fixture commit never depends on
# the machine's global git config, matching
# test-get-changed-lines.sh.
new_repo() {
  local dir="$work_dir/$1"
  mkdir -p "$dir"
  git -C "$dir" init -q .
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
  printf '%s' "$dir"
}

# run_check - invokes check-density.sh with the given extra args
# plus FIXTURE, capturing stdout+stderr into CHECK_OUT and the
# exit code into CHECK_EXIT.
#
# Runs in the ambient cwd (this repo) since these baseline cases
# never pass --changed-only.
run_check() {
  CHECK_OUT=$("$SCRIPT" "$@" "$FIXTURE" 2>&1)
  CHECK_EXIT=$?
}

# --- Baseline (no --changed-only): today's whole-file behavior
# ---

it_should_report_nothing_for_a_clean_file() {
  new_fixture clean.md "$(printf 'A short line.\nAnother short line.\n')"
  run_check
  assert_eq 'should report nothing for a clean file (stdout)' '' "$CHECK_OUT"
  assert_eq 'should report nothing for a clean file (exit code)' '0' "$CHECK_EXIT"
}

it_should_flag_a_line_over_the_char_cap() {
  new_fixture long-chars.md "$(printf '%s\n' "$LONG_A_LINE")"
  run_check
  assert_eq 'should flag a line over the char cap (stdout)' \
    "$(printf '== %s\n1:600:1' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag a line over the char cap (exit code)' '1' "$CHECK_EXIT"
}

it_should_flag_a_line_over_the_word_cap() {
  new_fixture long-words.md "$(printf '%s\n' "$LONG_WORDCOUNT_LINE")"
  run_check
  assert_eq 'should flag a line over the word cap (stdout)' \
    "$(printf '== %s\n1:350:70' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag a line over the word cap (exit code)' '1' "$CHECK_EXIT"
}

it_should_flag_a_line_only_once_max_chars_is_tightened_below_its_length() {
  new_fixture sixty-chars.md "$(printf '%s\n' "$SIXTY_X_LINE")"
  run_check
  assert_eq 'should stay clean under the default 512-char prose cap' '' "$CHECK_OUT"
  assert_eq 'should stay clean under the default 512-char prose cap (exit code)' \
    '0' "$CHECK_EXIT"

  run_check --max-chars 50
  assert_eq 'should flag it once --max-chars drops below its length (stdout)' \
    "$(printf '== %s\n1:60:1' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag it once --max-chars drops below its length (exit code)' \
    '1' "$CHECK_EXIT"
}

it_should_skip_yaml_frontmatter_content() {
  new_fixture frontmatter.md "$(printf -- '---\ndescription: %s\n---\nBody line.\n' "$LONG_A_LINE")"
  run_check
  assert_eq 'should skip yaml frontmatter content (stdout)' '' "$CHECK_OUT"
  assert_eq 'should skip yaml frontmatter content (exit code)' '0' "$CHECK_EXIT"
}

it_should_skip_fenced_code_block_content() {
  new_fixture fenced.md "$(printf 'Intro line.\n```\n%s\n```\n' "$LONG_A_LINE")"
  run_check
  assert_eq 'should skip fenced code block content (stdout)' '' "$CHECK_OUT"
  assert_eq 'should skip fenced code block content (exit code)' '0' "$CHECK_EXIT"
}

it_should_skip_table_rows() {
  new_fixture table.md "$(printf '| %s |\n' "$LONG_A_LINE")"
  run_check
  assert_eq 'should skip table rows (stdout)' '' "$CHECK_OUT"
  assert_eq 'should skip table rows (exit code)' '0' "$CHECK_EXIT"
}

it_should_print_a_header_and_blank_line_between_multiple_hit_files() {
  local dir="$work_dir/plain"
  mkdir -p "$dir"
  local fixture_a="$dir/multi-a.md" fixture_b="$dir/multi-b.md"
  printf '%s\n' "$LONG_A_LINE" > "$fixture_a"
  printf '%s\n' "$LONG_B_LINE" > "$fixture_b"

  local out
  out=$("$SCRIPT" "$fixture_a" "$fixture_b" 2>&1)
  local rc=$?

  assert_eq 'should print a header + blank-line separator across hit files (stdout)' \
    "$(printf '== %s\n1:600:1\n\n== %s\n1:600:1' "$fixture_a" "$fixture_b")" "$out"
  assert_eq 'should print a header + blank-line separator across hit files (exit code)' \
    '1' "$rc"
}

it_should_exit_2_when_no_files_given() {
  local out
  out=$("$SCRIPT" 2>&1)
  local rc=$?
  assert_eq 'should exit 2 when no files are given' '2' "$rc"
  assert_contains 'should exit 2 when no files are given (usage message)' 'usage:' "$out"
}

# --- Bullet vs prose caps: bullets/sub-bullets/ordered bullets
# stay at the tighter 256-char/32-word cap; everything else
# (prose) gets the looser 512-char/64-word cap.
#
# BETWEEN_CAPS_LINE (360 chars/40 words) sits strictly between
# the two, so it is the one fixture that tells them apart: it
# must flag when written as a bullet and stay clean when written
# as prose. ---

it_should_not_flag_a_prose_line_between_the_two_caps() {
  new_fixture between-caps-prose.md "$(printf '%s\n' "$BETWEEN_CAPS_LINE")"
  run_check
  assert_eq 'should not flag a prose line between the bullet and prose caps (stdout)' \
    '' "$CHECK_OUT"
  assert_eq 'should not flag a prose line between the bullet and prose caps (exit code)' \
    '0' "$CHECK_EXIT"
}

it_should_flag_a_bullet_line_between_the_two_caps() {
  new_fixture between-caps-bullet.md "$(printf -- '- %s\n' "$BETWEEN_CAPS_LINE")"
  run_check
  assert_eq 'should flag a plain bullet line between the two caps (stdout)' \
    "$(printf '== %s\n1:362:41' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag a plain bullet line between the two caps (exit code)' \
    '1' "$CHECK_EXIT"

  new_fixture between-caps-sub-bullet.md "$(printf -- '  - %s\n' "$BETWEEN_CAPS_LINE")"
  run_check
  assert_eq 'should flag an indented sub-bullet line between the two caps (stdout)' \
    "$(printf '== %s\n1:364:41' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag an indented sub-bullet line between the two caps (exit code)' \
    '1' "$CHECK_EXIT"

  new_fixture between-caps-ordered.md "$(printf -- '1. %s\n' "$BETWEEN_CAPS_LINE")"
  run_check
  assert_eq 'should flag an ordered bullet line between the two caps (stdout)' \
    "$(printf '== %s\n1:363:41' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag an ordered bullet line between the two caps (exit code)' \
    '1' "$CHECK_EXIT"
}

it_should_flag_a_prose_line_over_the_prose_cap() {
  new_fixture over-prose-cap.md "$(printf '%s\n' "$OVER_PROSE_CAP_LINE")"
  run_check
  assert_eq 'should flag a prose line over the prose cap (stdout)' \
    "$(printf '== %s\n1:720:80' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should flag a prose line over the prose cap (exit code)' \
    '1' "$CHECK_EXIT"
}

it_should_apply_bullet_and_prose_flags_independently() {
  # A bullet line: loosening the prose flags must not clear it
  # (bullet cap still governs); loosening the bullet flags must.
  new_fixture independent-bullet.md "$(printf -- '- %s\n' "$BETWEEN_CAPS_LINE")"
  run_check --max-chars 2000 --max-words 2000
  assert_eq 'should keep flagging a bullet line when only the prose flags are loosened (stdout)' \
    "$(printf '== %s\n1:362:41' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should keep flagging a bullet line when only the prose flags are loosened (exit code)' \
    '1' "$CHECK_EXIT"

  run_check --bullet-chars 2000 --bullet-words 2000
  assert_eq 'should clear a bullet line once the bullet flags are loosened (stdout)' \
    '' "$CHECK_OUT"
  assert_eq 'should clear a bullet line once the bullet flags are loosened (exit code)' \
    '0' "$CHECK_EXIT"

  # A prose line: loosening the bullet flags must not clear it
  # (prose cap still governs); loosening the prose flags must.
  new_fixture independent-prose.md "$(printf '%s\n' "$OVER_PROSE_CAP_LINE")"
  run_check --bullet-chars 2000 --bullet-words 2000
  assert_eq 'should keep flagging a prose line when only the bullet flags are loosened (stdout)' \
    "$(printf '== %s\n1:720:80' "$FIXTURE")" "$CHECK_OUT"
  assert_eq 'should keep flagging a prose line when only the bullet flags are loosened (exit code)' \
    '1' "$CHECK_EXIT"

  run_check --max-chars 2000 --max-words 2000
  assert_eq 'should clear a prose line once the prose flags are loosened (stdout)' \
    '' "$CHECK_OUT"
  assert_eq 'should clear a prose line once the prose flags are loosened (exit code)' \
    '0' "$CHECK_EXIT"
}

# --- --changed-only: scope violations to lines changed vs git
# HEAD ---

it_should_report_every_line_as_changed_for_an_untracked_file() {
  local repo
  repo=$(new_repo repo-untracked)
  printf '%s\n' "$LONG_A_LINE" > "$repo/new.md"

  local out
  out=$(cd "$repo" && "$SCRIPT" --changed-only new.md 2>&1)
  local rc=$?

  assert_eq 'should report every line as changed for an untracked file (stdout)' \
    "$(printf '== new.md\n1:600:1')" "$out"
  assert_eq 'should report every line as changed for an untracked file (exit code)' \
    '1' "$rc"
}

it_should_hide_pre_existing_violations_outside_changed_lines() {
  local repo
  repo=$(new_repo repo-modified)
  printf '%s\nok\n' "$LONG_A_LINE" > "$repo/mod.md"
  git -C "$repo" add mod.md
  git -C "$repo" commit -q -m base
  printf '%s\nok\n%s\n' "$LONG_A_LINE" "$LONG_B_LINE" > "$repo/mod.md"

  local baseline
  baseline=$(cd "$repo" && "$SCRIPT" mod.md 2>&1)
  assert_eq 'should still report both violations without the flag (baseline)' \
    "$(printf '== mod.md\n1:600:1\n3:600:1')" "$baseline"

  local scoped rc
  scoped=$(cd "$repo" && "$SCRIPT" --changed-only mod.md 2>&1)
  rc=$?
  assert_eq 'should hide the pre-existing violation and report only the added one (stdout)' \
    "$(printf '== mod.md\n3:600:1')" "$scoped"
  assert_eq 'should hide the pre-existing violation and report only the added one (exit code)' \
    '1' "$rc"
}

it_should_report_nothing_for_an_unmodified_tracked_file() {
  local repo
  repo=$(new_repo repo-unmodified)
  printf '%s\n' "$LONG_A_LINE" > "$repo/base.md"
  git -C "$repo" add base.md
  git -C "$repo" commit -q -m base

  local baseline
  baseline=$(cd "$repo" && "$SCRIPT" base.md 2>&1)
  assert_eq 'should still report the violation without the flag (baseline)' \
    "$(printf '== base.md\n1:600:1')" "$baseline"

  local scoped rc
  scoped=$(cd "$repo" && "$SCRIPT" --changed-only base.md 2>&1)
  rc=$?
  assert_eq 'should report nothing for an unmodified tracked file (stdout)' '' "$scoped"
  assert_eq 'should report nothing for an unmodified tracked file (exit code)' '0' "$rc"
}

it_should_exit_2_and_name_the_file_when_outside_a_git_work_tree() {
  local dir="$work_dir/no-repo-tree"
  mkdir -p "$dir"
  printf '%s\n' "$LONG_A_LINE" > "$dir/only.md"

  local out rc
  out=$(cd "$dir" && "$SCRIPT" --changed-only only.md 2>&1)
  rc=$?
  assert_eq 'should exit 2 when the file sits outside a git work tree' '2' "$rc"
  assert_contains 'should name the file in the exit-2 stderr message' \
    'check-density.sh: cannot scope only.md:' "$out"
}

it_should_scope_multiple_files_independently() {
  local repo
  repo=$(new_repo repo-multi)
  printf 'ok\n' > "$repo/a.md"
  printf '%s\n' "$LONG_B_LINE" > "$repo/b.md"
  git -C "$repo" add a.md b.md
  git -C "$repo" commit -q -m base
  printf 'ok\n%s\n' "$LONG_A_LINE" > "$repo/a.md"

  local out rc
  out=$(cd "$repo" && "$SCRIPT" --changed-only a.md b.md 2>&1)
  rc=$?
  assert_eq 'should scope multiple files independently (stdout)' \
    "$(printf '== a.md\n2:600:1')" "$out"
  assert_eq 'should scope multiple files independently (exit code)' '1' "$rc"
}

it_should_recompute_scope_fresh_on_each_invocation() {
  local repo
  repo=$(new_repo repo-fresh)
  printf 'ok\n' > "$repo/fresh.md"
  git -C "$repo" add fresh.md
  git -C "$repo" commit -q -m base

  local first_out first_rc
  first_out=$(cd "$repo" && "$SCRIPT" --changed-only fresh.md 2>&1)
  first_rc=$?
  assert_eq 'should report nothing before any modification (stdout)' '' "$first_out"
  assert_eq 'should report nothing before any modification (exit code)' '0' "$first_rc"

  printf 'ok\n%s\n' "$LONG_A_LINE" > "$repo/fresh.md"
  local second_out second_rc
  second_out=$(cd "$repo" && "$SCRIPT" --changed-only fresh.md 2>&1)
  second_rc=$?
  assert_eq 'should pick up the new violation on the very next invocation (stdout)' \
    "$(printf '== fresh.md\n2:600:1')" "$second_out"
  assert_eq 'should pick up the new violation on the very next invocation (exit code)' \
    '1' "$second_rc"
}

it_should_report_nothing_for_a_clean_file
it_should_flag_a_line_over_the_char_cap
it_should_flag_a_line_over_the_word_cap
it_should_flag_a_line_only_once_max_chars_is_tightened_below_its_length
it_should_skip_yaml_frontmatter_content
it_should_skip_fenced_code_block_content
it_should_skip_table_rows
it_should_print_a_header_and_blank_line_between_multiple_hit_files
it_should_exit_2_when_no_files_given
it_should_not_flag_a_prose_line_between_the_two_caps
it_should_flag_a_bullet_line_between_the_two_caps
it_should_flag_a_prose_line_over_the_prose_cap
it_should_apply_bullet_and_prose_flags_independently
it_should_report_every_line_as_changed_for_an_untracked_file
it_should_hide_pre_existing_violations_outside_changed_lines
it_should_report_nothing_for_an_unmodified_tracked_file
it_should_exit_2_and_name_the_file_when_outside_a_git_work_tree
it_should_scope_multiple_files_independently
it_should_recompute_scope_fresh_on_each_invocation

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
