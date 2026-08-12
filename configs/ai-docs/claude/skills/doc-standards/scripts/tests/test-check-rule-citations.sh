#!/usr/bin/env bash
# test-check-rule-citations.sh - plain-bash test file for
# check-rule-citations.py.
#
# Usage:
#   bash test-check-rule-citations.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design, matching this skill area's other test suites
# (agent-standards/scripts/tests/test-check-agent-contract.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-rule-citations.py"

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

# assert_contains - passes when VERDICT_OUT carries the given literal row.
assert_contains() {
  local description="$1" needle="$2"
  if printf '%s\n' "$VERDICT_OUT" | grep -qF -- "$needle"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  missing row: %s\n  actual:\n%s\n' "$description" "$needle" "$VERDICT_OUT"
  fi
}

# assert_not_contains - passes when VERDICT_OUT does NOT carry the given
# literal row - the --changed-only contract's "entirely invisible" check.
assert_not_contains() {
  local description="$1" needle="$2"
  if printf '%s\n' "$VERDICT_OUT" | grep -qF -- "$needle"; then
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  unexpected row: %s\n  actual:\n%s\n' "$description" "$needle" "$VERDICT_OUT"
  else
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  fi
}

# new_skill - builds an isolated fixture skill, nested so that the skill
# root's grandparent is a config root that can hold a CLAUDE.md.
# Sets SKILL_DIR (the skill root) and CONFIG_ROOT.
new_skill() {
  local name="$1"
  CONFIG_ROOT="$work_dir/$name"
  SKILL_DIR="$CONFIG_ROOT/skills/$name"
  mkdir -p "$SKILL_DIR/references"
  printf '# %s\n' "$name" > "$SKILL_DIR/SKILL.md"
}

