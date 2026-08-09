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
  assert_eq 'should split an over-cap line at a sentence boundary (file content, both halves under the caps)' "$expected" "$(cat "$FIXTURE")"

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

it_should_split_an_over_cap_line_at_a_sentence_boundary_with_both_halves_under_the_caps
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

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
