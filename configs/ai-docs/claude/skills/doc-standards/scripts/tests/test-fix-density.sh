#!/usr/bin/env bash
# test-fix-density.sh - plain-bash test file for fix-density.py.
#
# Usage:
#   bash test-fix-density.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design, matching this skill area's other test suites
# (test-check-rule-citations.sh, test-check-bullet-gap-fix.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/fix-density.py"
DENSITY_SCRIPT="$script_dir/check-density.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual,
# prints ok/not-ok.
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

# assert_contains - passes when the haystack carries the given literal row.
assert_contains() {
  local description="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  missing row: %s\n  actual:\n%s\n' "$description" "$needle" "$haystack"
  fi
}

# new_fixture - points FIXTURE at a fresh path under work_dir. Write its
# content right after calling this with `cat > "$FIXTURE" <<'EOF' ... EOF`
# (a heredoc straight into the file, not built through a `"$(cat <<EOF
# ...)"` string first) - bash's parser mis-tracks quote state across a
# heredoc body nested inside a command substitution once the body holds an
# apostrophe (e.g. "repository's"), misreading it as an unterminated
# single-quote and failing the whole script with a syntax error at parse
# time. Heredoc-straight-to-file sidesteps that entirely.
new_fixture() {
  FIXTURE="$work_dir/$1"
}

# run_fix - invokes fix-density.py on FIXTURE, capturing the exit code
# into FIX_EXIT and stdout+stderr into FIX_OUT.
run_fix() {
  python3 "$SCRIPT" "$FIXTURE" >"$work_dir/fix-stdout.txt" 2>&1
  FIX_EXIT=$?
  FIX_OUT=$(cat "$work_dir/fix-stdout.txt")
}

# run_density_check - independently re-verifies FIXTURE against
# check-density.sh directly (not through fix-density.py), so a passing
# fix is confirmed by the same tool an AI/human would run to check it,
# not just by re-reading fix-density.py's own opinion of itself.
run_density_check() {
  "$DENSITY_SCRIPT" "$FIXTURE" >"$work_dir/density-stdout.txt" 2>&1
  DENSITY_EXIT=$?
}

it_should_split_an_over_cap_line_at_a_sentence_boundary_with_both_halves_under_the_caps() {
  new_fixture ac4-sentence-boundary.md
  cat > "$FIXTURE" <<'EOF'
# AC4 fixture

This clause exists purely to push the line length well past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  run_fix
  assert_eq 'should split an over-cap line at a sentence boundary (exit code, fully resolved)' "0" "$FIX_EXIT"

  # Written to a file first, then read back into $expected - assigning
  # straight from `expected="$(cat <<'EOF' ...)"` hits the same nested
  # heredoc-in-command-substitution parser quirk new_fixture's comment
  # above describes, since this body also carries an apostrophe.
  local expected_file="$work_dir/ac4-expected.md"
  cat > "$expected_file" <<'EOF'
# AC4 fixture

This clause exists purely to push the line length well past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents.

This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF
  local expected
  expected="$(cat "$expected_file")"
  assert_eq 'should split an over-cap line at a sentence boundary (file content, the halves render as two separate paragraphs rather than one hard-wrapped one)' "$expected" "$(cat "$FIXTURE")"

  run_density_check
  assert_eq 'should split an over-cap line at a sentence boundary (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"
}