# run_script - invokes check-rule-citations.py on one file, capturing
# stdout/exit code into VERDICT_OUT/VERDICT_EXIT.
run_script() {
  local target_file="$1"
  local out_file="$work_dir/stdout.txt"
  python3 "$SCRIPT" "$target_file" >"$out_file" 2>&1
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

# run_script_args - invokes check-rule-citations.py with arbitrary args
# (a flag plus one or more files), capturing stdout+stderr/exit code
# into VERDICT_OUT/VERDICT_EXIT - same contract as run_script, for the
# --changed-only cases that need more than a single bare file argument.
run_script_args() {
  local out_file="$work_dir/stdout.txt"
  python3 "$SCRIPT" "$@" >"$out_file" 2>&1
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

# git_init_at - initializes a throwaway git repo at $1 with a local
# identity, so a --changed-only fixture never depends on the machine's
# global git config.
git_init_at() {
  local dir="$1"
  git -C "$dir" init -q .
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name test
}

it_should_accept_a_quoted_name_authored_as_a_bold_span_in_the_cited_file() {
  new_skill quoted-bold
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Context section** -- business context in scannable layers.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Business context per the "Context section" rule in writing-style.md.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should accept a quoted name authored as a bold span in the cited file' "0" "$VERDICT_EXIT"
}

it_should_accept_a_quoted_name_authored_as_a_heading_in_the_cited_file() {
  new_skill quoted-heading
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

## Absolute GitHub URLs

Relative paths are unreliable in rendered PR descriptions.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Source links follow writing-style.md's "Absolute GitHub URLs".
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should accept a quoted name authored as a heading in the cited file' "0" "$VERDICT_EXIT"
}

it_should_accept_a_citation_that_compresses_the_authored_rule_name() {
  new_skill compressed-name
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Section names AND body prose in the PR's primary language** -- translate both.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Translate headers per the "Section names in the PR's primary language" rule in writing-style.md.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should accept a citation that compresses the authored rule name' "0" "$VERDICT_EXIT"
}

it_should_accept_a_descriptive_slug_the_cited_file_discusses_without_forwarding_it() {
  new_skill slug-kept
  cat > "$SKILL_DIR/references/pr-page-budget.md" <<'EOF'
# Page budget

Decisions in the body sit at a higher altitude than the appendix catalog.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
The full catalog lives in the appendix, per pr-page-budget.md's altitude rule.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should accept a descriptive slug the cited file discusses without forwarding it' "0" "$VERDICT_EXIT"
}

it_should_accept_a_descriptive_slug_the_cited_file_authors_even_when_that_line_links_elsewhere() {
  new_skill slug-authored-with-link
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Altitude split** -- body summarises, appendix keeps the catalog; examples in decision-quality.md.
EOF
  cat > "$SKILL_DIR/references/decision-quality.md" <<'EOF'
# Decision quality
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Summarise here, per writing-style.md's altitude rule.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should accept a descriptive slug the cited file authors even when that line links elsewhere' "0" "$VERDICT_EXIT"
}

it_should_skip_a_cited_filename_that_resolves_to_no_file() {
  new_skill unresolvable-target
  cat > "$SKILL_DIR/references/pr-description-example.md" <<'EOF'
Criteria came from the "Sync agreements" rule in another-projects-lld.md.
EOF
  run_script "$SKILL_DIR/references/pr-description-example.md"
  assert_eq 'should skip a cited filename that resolves to no file' "0" "$VERDICT_EXIT"
}

it_should_skip_a_citation_inside_a_fenced_code_block() {
  new_skill fenced-citation
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Sample of a citation, shown but not made:

```
See the "Never authored anywhere" rule in writing-style.md.
```
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should skip a citation inside a fenced code block' "0" "$VERDICT_EXIT"
}

it_should_skip_a_citation_inside_frontmatter() {
  new_skill frontmatter-citation
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
---
# budget note citing the "Never authored anywhere" rule in writing-style.md
words-budget: 2048
---

Body prose.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should skip a citation inside frontmatter' "0" "$VERDICT_EXIT"
}

it_should_skip_a_file_citing_itself() {
  new_skill self-citation
  cat > "$SKILL_DIR/SKILL.md" <<'EOF'
# Self citation

Everything obeys the "Never authored anywhere" rule in SKILL.md.
EOF
  run_script "$SKILL_DIR/SKILL.md"
  assert_eq 'should skip a file citing itself' "0" "$VERDICT_EXIT"
}

it_should_flag_a_quoted_name_authored_nowhere_in_the_cited_file() {
  new_skill quoted-missing
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should flag a quoted name authored nowhere in the cited file (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should flag a quoted name authored nowhere in the cited file (row)' \
    '1:unresolved-rule:writing-style.md:"Separate planned from incidental"'
}

it_should_flag_a_quoted_name_the_cited_file_only_mentions_in_body_prose() {
  new_skill quoted-prose-only
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

Bullets should stay short, but no rule of that name is authored here.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Keep the changelog flat, per writing-style.md's "Bullets".
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should flag a quoted name the cited file only mentions in body prose (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should flag a quoted name the cited file only mentions in body prose (row)' \
    '1:unresolved-rule:writing-style.md:"Bullets"'
}

it_should_flag_a_quoted_name_cited_without_a_possessive() {
  new_skill quoted-no-possessive
  cat > "$SKILL_DIR/references/json-format-example.md" <<'EOF'
SKILL.md "JSON snippets" rule, worked example.
EOF
  run_script "$SKILL_DIR/references/json-format-example.md"
  assert_eq 'should flag a quoted name cited without a possessive (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should flag a quoted name cited without a possessive (row)' \
    '1:unresolved-rule:SKILL.md:"JSON snippets"'
}

it_should_flag_a_quoted_name_authored_nowhere_in_a_sh_scripts_comment_header() {
  new_skill sh-comment-header
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  mkdir -p "$SKILL_DIR/scripts"
  cat > "$SKILL_DIR/scripts/check-something.sh" <<'EOF'
#!/usr/bin/env bash
# check-something.sh - example script.
#
# Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  run_script "$SKILL_DIR/scripts/check-something.sh"
  assert_eq 'should flag a quoted name authored nowhere in a .sh script comment header (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should flag a quoted name authored nowhere in a .sh script comment header (row)' \
    '4:unresolved-rule:writing-style.md:"Separate planned from incidental"'
}

it_should_flag_a_descriptive_slug_whose_words_appear_nowhere_in_the_cited_file() {
  new_skill slug-absent
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Cite sources per writing-style.md's provenance rule.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should flag a descriptive slug whose words appear nowhere in the cited file (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should flag a descriptive slug whose words appear nowhere in the cited file (row)' \
    '1:unknown-topic:writing-style.md:provenance rule'
}

it_should_flag_a_descriptive_slug_the_cited_file_only_forwards_to_another_file() {
  new_skill slug-forwarded
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

The altitude split between body and appendix lives in pr-page-budget.md.
EOF
  cat > "$SKILL_DIR/references/pr-page-budget.md" <<'EOF'
# Page budget

- **Altitude** -- the body summarises what the appendix keeps verbatim.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Summarise here, per writing-style.md's altitude rule.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should flag a descriptive slug the cited file only forwards to another file (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should flag a descriptive slug the cited file only forwards to another file (row)' \
    '1:forwarded:writing-style.md:pr-page-budget.md'
}

it_should_resolve_a_claude_md_citation_against_the_config_root_above_the_skill() {
  new_skill claude-md-target
  cat > "$CONFIG_ROOT/CLAUDE.md" <<'EOF'
# Principles

- [Instruction] Batch independent corrections into one numbered list.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Re-ground before editing, per CLAUDE.md's fresh-context rule.
EOF
  run_script "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should resolve a CLAUDE.md citation against the config root above the skill (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should resolve a CLAUDE.md citation against the config root above the skill (row)' \
    '1:unknown-topic:CLAUDE.md:fresh-context rule'
}

it_should_exit_2_when_given_no_files() {
  local out_file="$work_dir/stdout.txt"
  python3 "$SCRIPT" >"$out_file" 2>&1
  assert_eq 'should exit 2 when given no files' "2" "$?"
}

it_should_flag_an_untracked_files_hit_under_changed_only_same_as_without_the_flag() {
  new_skill changed-only-untracked
  git_init_at "$CONFIG_ROOT"
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  run_script_args --changed-only "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should flag an untracked files hit under --changed-only same as without the flag (exit code)' \
    "1" "$VERDICT_EXIT"
  assert_contains 'should flag an untracked files hit under --changed-only same as without the flag (row)' \
    '1:unresolved-rule:writing-style.md:"Separate planned from incidental"'
}

it_should_hide_a_pre_existing_hit_on_an_unmodified_tracked_file_under_changed_only() {
  new_skill changed-only-unmodified
  git_init_at "$CONFIG_ROOT"
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  git -C "$CONFIG_ROOT" add -A
  git -C "$CONFIG_ROOT" commit -q -m fixture
  run_script_args --changed-only "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should hide a pre-existing hit on an unmodified tracked file under --changed-only (exit code)' \
    "0" "$VERDICT_EXIT"
  assert_eq 'should hide a pre-existing hit on an unmodified tracked file under --changed-only (no rows)' \
    "" "$VERDICT_OUT"
}

it_should_report_only_the_hit_on_a_line_the_session_changed_under_changed_only() {
  new_skill changed-only-modified
  git_init_at "$CONFIG_ROOT"
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  git -C "$CONFIG_ROOT" add -A
  git -C "$CONFIG_ROOT" commit -q -m fixture
  cat >> "$SKILL_DIR/references/pr-template.md" <<'EOF'
Keep the changelog flat, per the "Another missing" rule in writing-style.md.
EOF
  run_script_args --changed-only "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should report only the changed-line hit under --changed-only (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should report the hit on the newly appended line under --changed-only' \
    '2:unresolved-rule:writing-style.md:"Another missing"'
  assert_not_contains 'should hide the pre-existing hit on the unchanged first line under --changed-only' \
    '1:unresolved-rule:writing-style.md:"Separate planned from incidental"'
}

it_should_scope_changed_only_independently_per_file_when_multiple_files_are_given() {
  new_skill changed-only-multi
  git_init_at "$CONFIG_ROOT"
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template-tracked.md" <<'EOF'
Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  git -C "$CONFIG_ROOT" add -A
  git -C "$CONFIG_ROOT" commit -q -m fixture
  cat > "$SKILL_DIR/references/pr-template-untracked.md" <<'EOF'
Cite sources per writing-style.md's provenance rule.
EOF
  run_script_args --changed-only \
    "$SKILL_DIR/references/pr-template-tracked.md" \
    "$SKILL_DIR/references/pr-template-untracked.md"
  assert_eq 'should scope --changed-only independently per file (exit code)' "1" "$VERDICT_EXIT"
  assert_contains 'should still flag the untracked files hit' \
    '1:unknown-topic:writing-style.md:provenance rule'
  assert_not_contains 'should hide the tracked-unmodified files pre-existing hit' \
    '1:unresolved-rule:writing-style.md:"Separate planned from incidental"'
}

it_should_exit_2_and_name_the_file_when_changed_lines_sh_cannot_determine_scope() {
  new_skill changed-only-not-a-repo
  # Deliberately no git_init_at - the fixture sits outside any git work
  # tree, so changed-lines.sh itself exits 2 and this must propagate
  # rather than read as clean or fall back to whole-file scope.
  cat > "$SKILL_DIR/references/writing-style.md" <<'EOF'
# Writing style

- **Bullets** -- one thought per bullet.
EOF
  cat > "$SKILL_DIR/references/pr-template.md" <<'EOF'
Group changes per the "Separate planned from incidental" rule in writing-style.md.
EOF
  run_script_args --changed-only "$SKILL_DIR/references/pr-template.md"
  assert_eq 'should exit 2 when changed-lines.sh cannot determine scope' "2" "$VERDICT_EXIT"
  assert_contains 'should name the file in the exit-2 stderr message' \
    "$SKILL_DIR/references/pr-template.md"
}

it_should_accept_a_quoted_name_authored_as_a_bold_span_in_the_cited_file
it_should_accept_a_quoted_name_authored_as_a_heading_in_the_cited_file
it_should_accept_a_citation_that_compresses_the_authored_rule_name
it_should_accept_a_descriptive_slug_the_cited_file_discusses_without_forwarding_it
it_should_accept_a_descriptive_slug_the_cited_file_authors_even_when_that_line_links_elsewhere
it_should_skip_a_cited_filename_that_resolves_to_no_file
it_should_skip_a_citation_inside_a_fenced_code_block
it_should_skip_a_citation_inside_frontmatter
it_should_skip_a_file_citing_itself
it_should_flag_a_quoted_name_authored_nowhere_in_the_cited_file
it_should_flag_a_quoted_name_the_cited_file_only_mentions_in_body_prose
it_should_flag_a_quoted_name_cited_without_a_possessive
it_should_flag_a_quoted_name_authored_nowhere_in_a_sh_scripts_comment_header
it_should_flag_a_descriptive_slug_whose_words_appear_nowhere_in_the_cited_file
it_should_flag_a_descriptive_slug_the_cited_file_only_forwards_to_another_file
it_should_resolve_a_claude_md_citation_against_the_config_root_above_the_skill
it_should_exit_2_when_given_no_files
it_should_flag_an_untracked_files_hit_under_changed_only_same_as_without_the_flag
it_should_hide_a_pre_existing_hit_on_an_unmodified_tracked_file_under_changed_only
it_should_report_only_the_hit_on_a_line_the_session_changed_under_changed_only
it_should_scope_changed_only_independently_per_file_when_multiple_files_are_given
it_should_exit_2_and_name_the_file_when_changed_lines_sh_cannot_determine_scope

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
