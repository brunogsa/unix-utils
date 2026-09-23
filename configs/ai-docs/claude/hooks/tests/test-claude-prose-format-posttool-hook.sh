#!/usr/bin/env bash
# Plain-bash test file for
# claude-prose-format-posttool-hook.sh.
#
# Usage:
#   bash test-claude-prose-format-posttool-hook.sh
#
# Exits 0 when every assertion passes, non-zero
# otherwise. No bats dependency by design - the sibling
# hook tests set that precedent.
#
# Each fixture gets its own scratch git repo under
# TMPDIR, so --changed-only always sees the fixture's
# whole content as changed (untracked, or staged but
# never committed).
#
# This never touches this repo's own history.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/claude-prose-format-posttool-hook.sh"

pass_count=0
fail_count=0

TMPDIR=$(mktemp -d)
export TMPDIR
trap 'rm -rf "$TMPDIR"' EXIT

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

# assert_contains - passes when actual contains needle.
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

# assert_not_contains - passes when actual does NOT
# contain needle.
assert_not_contains() {
  local description="$1" needle="$2" actual="$3"
  if [[ "$actual" != *"$needle"* ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected NOT to contain: %s\n  actual:   %s\n' "$description" "$needle" "$actual"
  fi
}

# assert_no_line_number_row - passes when actual contains
# no printed line-number row.
#
# Anchored to the hook's real row shape (two leading
# spaces, a label, whitespace, then "L<digits>") rather than
# a naked `L[0-9]` substring search.
#
# A fixture's own tmp path can itself contain "L" followed
# by a digit (mktemp's random suffix, or a printed pointer
# command that carries that path), which a naked substring
# search misreads as a row.
assert_no_line_number_row() {
  local description="$1" actual="$2"
  if printf '%s\n' "$actual" | grep -qE '^  [A-Za-z-]+[[:space:]]+L[0-9]'; then
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  actual:   %s\n' "$description" "$actual"
  else
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  fi
}

# assert_line_number_row_matches - passes when actual
# contains a real line-number row (same anchored shape as
# assert_no_line_number_row) whose value column carries the
# given "L<n>" token as a whole token.
#
# Never a substring match against the fixture's own tmp
# path, which the header line also prints.
assert_line_number_row_matches() {
  local description="$1" token="$2" actual="$3"
  if printf '%s\n' "$actual" | grep -qE "^  [A-Za-z-]+[[:space:]]+${token}([^0-9]|\$)"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected row containing: %s\n  actual:   %s\n' "$description" "$token" "$actual"
  fi
}

# new_repo_fixture - creates a fresh scratch git repo
# under TMPDIR and echoes its path.
new_repo_fixture() {
  local dir
  dir=$(mktemp -d)
  git init -q "$dir"

  # A committer identity is needed for later commands in
  # this repo, even though these fixtures never commit -
  # git init alone is enough for get-changed-lines.sh's
  # "is this a work tree" check.
  printf '%s' "$dir"
}

# run_hook - invokes the hook with the given tool_name
# and file_path, wrapped into the PostToolUse JSON
# shape. Captures exit code into HOOK_EXIT and combined
# stdout+stderr into HOOK_OUT.
run_hook() {
  local tool_name="$1" file_path="$2" stdin_json
  stdin_json=$(jq -n --arg t "$tool_name" --arg f "$file_path" \
    '{tool_name: $t, tool_input: {file_path: $f}}')
  HOOK_OUT=$(printf '%s' "$stdin_json" | "$bash_bin" "$SCRIPT" 2>&1)
  HOOK_EXIT=$?
}

it_should_stay_silent_on_a_clean_markdown_write() {
  local dir
  dir=$(new_repo_fixture)
  cat > "$dir/clean.md" << 'EOF'
Small clean paragraph.

Another small one.
EOF
  run_hook "Write" "$dir/clean.md"
  assert_eq "should exit 0 on a clean markdown write" "0" "$HOOK_EXIT"
  assert_eq "should print nothing on a clean markdown write" "" "$HOOK_OUT"
}

it_should_report_a_wall_of_text_markdown_write() {
  local dir long_line
  dir=$(new_repo_fixture)
  long_line=$(python3 -c "print('word ' * 120)")
  {
    printf '%s\n\n' "$long_line"
    printf '%s\n\n' "$long_line"
    printf '%s\n\n' "$long_line"
  } > "$dir/wall.md"
  run_hook "Write" "$dir/wall.md"
  assert_eq "should exit 2 on a wall-of-text markdown write" "2" "$HOOK_EXIT"
  assert_contains "should name the file in the report" "wall.md" "$HOOK_OUT"
  assert_contains "should report the right violation count" "3 violations" "$HOOK_OUT"

  # The checker's own "== <path>" header line is never a
  # violation - a prior session miscounted by including
  # it, so this pins the count against that regression.
  assert_not_contains "should never count the checker's own header line" "== " "$HOOK_OUT"
}

it_should_use_the_counts_regime_over_the_threshold() {
  local dir long_line i
  dir=$(new_repo_fixture)
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$dir/big.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/big.md"
  done
  run_hook "Write" "$dir/big.md"
  assert_eq "should exit 2 over the threshold" "2" "$HOOK_EXIT"
  assert_contains "should report 15 violations" "15 violations" "$HOOK_OUT"

  # Counts regime: no line-number rows, but does list the
  # checker's own script pointer command.
  assert_no_line_number_row \
    "should not print any L<digits> line-number row over threshold" \
    "$HOOK_OUT"

  # The pointer command must resolve when run as printed, so it
  # carries the real file_path (defect 1), never the bare
  # basename the header shows.
  assert_contains "should list the checker's own script pointer over threshold" \
    "check-density.sh   --changed-only $dir/big.md" "$HOOK_OUT"
}

it_should_not_flake_when_the_fixture_path_contains_l_digit_over_threshold() {
  # Regression: a prior run hit a fixture dir whose mktemp
  # random suffix happened to contain "L2" (e.g.
  # .../tmp.R5L2gMWnKC/big.md).
  #
  # The naked `L[0-9]` substring check below misread that
  # path fragment as a printed line-number row.
  #
  # This test forces the same collision deterministically -
  # via a fixed "L2" in the dir name, not mktemp's luck - so
  # the flaw reproduces on every run instead of only
  # sometimes.
  local dir long_line i
  dir=$(mktemp -d "$TMPDIR/tmpL2XXXXXX")
  git init -q "$dir"
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$dir/big.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/big.md"
  done
  run_hook "Write" "$dir/big.md"
  assert_eq "should exit 2 over the threshold with an L-digit-bearing fixture path" "2" "$HOOK_EXIT"

  assert_no_line_number_row \
    "should not print any L<digits> line-number row over threshold, even when the fixture path itself contains \"L<digit>\"" \
    "$HOOK_OUT"
}

it_should_use_the_line_number_regime_under_the_threshold() {
  local dir long_line
  dir=$(new_repo_fixture)
  long_line=$(python3 -c "print('word ' * 120)")
  printf '%s\n' "$long_line" > "$dir/small.md"
  run_hook "Write" "$dir/small.md"
  assert_eq "should exit 2 under the threshold" "2" "$HOOK_EXIT"
  assert_line_number_row_matches "should print the violated line number" "L1" "$HOOK_OUT"
  assert_not_contains "should not list a script pointer under threshold" \
    "doc-standards/scripts/check-density.sh" "$HOOK_OUT"
}

it_should_route_a_shell_file_to_the_comment_checker() {
  local dir
  dir=$(new_repo_fixture)
  {
    printf '#!/bin/bash\n'
    printf '# %s\n' "$(python3 -c "print('word ' * 30)")"
    printf 'echo hi\n'
  } > "$dir/wide.sh"
  run_hook "Write" "$dir/wide.sh"
  assert_eq "should exit 2 on an over-wide shell comment" "2" "$HOOK_EXIT"
  assert_contains "should report the comment-format finding" "width" "$HOOK_OUT"
  assert_not_contains "should not run the density checker on a shell file" "density" "$HOOK_OUT"

  # "hard-wrap" also appears inside the rule block's own prose
  # ("never hard-wrap"), so the label row is what's asserted
  # against, not the bare substring.
  assert_not_contains "should not run the hard-wrap checker on a shell file" "  hard-wrap " "$HOOK_OUT"
}

it_should_stay_silent_on_an_unknown_extension() {
  local dir
  dir=$(new_repo_fixture)
  printf '{"a": 1}' > "$dir/data.json"
  run_hook "Write" "$dir/data.json"
  assert_eq "should exit 0 on an unknown extension" "0" "$HOOK_EXIT"
  assert_eq "should print nothing on an unknown extension" "" "$HOOK_OUT"
}

it_should_fail_open_outside_a_git_repo() {
  local dir long_line
  dir=$(mktemp -d)
  long_line=$(python3 -c "print('word ' * 120)")
  printf '%s\n' "$long_line" > "$dir/wall.md"
  run_hook "Write" "$dir/wall.md"
  assert_eq "should exit 0 outside a git work tree" "0" "$HOOK_EXIT"
  assert_eq "should print nothing outside a git work tree" "" "$HOOK_OUT"
}

it_should_fail_open_on_a_missing_file() {
  run_hook "Write" "$TMPDIR/does-not-exist-xyz.md"
  assert_eq "should exit 0 on a missing file" "0" "$HOOK_EXIT"
  assert_eq "should print nothing on a missing file" "" "$HOOK_OUT"
}

it_should_fail_open_on_a_non_write_edit_payload() {
  local dir
  dir=$(new_repo_fixture)
  cat > "$dir/clean.md" << 'EOF'
Small clean paragraph.
EOF
  run_hook "Read" "$dir/clean.md"
  assert_eq "should exit 0 on a Read payload" "0" "$HOOK_EXIT"
  assert_eq "should print nothing on a Read payload" "" "$HOOK_OUT"
}

it_should_carry_the_rule_block_verbatim_in_every_report() {
  local dir long_line rule1 rule2 rule3
  rule1='Prose: small paragraphs of 1-4 sentences, blank line between each.'
  rule2='Bullets + sub-bullets: 1-2 sentences each.'
  rule3='One paragraph = one physical line — never hard-wrap. Never drop information.'

  dir=$(new_repo_fixture)
  long_line=$(python3 -c "print('word ' * 120)")
  printf '%s\n' "$long_line" > "$dir/small.md"
  run_hook "Write" "$dir/small.md"
  assert_contains "under-threshold report should carry rule line 1 verbatim" "$rule1" "$HOOK_OUT"
  assert_contains "under-threshold report should carry rule line 2 verbatim" "$rule2" "$HOOK_OUT"
  assert_contains "under-threshold report should carry rule line 3 verbatim" "$rule3" "$HOOK_OUT"

  dir=$(new_repo_fixture)
  : > "$dir/big.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/big.md"
  done
  run_hook "Write" "$dir/big.md"
  assert_contains "over-threshold report should carry rule line 1 verbatim" "$rule1" "$HOOK_OUT"
  assert_contains "over-threshold report should carry rule line 2 verbatim" "$rule2" "$HOOK_OUT"
  assert_contains "over-threshold report should carry rule line 3 verbatim" "$rule3" "$HOOK_OUT"
}

it_should_run_the_printed_pointer_command_for_a_nested_file() {
  local dir long_line pointer_line
  dir=$(new_repo_fixture)
  mkdir -p "$dir/subdir"
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$dir/subdir/big.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/subdir/big.md"
  done
  run_hook "Write" "$dir/subdir/big.md"
  assert_eq "should exit 2 over the threshold on a nested file" "2" "$HOOK_EXIT"

  pointer_line=$(printf '%s\n' "$HOOK_OUT" | grep 'check-density.sh' | head -1)
  if [ -z "$pointer_line" ]; then
    fail_count=$((fail_count + 1))
    printf 'not ok - should print a check-density.sh pointer line\n  actual:   %s\n' "$HOOK_OUT"
    return
  fi
  pass_count=$((pass_count + 1))
  printf 'ok - should print a check-density.sh pointer line\n'

  # Strip the two leading spaces the report indents pointer
  # lines with, then run it verbatim as printed.
  local cmd
  cmd=$(printf '%s' "$pointer_line" | sed -e 's/^[[:space:]]*//')
  eval "$cmd" > /dev/null 2>&1
  local pointer_rc=$?
  if [ "$pointer_rc" -eq 0 ] || [ "$pointer_rc" -eq 1 ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - printed pointer command should resolve the nested file (exit %s)\n' "$pointer_rc"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - printed pointer command should resolve the nested file\n  command:  %s\n  exit:     %s\n' "$cmd" "$pointer_rc"
  fi
}

it_should_keep_the_basename_in_the_header_for_a_nested_file() {
  local dir long_line
  dir=$(new_repo_fixture)
  mkdir -p "$dir/subdir"
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$dir/subdir/big.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/subdir/big.md"
  done
  run_hook "Write" "$dir/subdir/big.md"
  assert_contains "header should show the basename for a nested file" "prose-format: big.md" "$HOOK_OUT"
  assert_not_contains "header should not show the full nested path" "subdir/big.md —" "$HOOK_OUT"
}

it_should_align_the_flag_column_across_printed_commands() {
  local dir long_bullet
  dir=$(new_repo_fixture)
  : > "$dir/mixed.md"

  # Bullets over the bullet density cap (256c/32w) AND spanning
  # multiple physical lines - trips both check-density.sh (16
  # chars) and check-hard-wrap.py (19 chars).
  #
  # Two different-length script names, over the 10-violation
  # threshold.
  long_bullet=$(python3 -c "print('- ' + 'word ' * 40)")
  for ((i = 0; i < 12; i++)); do
    printf '%s\n' "$long_bullet" >> "$dir/mixed.md"
    printf 'continuation line %s\n\n' "$i" >> "$dir/mixed.md"
  done
  run_hook "Write" "$dir/mixed.md"
  assert_eq "should exit 2 over the threshold on the mixed fixture" "2" "$HOOK_EXIT"

  local columns
  columns=$(printf '%s\n' "$HOOK_OUT" | grep -- '--changed-only' | sed -n 's/.*\(--changed-only\).*/\1/p' | wc -l)
  local first_col
  first_col=$(printf '%s\n' "$HOOK_OUT" | grep -- '--changed-only' | head -1 | awk '{print index($0, "--changed-only")}')
  local all_match=1
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    local col
    col=$(printf '%s' "$line" | awk '{print index($0, "--changed-only")}')
    [ "$col" = "$first_col" ] || all_match=0
  done < <(printf '%s\n' "$HOOK_OUT" | grep -- '--changed-only')

  if [ "$columns" -ge 2 ] && [ "$all_match" -eq 1 ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - --changed-only should start at the same column on every printed command\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - --changed-only should start at the same column on every printed command\n  actual:   %s\n' "$HOOK_OUT"
  fi
}

it_should_carry_density_char_word_counts_under_the_threshold() {
  local dir long_line
  dir=$(new_repo_fixture)
  long_line=$(python3 -c "print('word ' * 120)")
  {
    printf '%s\n\n' "$long_line"
    printf '%s\n' "$long_line"
  } > "$dir/small.md"
  run_hook "Write" "$dir/small.md"
  assert_eq "should exit 2 under the threshold" "2" "$HOOK_EXIT"
  assert_contains "density row should carry chars/words for line 1" "L1 " "$HOOK_OUT"

  local density_row
  density_row=$(printf '%s\n' "$HOOK_OUT" | grep '^  density')
  if [[ "$density_row" =~ [0-9]+c/[0-9]+w.*,.*[0-9]+c/[0-9]+w ]]; then
    pass_count=$((pass_count + 1))
    printf 'ok - density row should carry a c/w detail per line, not just the first\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - density row should carry a c/w detail per line, not just the first\n  actual:   %s\n' "$density_row"
  fi
}

it_should_keep_hard_wrap_rows_bare_under_the_threshold() {
  local dir
  dir=$(new_repo_fixture)
  {
    printf 'One sentence here.\nAnd a second physical line\nfor the same paragraph.\n'
  } > "$dir/hardwrap.md"
  run_hook "Write" "$dir/hardwrap.md"
  local hardwrap_row
  hardwrap_row=$(printf '%s\n' "$HOOK_OUT" | grep '^  hard-wrap')
  if [[ "$hardwrap_row" =~ c/[0-9]+w ]]; then
    fail_count=$((fail_count + 1))
    printf 'not ok - hard-wrap row should stay bare (no c/w detail)\n  actual:   %s\n' "$hardwrap_row"
  else
    pass_count=$((pass_count + 1))
    printf 'ok - hard-wrap row should stay bare (no c/w detail)\n'
  fi
}

it_should_run_correctly_when_the_path_has_a_space() {
  local dir subdir long_line pointer_line cmd rc
  dir=$(new_repo_fixture)
  subdir="$dir/probe dir"
  mkdir -p "$subdir"
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$subdir/wall.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$subdir/wall.md"
  done
  run_hook "Write" "$subdir/wall.md"
  assert_eq "should exit 2 over the threshold with a space in the path" "2" "$HOOK_EXIT"

  pointer_line=$(printf '%s\n' "$HOOK_OUT" | grep 'check-density.sh' | head -1)
  if [ -z "$pointer_line" ]; then
    fail_count=$((fail_count + 1))
    printf 'not ok - should print a check-density.sh pointer line for a spaced path\n  actual:   %s\n' "$HOOK_OUT"
    return
  fi
  pass_count=$((pass_count + 1))
  printf 'ok - should print a check-density.sh pointer line for a spaced path\n'

  cmd=$(printf '%s' "$pointer_line" | sed -e 's/^[[:space:]]*//')
  eval "$cmd" > /dev/null 2>&1
  rc=$?
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - printed command for a spaced path runs and exits 0 or 1, never 2\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - printed command for a spaced path runs and exits 0 or 1, never 2\n  actual exit: %s\n' "$rc"
  fi
}

it_should_produce_an_inert_command_for_a_shell_metacharacter_path() {
  local dir long_line injected_name sentinel pointer_line cmd rc
  dir=$(new_repo_fixture)
  sentinel="$dir/PWNED-marker.md"
  injected_name='wall; touch PWNED-marker.md #.md'
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$dir/$injected_name"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/$injected_name"
  done
  run_hook "Write" "$dir/$injected_name"
  assert_eq "should exit 2 over the threshold with an injected-command filename" "2" "$HOOK_EXIT"

  pointer_line=$(printf '%s\n' "$HOOK_OUT" | grep 'check-density.sh' | head -1)
  if [ -z "$pointer_line" ]; then
    fail_count=$((fail_count + 1))
    printf 'not ok - should print a check-density.sh pointer line for an injected-command filename\n  actual:   %s\n' "$HOOK_OUT"
    return
  fi
  pass_count=$((pass_count + 1))
  printf 'ok - should print a check-density.sh pointer line for an injected-command filename\n'

  cmd=$(printf '%s' "$pointer_line" | sed -e 's/^[[:space:]]*//')
  ( cd "$dir" && eval "$cmd" > /dev/null 2>&1 )
  rc=$?
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - printed command for an injected-command filename runs and exits 0 or 1, never 2\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - printed command for an injected-command filename runs and exits 0 or 1, never 2\n  actual exit: %s\n' "$rc"
  fi

  if [ -f "$sentinel" ]; then
    fail_count=$((fail_count + 1))
    printf 'not ok - printed command must never execute the injected touch\n'
    rm -f "$sentinel"
  else
    pass_count=$((pass_count + 1))
    printf 'ok - printed command must never execute the injected touch\n'
  fi
}

it_should_treat_a_leading_dash_filename_as_a_path_not_a_flag() {
  # tool_input.file_path is the raw argument every downstream
  # tool sees, so the leading-dash risk is real only when that
  # value itself starts with "-" - a relative path with no
  # directory component.

  # cd into the fixture repo so both the hook's own file check
  # and the checker's --changed-only git lookup resolve it
  # there.

  # get-changed-lines.sh (a shared dependency every
  # --changed-only checker calls) used to crash on a bare
  # leading-dash name via a dirname/basename option-parsing bug,
  # forcing this hook to fail open with no signal.

  # Now fixed, so the checker runs for real and this test pins
  # the same exit-2/pointer-line/no-rewrite contract the
  # spaced-path and injected-command cases already pin.
  local dir long_line before after orig_pwd pointer_line cmd rc
  dir=$(new_repo_fixture)
  long_line=$(python3 -c "print('word ' * 120)")
  : > "$dir/-danger.md"
  for ((i = 0; i < 15; i++)); do
    printf '%s\n\n' "$long_line" >> "$dir/-danger.md"
  done
  before=$(cat "$dir/-danger.md")
  orig_pwd=$(pwd)
  cd "$dir" || return
  run_hook "Write" "-danger.md"
  cd "$orig_pwd" || return
  assert_eq "should exit 2 over the threshold with a leading-dash filename" "2" "$HOOK_EXIT"

  pointer_line=$(printf '%s\n' "$HOOK_OUT" | grep 'check-density.sh' | head -1)
  if [ -z "$pointer_line" ]; then
    fail_count=$((fail_count + 1))
    printf 'not ok - should print a check-density.sh pointer line for a leading-dash filename\n  actual:   %s\n' "$HOOK_OUT"
    return
  fi
  pass_count=$((pass_count + 1))
  printf 'ok - should print a check-density.sh pointer line for a leading-dash filename\n'

  cmd=$(printf '%s' "$pointer_line" | sed -e 's/^[[:space:]]*//')
  ( cd "$dir" && eval "$cmd" > /dev/null 2>&1 )
  rc=$?
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 1 ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - printed command for a leading-dash filename runs and exits 0 or 1, never 2\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - printed command for a leading-dash filename runs and exits 0 or 1, never 2\n  actual exit: %s\n' "$rc"
  fi

  after=$(cat "$dir/-danger.md")
  assert_eq "the checker must never rewrite the file while checking its leading-dash name" "$before" "$after"
}

it_should_stay_silent_on_a_clean_markdown_write
it_should_report_a_wall_of_text_markdown_write
it_should_use_the_counts_regime_over_the_threshold
it_should_not_flake_when_the_fixture_path_contains_l_digit_over_threshold
it_should_use_the_line_number_regime_under_the_threshold
it_should_route_a_shell_file_to_the_comment_checker
it_should_stay_silent_on_an_unknown_extension
it_should_fail_open_outside_a_git_repo
it_should_fail_open_on_a_missing_file
it_should_fail_open_on_a_non_write_edit_payload
it_should_carry_the_rule_block_verbatim_in_every_report
it_should_run_the_printed_pointer_command_for_a_nested_file
it_should_keep_the_basename_in_the_header_for_a_nested_file
it_should_align_the_flag_column_across_printed_commands
it_should_carry_density_char_word_counts_under_the_threshold
it_should_keep_hard_wrap_rows_bare_under_the_threshold
it_should_run_correctly_when_the_path_has_a_space
it_should_produce_an_inert_command_for_a_shell_metacharacter_path
it_should_treat_a_leading_dash_filename_as_a_path_not_a_flag

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