it_should_leave_an_over_cap_line_with_no_safe_boundary_untouched_and_exit_1_reporting_residue() {
  new_fixture ac5-no-boundary.md
  cat > "$FIXTURE" <<'EOF'
# AC5 fixture

This line deliberately avoids every recognized split boundary so the fixer has nowhere safe to break it and must leave it fully untouched while reporting it as residue instead of mutating anything inside it here
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave a no-safe-boundary line untouched (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should leave a no-safe-boundary line untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should leave a no-safe-boundary line untouched (residue row)' "$FIX_OUT" '3:211:35'
}

it_should_leave_a_fenced_code_block_untouched_even_with_an_over_cap_line_inside_it() {
  new_fixture ac6a-fenced-code.md
  cat > "$FIXTURE" <<'EOF'
# AC6a fixture

```bash
def process_all_the_records_in_the_batch_with_no_early_return_and_no_helper_extraction_anywhere_at_all(records, options, context, extra_flags): return [transform_record_completely_inline_without_any_named_intermediate_step(r, options, context) for r in records if r is not None]
```

Short trailing note.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave a fenced code block untouched (exit code)' "0" "$FIX_EXIT"
  assert_eq 'should leave a fenced code block untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
}

it_should_leave_a_mermaid_block_untouched_even_with_an_over_cap_line_inside_it() {
  new_fixture ac6b-mermaid.md
  cat > "$FIXTURE" <<'EOF'
# AC6b fixture

```mermaid
A --> B --> C --> D --> E --> F --> G --> H --> I --> J --> K --> L --> M --> N --> O --> P --> Q --> R --> S --> T --> U --> V --> W --> X --> Y --> Z
```

Short trailing note.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave a mermaid block untouched (exit code)' "0" "$FIX_EXIT"
  assert_eq 'should leave a mermaid block untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
}

it_should_leave_yaml_frontmatter_untouched_even_with_an_over_cap_description_scalar() {
  new_fixture ac7-frontmatter.md
  cat > "$FIXTURE" <<'EOF'
---
description: A very long router-facing description scalar that exists purely to exceed the density cap on purpose so the frontmatter skip logic inside check-density.sh has a genuine violation to actually skip over during this particular test run instead of trivially passing regardless of whether the skip logic works
---

Body prose stays short.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave YAML frontmatter untouched (exit code)' "0" "$FIX_EXIT"
  assert_eq 'should leave YAML frontmatter untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
}

it_should_make_no_further_changes_on_a_second_run_over_its_own_output() {
  new_fixture ac8-idempotent.md
  cat > "$FIXTURE" <<'EOF'
# AC8 fixture

This clause exists purely to push the line length well past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  run_fix
  local first_run_content
  first_run_content="$(cat "$FIXTURE")"
  local first_run_exit="$FIX_EXIT"

  run_fix
  assert_eq 'should make no further changes on a second run (exit code stays clean)' "$first_run_exit" "$FIX_EXIT"
  assert_eq 'should make no further changes on a second run (file content unchanged from the first run)' "$first_run_content" "$(cat "$FIXTURE")"
}

it_should_refuse_to_split_when_the_remainder_would_start_with_a_markdown_structural_token_and_report_residue() {
  new_fixture ac9-structural-token.md
  cat > "$FIXTURE" <<'EOF'
# AC9 fixture

Run the setup steps carefully before continuing on to the next stage of the deployment process today. - This looks exactly like the start of a bullet so the split must be rejected here
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should refuse a structural-token remainder (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should refuse a structural-token remainder (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should refuse a structural-token remainder (residue row)' "$FIX_OUT" '3:184:34'
}

it_should_repair_hits_at_many_line_numbers_in_one_invocation() {
  new_fixture ac10-many-hits.md
  cat > "$FIXTURE" <<'EOF'
# AC10 fixture

Alpha sentence exists purely to push alpha's line length well past the two hundred and fifty six character density cap enforced elsewhere in this fixture file. Alpha continuation clause finishes the alpha thought after the boundary point here.

Short filler paragraph one.

Beta sentence exists purely to push beta's line length well past the two hundred and fifty six character density cap enforced elsewhere in this fixture file. Beta continuation clause finishes the beta thought after the boundary point here.

Short filler paragraph two.

Gamma sentence exists purely to push gamma's line length well past the two hundred and fifty six character density cap enforced elsewhere in this fixture file. Gamma continuation clause finishes the gamma thought after the boundary point here.
EOF

  run_fix
  assert_eq 'should repair hits at many line numbers in one invocation (exit code, fully resolved)' "0" "$FIX_EXIT"

  # Written to a file first, then read back - see the comment on AC4's
  # expected_file above for why (apostrophes in "alpha's"/"beta's"/"gamma's").
  local expected_file="$work_dir/ac10-expected.md"
  cat > "$expected_file" <<'EOF'
# AC10 fixture

Alpha sentence exists purely to push alpha's line length well past the two hundred and fifty six character density cap enforced elsewhere in this fixture file.

Alpha continuation clause finishes the alpha thought after the boundary point here.

Short filler paragraph one.

Beta sentence exists purely to push beta's line length well past the two hundred and fifty six character density cap enforced elsewhere in this fixture file.

Beta continuation clause finishes the beta thought after the boundary point here.

Short filler paragraph two.

Gamma sentence exists purely to push gamma's line length well past the two hundred and fifty six character density cap enforced elsewhere in this fixture file.

Gamma continuation clause finishes the gamma thought after the boundary point here.
EOF
  local expected
  expected="$(cat "$expected_file")"
  assert_eq 'should repair hits at many line numbers in one invocation (all three lines split at their original positions)' "$expected" "$(cat "$FIXTURE")"

  run_density_check
  assert_eq 'should repair hits at many line numbers in one invocation (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"
}

it_should_leave_an_already_clean_file_unchanged_and_exit_0() {
  new_fixture ac11-clean.md
  cat > "$FIXTURE" <<'EOF'
# Clean fixture

Nothing in this short file is anywhere near the density caps.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave an already-clean file unchanged (exit code)' "0" "$FIX_EXIT"
  assert_eq 'should leave an already-clean file unchanged (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
}

it_should_exit_2_when_given_a_missing_file() {
  FIXTURE="$work_dir/does-not-exist.md"
  run_fix
  assert_eq 'should exit 2 when given a missing file' "2" "$FIX_EXIT"
}

it_should_exit_2_when_given_an_unknown_flag() {
  new_fixture unknown-flag.md
  printf '# ok\n' > "$FIXTURE"
  python3 "$SCRIPT" --nope "$FIXTURE" >"$work_dir/unknown-stdout.txt" 2>&1
  assert_eq 'should exit 2 when given an unknown flag' "2" "$?"
}

it_should_leave_an_over_cap_line_untouched_when_an_unclosed_bracket_precedes_the_only_boundary() {
  new_fixture ac12-unclosed-bracket.md
  cat > "$FIXTURE" <<'EOF'
# AC12 fixture

Check [the reference material without a closing bracket anywhere before the sentence boundary point right here. This continuation clause exists solely to push total length well past caps enforced elsewhere in this fixture for the test scenario at hand today truly indeed
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave an unclosed-bracket line untouched (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should leave an unclosed-bracket line untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should leave an unclosed-bracket line untouched (residue row)' "$FIX_OUT" '3:269:42'
}

it_should_leave_an_over_cap_line_untouched_when_its_only_boundary_sits_inside_a_code_span() {
  new_fixture ac13-code-span-boundary.md
  cat > "$FIXTURE" <<'EOF'
# AC13 fixture

Run the `first step of setup. Then continue with the configuration` before moving further along in this particularly long winded deployment procedure that keeps dragging on for quite some time here today certainly for sure absolutely without any doubt whatsoever really
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave a code-span-boundary line untouched (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should leave a code-span-boundary line untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should leave a code-span-boundary line untouched (residue row)' "$FIX_OUT" '3:269:41'
}

it_should_leave_an_over_cap_line_untouched_when_its_only_semicolon_boundary_sits_inside_parentheses() {
  new_fixture ac14-semicolon-in-parens.md
  cat > "$FIXTURE" <<'EOF'
# AC14 fixture

This bullet point wraps up nicely and cannot possibly reach the cap easily today (structurally this cannot ever reach zero completely; reports stay capped every run and simply never gate anything at all around here).
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should leave a semicolon-in-parens line untouched (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should leave a semicolon-in-parens line untouched (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should leave a semicolon-in-parens line untouched (residue row)' "$FIX_OUT" '3:216:35'
}

it_should_refuse_to_split_a_paragraph_whose_only_boundary_is_a_semicolon_and_report_it_as_residue() {
  new_fixture paragraph-semicolon-only.md
  cat > "$FIXTURE" <<'EOF'
# Semicolon-only paragraph fixture

This first independent clause exists purely to push the overall line length well past the two hundred fifty six character density cap enforced here today for sure absolutely; this second clause continues the thought cleanly right after the semicolon boundary point without any issue.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should refuse to split a paragraph whose only boundary is a semicolon (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should refuse to split a paragraph whose only boundary is a semicolon (file content byte-identical, no second paragraph opening mid-sentence)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should refuse to split a paragraph whose only boundary is a semicolon (residue row)' "$FIX_OUT" '3:283:44'
}

it_should_split_an_over_cap_bullet_at_a_semicolon_boundary_outside_any_brackets_and_stay_idempotent_on_a_second_run() {
  new_fixture bullet-semicolon-outside-brackets.md
  cat > "$FIXTURE" <<'EOF'
# Semicolon bullet fixture

- This first independent clause exists purely to push the overall line length well past the two hundred fifty six character density cap enforced here today for sure absolutely; this second clause continues the thought cleanly right after the semicolon boundary point.
EOF

  run_fix
  assert_eq 'should split a bullet at a semicolon boundary outside brackets (exit code, fully resolved)' "0" "$FIX_EXIT"

  local expected_file="$work_dir/bullet-semicolon-expected.md"
  cat > "$expected_file" <<'EOF'
# Semicolon bullet fixture

- This first independent clause exists purely to push the overall line length well past the two hundred fifty six character density cap enforced here today for sure absolutely;
  - this second clause continues the thought cleanly right after the semicolon boundary point.
EOF
  local expected
  expected="$(cat "$expected_file")"
  local first_run_content
  first_run_content="$(cat "$FIXTURE")"
  assert_eq 'should split a bullet at a semicolon boundary outside brackets (file content, the second half subordinated as a sub-bullet)' "$expected" "$first_run_content"

  run_density_check
  assert_eq 'should split a bullet at a semicolon boundary outside brackets (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"

  run_fix
  assert_eq 'should split a bullet at a semicolon boundary outside brackets (second run makes no further changes)' "$first_run_content" "$(cat "$FIXTURE")"
}

it_should_split_at_the_same_sentence_boundary_when_a_semicolon_also_appears_later_in_the_line() {
  new_fixture ac16-both-boundaries.md
  cat > "$FIXTURE" <<'EOF'
# AC16 fixture

This clause exists purely to push the line length well past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves; yes indeed for sure certainly absolutely today.
EOF

  run_fix
  assert_eq 'should split at the pre-existing sentence boundary despite a later semicolon (exit code, fully resolved)' "0" "$FIX_EXIT"

  # Written to a file first, then read back - see the comment on AC4's
  # expected_file above for why (apostrophe in "repository's").
  local expected_file="$work_dir/ac16-expected.md"
  cat > "$expected_file" <<'EOF'
# AC16 fixture

This clause exists purely to push the line length well past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents.

This second clause continues the thought after the boundary so the split can balance both halves; yes indeed for sure certainly absolutely today.
EOF
  local expected
  expected="$(cat "$expected_file")"
  assert_eq 'should split at the pre-existing sentence boundary despite a later semicolon (file content, same split point as before the semicolon boundary existed)' "$expected" "$(cat "$FIXTURE")"

  run_density_check
  assert_eq 'should split at the pre-existing sentence boundary despite a later semicolon (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"
}
it_should_split_an_over_cap_top_level_bullet_into_a_parent_bullet_and_an_indented_sub_bullet() {
  new_fixture bullet-top-level.md
  cat > "$FIXTURE" <<'EOF'
# Top-level bullet fixture

- This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  run_fix
  assert_eq 'should split a top-level bullet (exit code, fully resolved)' "0" "$FIX_EXIT"

  # Same heredoc-straight-to-file rule as new_fixture's comment: this
  # body carries an apostrophe, so it cannot be built through a nested
  # command substitution.
  local expected_file="$work_dir/bullet-top-level-expected.md"
  cat > "$expected_file" <<'EOF'
# Top-level bullet fixture

- This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents.
  - This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF
  local expected
  expected="$(cat "$expected_file")"
  assert_eq 'should split a top-level bullet (second half is a real sub-bullet, not a continuation line)' "$expected" "$(cat "$FIXTURE")"

  run_density_check
  assert_eq 'should split a top-level bullet (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"

  run_fix
  assert_eq 'should split a top-level bullet (second run makes no further changes)' "$expected" "$(cat "$FIXTURE")"
}

it_should_nest_a_split_sub_bullet_one_level_under_an_already_indented_parent_bullet() {
  new_fixture bullet-already-nested.md
  cat > "$FIXTURE" <<'EOF'
# Already-nested bullet fixture

  - This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  run_fix
  assert_eq 'should nest under an already-indented parent (exit code, fully resolved)' "0" "$FIX_EXIT"

  local expected_file="$work_dir/bullet-already-nested-expected.md"
  cat > "$expected_file" <<'EOF'
# Already-nested bullet fixture

  - This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents.
    - This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF
  local expected
  expected="$(cat "$expected_file")"
  assert_eq 'should nest under an already-indented parent (sub-bullet sits one level deeper, not at the top level)' "$expected" "$(cat "$FIXTURE")"

  run_density_check
  assert_eq 'should nest under an already-indented parent (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"
}

it_should_split_an_ordered_list_item_at_a_real_sentence_boundary_rather_than_at_its_own_marker() {
  new_fixture bullet-ordered-list.md
  cat > "$FIXTURE" <<'EOF'
# Ordered-list fixture

1. This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  run_fix
  assert_eq 'should split an ordered-list item (exit code, fully resolved)' "0" "$FIX_EXIT"

  local expected_file="$work_dir/bullet-ordered-list-expected.md"
  cat > "$expected_file" <<'EOF'
# Ordered-list fixture

1. This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents.
   - This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF
  local expected
  expected="$(cat "$expected_file")"
  assert_eq 'should split an ordered-list item (the item number keeps its own text instead of being stranded alone)' "$expected" "$(cat "$FIXTURE")"

  run_density_check
  assert_eq 'should split an ordered-list item (independently re-verified clean by check-density.sh)' "0" "$DENSITY_EXIT"
}

it_should_refuse_to_split_a_bullet_carrying_a_counting_marker_and_report_it_as_residue() {
  new_fixture bullet-counting-marker.md
  cat > "$FIXTURE" <<'EOF'
# Counting-marker bullet fixture

- [Instruction] This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should refuse to split a bullet carrying a counting marker (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should refuse to split a bullet carrying a counting marker (file content byte-identical, no unmarked sub-bullet invented)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should refuse to split a bullet carrying a counting marker (residue row)' "$FIX_OUT" '3:319:50'
}

it_should_refuse_to_split_a_bullet_whose_counting_marker_is_wrapped_in_bold_and_backticks() {
  new_fixture bullet-wrapped-counting-marker.md
  cat > "$FIXTURE" <<'EOF'
# Wrapped counting-marker bullet fixture

- **`[Instruction]`** This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should refuse to split a bold-and-backtick-wrapped counting marker (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should refuse to split a bold-and-backtick-wrapped counting marker (file content byte-identical)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should refuse to split a bold-and-backtick-wrapped counting marker (residue row)' "$FIX_OUT" '3:325:50'
}

it_should_refuse_to_split_a_blockquote_line_and_report_it_as_residue() {
  new_fixture blockquote.md
  cat > "$FIXTURE" <<'EOF'
# Blockquote fixture

> This clause exists to push the line length past the two hundred and fifty six character density cap that check-density.sh enforces on every prose line in this repository's markdown documents. This second clause continues the thought after the boundary so the split can balance both halves reasonably well.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should refuse to split a blockquote line (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should refuse to split a blockquote line (file content byte-identical, the quote never broken by an inserted blank line)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should refuse to split a blockquote line (residue row)' "$FIX_OUT" '3:307:49'
}

it_should_refuse_to_split_an_over_cap_heading_and_report_it_as_residue() {
  new_fixture heading.md
  cat > "$FIXTURE" <<'EOF'
# Heading fixture

### How the harness normalizes a non-deterministic captured value such as a duration. Every one of them passes through one single shared mask set before any comparison between the expected and actual output happens.

Body text.
EOF

  local before
  before="$(cat "$FIXTURE")"
  run_fix
  assert_eq 'should refuse to split an over-cap heading (exit code reports residue)' "1" "$FIX_EXIT"
  assert_eq 'should refuse to split an over-cap heading (file content byte-identical, the heading text never severed into body prose below it)' "$before" "$(cat "$FIXTURE")"
  assert_contains 'should refuse to split an over-cap heading (residue row)' "$FIX_OUT" '3:215:34'
}

it_should_split_an_over_cap_line_at_a_sentence_boundary_with_both_halves_under_the_caps
it_should_split_an_over_cap_top_level_bullet_into_a_parent_bullet_and_an_indented_sub_bullet
it_should_nest_a_split_sub_bullet_one_level_under_an_already_indented_parent_bullet
it_should_split_an_ordered_list_item_at_a_real_sentence_boundary_rather_than_at_its_own_marker
it_should_refuse_to_split_a_bullet_carrying_a_counting_marker_and_report_it_as_residue
it_should_refuse_to_split_a_bullet_whose_counting_marker_is_wrapped_in_bold_and_backticks
it_should_refuse_to_split_a_blockquote_line_and_report_it_as_residue
it_should_refuse_to_split_an_over_cap_heading_and_report_it_as_residue
it_should_leave_an_over_cap_line_with_no_safe_boundary_untouched_and_exit_1_reporting_residue
it_should_leave_a_fenced_code_block_untouched_even_with_an_over_cap_line_inside_it
it_should_leave_a_mermaid_block_untouched_even_with_an_over_cap_line_inside_it
it_should_leave_yaml_frontmatter_untouched_even_with_an_over_cap_description_scalar
it_should_make_no_further_changes_on_a_second_run_over_its_own_output
it_should_refuse_to_split_when_the_remainder_would_start_with_a_markdown_structural_token_and_report_residue
it_should_repair_hits_at_many_line_numbers_in_one_invocation
it_should_leave_an_already_clean_file_unchanged_and_exit_0
it_should_exit_2_when_given_a_missing_file
it_should_exit_2_when_given_an_unknown_flag
it_should_leave_an_over_cap_line_untouched_when_an_unclosed_bracket_precedes_the_only_boundary
it_should_leave_an_over_cap_line_untouched_when_its_only_boundary_sits_inside_a_code_span
it_should_leave_an_over_cap_line_untouched_when_its_only_semicolon_boundary_sits_inside_parentheses
it_should_refuse_to_split_a_paragraph_whose_only_boundary_is_a_semicolon_and_report_it_as_residue
it_should_split_an_over_cap_bullet_at_a_semicolon_boundary_outside_any_brackets_and_stay_idempotent_on_a_second_run
it_should_split_at_the_same_sentence_boundary_when_a_semicolon_also_appears_later_in_the_line

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
