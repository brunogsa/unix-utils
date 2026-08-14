#!/usr/bin/env bash
# test-check-agent-contract.sh - plain-bash test file for
# check-agent-contract.sh.
#
# Usage:
#   bash test-check-agent-contract.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design, matching this skill area's other test suites
# (spec-driven-development/scripts/tests/test-check-tasks-dag.sh).

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-agent-contract.sh"

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

# assert_nonempty - passes when the given value is a non-empty string.
assert_nonempty() {
  local description="$1" actual="$2"
  if [ -n "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s (expected non-empty diagnostic output)\n' "$description"
  fi
}

# run_script - invokes check-agent-contract.sh against a fixture
# directory, capturing stdout/exit code into VERDICT_OUT/VERDICT_EXIT.
run_script() {
  local target_dir="$1"
  local out_file="$work_dir/stdout.txt"
  bash "$SCRIPT" "$target_dir" >"$out_file" 2>&1
  VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

it_should_exit_0_when_a_file_has_all_six_required_headings_in_canonical_order_with_non_empty_content() {
  local dir="$work_dir/happy-six-headings"
  mkdir -p "$dir"
  cat > "$dir/sample-agent.md" <<'EOF'
---
name: sample-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.
- The directory scope to search within.

## Sources and tools

- Grep and Glob for search; Read for confirming matches.

## Procedure

1. Run the search across the given scope.
2. Summarize every match found.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when a file has all six required headings in canonical order with non-empty content" "0" "$VERDICT_EXIT"
}

it_should_exit_0_when_a_shadow_file_carries_only_a_shadows_heading_with_non_empty_content() {
  local dir="$work_dir/happy-shadow"
  mkdir -p "$dir"
  cat > "$dir/sample-shadow.md" <<'EOF'
---
name: sample-shadow
description: Sample shadow agent used for fixture testing.
model: sonnet
---

This file shadows Claude Code's built-in sample agent.

## Shadows

Shadows the built-in sample agent, overriding maxTurns: 64 as a
runaway-loop backstop.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when a shadow file carries only a ## Shadows heading with non-empty content" "0" "$VERDICT_EXIT"
}

it_should_exit_0_when_frontmatter_has_a_name_matching_the_filename_non_empty_description_and_a_model_key() {
  local dir="$work_dir/happy-frontmatter"
  mkdir -p "$dir"
  cat > "$dir/quoted-frontmatter-agent.md" <<'EOF'
---
name: quoted-frontmatter-agent
description: "Sample agent with a quoted description for fixture testing."
model: opus
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when frontmatter has a name matching the filename, non-empty description, and a model key" "0" "$VERDICT_EXIT"
}

it_should_exit_0_when_a_shadow_files_frontmatter_has_no_model_key() {
  local dir="$work_dir/happy-shadow-no-model"
  mkdir -p "$dir"
  cat > "$dir/general-sample.md" <<'EOF'
---
name: general-sample
description: Sample shadow agent used for fixture testing.
maxTurns: 128
---

This file shadows a Claude Code built-in for one reason: setting
maxTurns as a runaway-loop backstop.

## Shadows

Shadows the built-in sample agent, overriding maxTurns: 128.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when a shadow file's frontmatter has no model key" "0" "$VERDICT_EXIT"
}

it_should_exit_0_when_a_heading_has_trailing_whitespace() {
  local dir="$work_dir/corner-trailing-whitespace"
  mkdir -p "$dir"
  printf '%s\n' \
    '---' \
    'name: trailing-whitespace-agent' \
    'description: Sample agent used for fixture testing.' \
    'model: sonnet' \
    'effort: high' \
    '---' \
    '' \
    '## Objective   ' \
    '' \
    'Search the codebase for a pattern and report every match.' \
    '' \
    '## Inputs' \
    '' \
    '- The search query string.' \
    '' \
    '## Sources and tools' \
    '' \
    '- Grep and Glob for search.' \
    '' \
    '## Procedure' \
    '' \
    '1. Run the search.' \
    '2. Summarize the results.' \
    '' \
    '## Boundaries' \
    '' \
    '- Never modify any file found during the search.' \
    '' \
    '## Report format' \
    '' \
    '- **Matches**: file:line pairs found, or none.' \
    > "$dir/trailing-whitespace-agent.md"
  run_script "$dir"
  assert_eq "should exit 0 when a heading has trailing whitespace" "0" "$VERDICT_EXIT"
}

it_should_skip_non_md_files_in_the_target_directory() {
  local dir="$work_dir/corner-skip-non-md"
  mkdir -p "$dir"
  cat > "$dir/sample-agent.md" <<'EOF'
---
name: sample-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  cat > "$dir/notes.txt" <<'EOF'
This is not a markdown agent file and has none of the required
headings or frontmatter at all.
EOF
  run_script "$dir"
  assert_eq "should skip non-.md files in the target directory" "0" "$VERDICT_EXIT"
}

it_should_exit_1_when_a_required_headings_text_only_appears_inside_a_fenced_code_block() {
  local dir="$work_dir/corner-fenced-heading"
  mkdir -p "$dir"
  cat > "$dir/fenced-heading-agent.md" <<'EOF'
---
name: fenced-heading-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

Example of the expected report shape:

```
## Report format

- **Matches**: file:line pairs found, or none.
```

Run the search and summarize the results.

## Boundaries

- Never modify any file found during the search.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a required heading's text only appears inside a fenced code block (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a required heading's text only appears inside a fenced code block (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_a_required_heading_is_missing() {
  local dir="$work_dir/failure-missing-heading"
  mkdir -p "$dir"
  cat > "$dir/missing-heading-agent.md" <<'EOF'
---
name: missing-heading-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a required heading is missing (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a required heading is missing (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_a_required_heading_has_no_content_beneath_it_before_the_next_heading() {
  local dir="$work_dir/failure-empty-heading"
  mkdir -p "$dir"
  cat > "$dir/empty-heading-agent.md" <<'EOF'
---
name: empty-heading-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a required heading has no content beneath it before the next heading (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a required heading has no content beneath it before the next heading (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_headings_appear_out_of_canonical_order() {
  local dir="$work_dir/failure-out-of-order"
  mkdir -p "$dir"
  cat > "$dir/out-of-order-agent.md" <<'EOF'
---
name: out-of-order-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Inputs

- The search query string.

## Objective

Search the codebase for a pattern and report every match.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when headings appear out of canonical order (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when headings appear out of canonical order (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_a_heading_is_duplicated() {
  local dir="$work_dir/failure-duplicate-heading"
  mkdir -p "$dir"
  cat > "$dir/duplicate-heading-agent.md" <<'EOF'
---
name: duplicate-heading-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Objective

A second Objective section that should never be allowed.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a heading is duplicated (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a heading is duplicated (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_an_h3_objective_is_used_instead_of_h2_objective() {
  local dir="$work_dir/failure-h3-objective"
  mkdir -p "$dir"
  cat > "$dir/h3-objective-agent.md" <<'EOF'
---
name: h3-objective-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

### Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when an h3 ### Objective is used instead of h2 ## Objective (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when an h3 ### Objective is used instead of h2 ## Objective (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_frontmatter_name_does_not_match_the_filename() {
  local dir="$work_dir/failure-name-mismatch"
  mkdir -p "$dir"
  cat > "$dir/name-mismatch-agent.md" <<'EOF'
---
name: a-completely-different-name
description: Sample agent used for fixture testing.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when frontmatter name does not match the filename (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when frontmatter name does not match the filename (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_frontmatter_description_is_missing_or_empty() {
  local dir="$work_dir/failure-missing-description"
  mkdir -p "$dir"
  cat > "$dir/missing-description-agent.md" <<'EOF'
---
name: missing-description-agent
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when frontmatter description is missing or empty (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when frontmatter description is missing or empty (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_a_non_shadow_files_frontmatter_has_no_model_key() {
  local dir="$work_dir/failure-missing-model"
  mkdir -p "$dir"
  cat > "$dir/missing-model-agent.md" <<'EOF'
---
name: missing-model-agent
description: Sample agent used for fixture testing.
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a non-shadow file's frontmatter has no model key (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a non-shadow file's frontmatter has no model key (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_1_when_a_non_shadow_files_frontmatter_has_no_effort_key() {
  local dir="$work_dir/failure-missing-effort"
  mkdir -p "$dir"
  cat > "$dir/missing-effort-agent.md" <<'EOF'
---
name: missing-effort-agent
description: Sample agent used for fixture testing.
model: sonnet
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a non-shadow file's frontmatter has no effort key (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a non-shadow file's frontmatter has no effort key (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_0_when_a_description_lands_on_exactly_the_character_budget() {
  local dir="$work_dir/happy-description-at-cap"
  mkdir -p "$dir"
  cat > "$dir/at-cap-description-agent.md" <<'EOF'
---
name: at-cap-description-agent
description: Sample agent used for fixture testing, with a description written deliberately to land on exactly the two-hundred-and-fifty character budget so the length gate has its permitted boundary pinned, padded with filler carrying no meaning.................
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when a description lands on exactly the character budget" "0" "$VERDICT_EXIT"
}

it_should_exit_1_when_a_non_shadow_description_exceeds_the_character_budget() {
  local dir="$work_dir/failure-long-description"
  mkdir -p "$dir"
  cat > "$dir/long-description-agent.md" <<'EOF'
---
name: long-description-agent
description: Sample agent used for fixture testing, with a description written deliberately past the two-hundred-and-fifty character budget so the length gate has something real to flag, padded here with filler that carries no meaning at all beyond its own length.
model: sonnet
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 1 when a non-shadow description exceeds the character budget (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should exit 1 when a non-shadow description exceeds the character budget (diagnostic present)" "$VERDICT_OUT"
}

it_should_exit_0_when_a_shadow_files_description_exceeds_the_character_budget() {
  local dir="$work_dir/happy-long-shadow-description"
  mkdir -p "$dir"
  cat > "$dir/long-description-shadow.md" <<'EOF'
---
name: long-description-shadow
description: Sample agent used for fixture testing, with a description written deliberately past the two-hundred-and-fifty character budget so the length gate has something real to flag, padded here with filler that carries no meaning at all beyond its own length.
---

## Shadows

Shadows the built-in sample agent, overriding maxTurns: 64 as a
runaway-loop backstop.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when a shadow file's description exceeds the character budget" "0" "$VERDICT_EXIT"
}

it_should_exit_0_when_an_exempt_named_agents_description_exceeds_the_character_budget() {
  local dir="$work_dir/happy-exempt-description"
  mkdir -p "$dir"
  cat > "$dir/markdown-standards-fixer.md" <<'EOF'
---
name: markdown-standards-fixer
description: Sample agent used for fixture testing, with a description written deliberately past the two-hundred-and-fifty character budget so the length gate has something real to flag, padded here with filler that carries no meaning at all beyond its own length.
model: haiku
effort: high
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should exit 0 when an exempt-named agent's description exceeds the character budget" "0" "$VERDICT_EXIT"
}


it_should_fail_an_agent_file_that_declares_allowed_subagents_alongside_a_disallowed_tools_containing_agent() {
  local dir="$work_dir/failure-allowed-subagents-contradicts-disallowed-tools"
  mkdir -p "$dir"
  cat > "$dir/contradicting-carve-out-agent.md" <<'EOF'
---
name: contradicting-carve-out-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
disallowedTools: Agent, Workflow
allowedSubagents: Explore
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should fail an agent file that declares allowedSubagents alongside a disallowedTools containing Agent (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should fail an agent file that declares allowedSubagents alongside a disallowedTools containing Agent (diagnostic present)" "$VERDICT_OUT"
}

it_should_fail_an_agent_file_whose_allowed_subagents_key_is_present_but_has_an_empty_list() {
  local dir="$work_dir/corner-allowed-subagents-empty-list"
  mkdir -p "$dir"
  cat > "$dir/empty-allowed-subagents-agent.md" <<'EOF'
---
name: empty-allowed-subagents-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
disallowedTools: Workflow
allowedSubagents:
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should fail an agent file whose allowedSubagents key is present but has an empty list (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should fail an agent file whose allowedSubagents key is present but has an empty list (diagnostic present)" "$VERDICT_OUT"
}

it_should_fail_an_agent_file_whose_allowed_subagents_list_contains_only_whitespace() {
  local dir="$work_dir/corner-allowed-subagents-whitespace-only"
  mkdir -p "$dir"
  printf '%s\n' \
    '---' \
    'name: whitespace-allowed-subagents-agent' \
    'description: Sample agent used for fixture testing.' \
    'model: sonnet' \
    'effort: high' \
    'disallowedTools: Workflow' \
    'allowedSubagents:    ' \
    '---' \
    '' \
    '## Objective' \
    '' \
    'Search the codebase for a pattern and report every match.' \
    '' \
    '## Inputs' \
    '' \
    '- The search query string.' \
    '' \
    '## Sources and tools' \
    '' \
    '- Grep and Glob for search.' \
    '' \
    '## Procedure' \
    '' \
    '1. Run the search.' \
    '2. Summarize the results.' \
    '' \
    '## Boundaries' \
    '' \
    '- Never modify any file found during the search.' \
    '' \
    '## Report format' \
    '' \
    '- **Matches**: file:line pairs found, or none.' \
    > "$dir/whitespace-allowed-subagents-agent.md"
  run_script "$dir"
  assert_eq "should fail an agent file whose allowedSubagents list contains only whitespace (exit code)" "1" "$VERDICT_EXIT"
  assert_nonempty "should fail an agent file whose allowedSubagents list contains only whitespace (diagnostic present)" "$VERDICT_OUT"
}

it_should_pass_an_agent_file_that_declares_no_allowed_subagents_key_at_all() {
  local dir="$work_dir/happy-no-allowed-subagents-key"
  mkdir -p "$dir"
  cat > "$dir/no-allowed-subagents-agent.md" <<'EOF'
---
name: no-allowed-subagents-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
disallowedTools: Agent, Workflow
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should pass an agent file that declares no allowedSubagents key at all" "0" "$VERDICT_EXIT"
}

it_should_pass_an_agent_file_whose_allowed_subagents_list_is_non_empty_and_whose_disallowed_tools_does_not_contain_agent() {
  local dir="$work_dir/happy-allowed-subagents-non-empty-no-agent-conflict"
  mkdir -p "$dir"
  cat > "$dir/valid-carve-out-agent.md" <<'EOF'
---
name: valid-carve-out-agent
description: Sample agent used for fixture testing.
model: sonnet
effort: high
disallowedTools: Workflow
allowedSubagents: Explore
---

## Objective

Search the codebase for a pattern and report every match.

## Inputs

- The search query string.

## Sources and tools

- Grep and Glob for search.

## Procedure

1. Run the search.
2. Summarize the results.

## Boundaries

- Never modify any file found during the search.

## Report format

- **Matches**: file:line pairs found, or none.
EOF
  run_script "$dir"
  assert_eq "should pass an agent file whose allowedSubagents list is non-empty and whose disallowedTools does not contain Agent" "0" "$VERDICT_EXIT"
}

it_should_exit_0_when_a_file_has_all_six_required_headings_in_canonical_order_with_non_empty_content
it_should_exit_0_when_a_shadow_file_carries_only_a_shadows_heading_with_non_empty_content
it_should_exit_0_when_frontmatter_has_a_name_matching_the_filename_non_empty_description_and_a_model_key
it_should_exit_0_when_a_shadow_files_frontmatter_has_no_model_key
it_should_exit_0_when_a_heading_has_trailing_whitespace
it_should_skip_non_md_files_in_the_target_directory
it_should_exit_1_when_a_required_headings_text_only_appears_inside_a_fenced_code_block
it_should_exit_1_when_a_required_heading_is_missing
it_should_exit_1_when_a_required_heading_has_no_content_beneath_it_before_the_next_heading
it_should_exit_1_when_headings_appear_out_of_canonical_order
it_should_exit_1_when_a_heading_is_duplicated
it_should_exit_1_when_an_h3_objective_is_used_instead_of_h2_objective
it_should_exit_1_when_frontmatter_name_does_not_match_the_filename
it_should_exit_1_when_frontmatter_description_is_missing_or_empty
it_should_exit_1_when_a_non_shadow_files_frontmatter_has_no_model_key
it_should_exit_1_when_a_non_shadow_files_frontmatter_has_no_effort_key
it_should_exit_1_when_a_non_shadow_description_exceeds_the_character_budget
it_should_exit_0_when_a_description_lands_on_exactly_the_character_budget
it_should_exit_0_when_a_shadow_files_description_exceeds_the_character_budget
it_should_exit_0_when_an_exempt_named_agents_description_exceeds_the_character_budget
it_should_pass_an_agent_file_that_declares_no_allowed_subagents_key_at_all
it_should_pass_an_agent_file_whose_allowed_subagents_list_is_non_empty_and_whose_disallowed_tools_does_not_contain_agent
it_should_fail_an_agent_file_whose_allowed_subagents_key_is_present_but_has_an_empty_list
it_should_fail_an_agent_file_whose_allowed_subagents_list_contains_only_whitespace
it_should_fail_an_agent_file_that_declares_allowed_subagents_alongside_a_disallowed_tools_containing_agent

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
