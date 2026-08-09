#!/usr/bin/env bash
# test-check-coverage-checklists.sh - plain-bash test file for
# check-coverage-checklists.sh.
#
# Usage:
#   bash test-check-coverage-checklists.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats
# dependency by design, matching the other scripts in this skill's
# test suite.
#
# Fixtures use a small custom taxonomy file, not the real
# coverage-taxonomy.md -- a fixture built against the real file would
# silently go stale (false "missing row" failures) the next time
# someone edits that file's row list, since it's a shared canonical
# doc this suite doesn't own.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-coverage-checklists.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual, prints ok/not-ok.
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

# taxonomy_file - a small, fixed corner-cases/failure-modes taxonomy
# (with an Async delivery row nested under Failure modes, mirroring
# the real file's structure) so fixtures stay short and immune to
# drift in the real canonical taxonomy.
taxonomy_file="$work_dir/taxonomy.md"
cat > "$taxonomy_file" <<'EOF'
## Corner cases (data-shape boundaries)

- empty / single / many
- null / undefined / missing

## Failure modes (adverse interactions and dependencies)

- validation error (4xx)
- downstream timeout / never-responds

### Async delivery (event/message consumers)

- duplicate delivery (at-least-once redelivery)

## Classification note

Unrelated trailing note, not a row.
EOF

# run_script - invokes check-coverage-checklists.sh against a spec
# fixture and the fixed test taxonomy, capturing stderr/exit code
# into VERDICT_ERR/VERDICT_EXIT (stdout is discarded -- these tests
# assert on exit code and diagnostic presence only).
run_script() {
  local spec_file="$1"
  local err_file="$work_dir/stderr.txt"
  bash "$SCRIPT" "$spec_file" "$taxonomy_file" >/dev/null 2>"$err_file"
  VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_spec - writes the given "## Testable Acceptance Criteria"
# body to a fresh spec fixture under work_dir, returns its path.
write_spec() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '## Testable Acceptance Criteria\n\n%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_pass_when_both_checklists_instantiate_every_taxonomy_row() {
  local fixture
  fixture=$(write_spec "complete" '#### Happy path

### AC-1: When a request arrives, the system shall respond

- **When** a request arrives
- **Then** it succeeds

#### Corner cases

**Boundary checklist**

- empty / single / many: covered (AC-2)
- null / undefined / missing: N/A — irrelevant

### AC-2: When the input is empty, the system shall return an empty result

- **When** the input list is empty
- **Then** the system returns an empty result

#### Failure modes

**Failure category checklist**

- validation error (4xx): covered (AC-3)
- downstream timeout / never-responds: N/A — irrelevant
- duplicate delivery (at-least-once redelivery): N/A — irrelevant

### AC-3: If the request is invalid, then the system shall return a 400

- **When** the request fails validation
- **Then** the system returns HTTP 400')
  run_script "$fixture"
  assert_eq "should pass when both checklists instantiate every taxonomy row" "0" "$VERDICT_EXIT"
}

it_should_fail_when_one_taxonomy_row_is_missing_from_a_checklist() {
  local fixture
  fixture=$(write_spec "missing-row" '#### Corner cases

**Boundary checklist**

- empty / single / many: covered (AC-2)

### AC-2: When the input is empty, the system shall return an empty result

- **When** the input list is empty
- **Then** the system returns an empty result')
  run_script "$fixture"
  assert_eq "should fail when one taxonomy row is missing from a checklist (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should fail when one taxonomy row is missing from a checklist (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should fail when one taxonomy row is missing from a checklist (diagnostic present)\n'
  fi
}

it_should_fail_when_a_row_has_malformed_grammar() {
  local fixture
  fixture=$(write_spec "malformed-row" '#### Corner cases

**Boundary checklist**

- empty / single / many: covered (AC-2)
- null / undefined / missing: sometimes

### AC-2: When the input is empty, the system shall return an empty result

- **When** the input list is empty
- **Then** the system returns an empty result')
  run_script "$fixture"
  assert_eq "should fail when a row has malformed grammar (exit code)" "1" "$VERDICT_EXIT"
  if [ -n "$VERDICT_ERR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - should fail when a row has malformed grammar (diagnostic present)\n'
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - should fail when a row has malformed grammar (diagnostic present)\n'
  fi
}

it_should_pass_when_the_whole_checklist_opt_out_marker_is_used() {
  local fixture
  fixture=$(write_spec "opt-out" '#### Corner cases

**DECISION:** Skip boundary checklist because this is a one-line config change.

### AC-2: When the input is empty, the system shall return an empty result

- **When** the input list is empty
- **Then** the system returns an empty result')
  run_script "$fixture"
  assert_eq "should pass when the whole-checklist opt-out marker is used" "0" "$VERDICT_EXIT"
}

it_should_pass_trivially_when_the_spec_has_no_checklist_block_at_all() {
  local fixture
  fixture=$(write_spec "no-checklist" '#### Happy path

### AC-1: When a request arrives, the system shall respond

- **When** a request arrives
- **Then** it succeeds')
  run_script "$fixture"
  assert_eq "should pass trivially when the spec has no checklist block at all" "0" "$VERDICT_EXIT"
}

it_should_report_a_usage_error_when_the_spec_file_is_missing() {
  run_script "$work_dir/absent.md"
  assert_eq "should report a usage error when the spec file is missing" "2" "$VERDICT_EXIT"
}

it_should_not_count_a_row_quoted_inside_a_fenced_code_block() {
  local fixture
  fixture=$(write_spec "fenced-row" '#### Corner cases

**Boundary checklist**

Example format:

```markdown
- empty / single / many: covered (AC-2)
```

- null / undefined / missing: N/A — irrelevant

### AC-2: When the input is empty, the system shall return an empty result

- **When** the input list is empty
- **Then** the system returns an empty result')
  run_script "$fixture"
  assert_eq "should not count a row quoted inside a fenced code block (exit code)" "1" "$VERDICT_EXIT"
  case "$VERDICT_ERR" in
    *"missing: empty / single / many"*)
      pass_count=$((pass_count + 1))
      printf 'ok - should not count a row quoted inside a fenced code block (row still missing)\n'
      ;;
    *)
      fail_count=$((fail_count + 1))
      printf 'not ok - should not count a row quoted inside a fenced code block (row still missing)\n'
      ;;
  esac
}

it_should_pass_when_both_checklists_instantiate_every_taxonomy_row
it_should_fail_when_one_taxonomy_row_is_missing_from_a_checklist
it_should_fail_when_a_row_has_malformed_grammar
it_should_pass_when_the_whole_checklist_opt_out_marker_is_used
it_should_pass_trivially_when_the_spec_has_no_checklist_block_at_all
it_should_report_a_usage_error_when_the_spec_file_is_missing
it_should_not_count_a_row_quoted_inside_a_fenced_code_block

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
