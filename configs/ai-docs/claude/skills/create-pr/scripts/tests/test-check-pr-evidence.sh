#!/usr/bin/env bash
# test-check-pr-evidence.sh - plain-bash test file for
# check-pr-evidence.sh.
#
# Usage:
#   bash test-check-pr-evidence.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-pr-evidence.sh"

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

# run_script - invokes check-pr-evidence.sh with any number of
# args, capturing stdout/exit code into VERDICT_OUT and
# VERDICT_EXIT. stderr goes to a file rather than a variable:
# no assertion below reads a diagnostic's wording.
run_script() {
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  VERDICT_EXIT=0
  bash "$SCRIPT" "$@" >"$out_file" 2>"$err_file" || VERDICT_EXIT=$?
  VERDICT_OUT=$(cat "$out_file")
}

# write_body - writes the given PR-body markdown to a fresh
# fixture under work_dir, returns its path via stdout.
write_body() {
  local name="$1" body="$2"
  local path="$work_dir/$name.md"
  printf '%s\n' "$body" > "$path"
  printf '%s' "$path"
}

it_should_pass_a_scenario_whose_block_pastes_a_fenced_response_body() {
  local fixture
  fixture=$(write_body "happy-fenced-artifact" '## Evidences

12 tests added, covering 5 acceptance criteria.

<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — kit-less collection against Oracle EBS on stage</summary>

Ran a kit-less collection against Oracle EBS on stage, 2026-09-18 14:02 UTC.

`POST /v1/collections` → `201 Created`:

```json
{ "collectionId": 88421, "totalItems": 3 }
```

</details>')
  run_script "$fixture"
  assert_eq "should pass a scenario whose block pastes a fenced response body (exit code)" "0" "$VERDICT_EXIT"
}

it_should_pass_a_scenario_whose_only_artifact_is_a_screenshot() {
  local fixture
  fixture=$(write_body "happy-image-artifact" '## Evidences

<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — invoice drawer on stage</summary>

Opened the invoice drawer on stage, 2026-09-18, and read back the rendered total.

![invoice drawer showing R$ 1.058,33](https://user-images.githubusercontent.com/1/drawer.png)

</details>')
  run_script "$fixture"
  assert_eq "should pass a scenario whose only artifact is a screenshot (exit code)" "0" "$VERDICT_EXIT"
}

it_should_fail_a_scenario_whose_only_fence_is_a_mermaid_diagram() {
  local fixture
  fixture=$(write_body "mermaid-is-not-evidence" '## Evidences

<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — sync flow walked on stage</summary>

Walked the sync flow on stage, 2026-09-18, and confirmed each hop.

```mermaid
graph LR
  A[collection] --> B[Oracle EBS]
```

</details>')
  run_script "$fixture"
  assert_eq "should fail a scenario whose only fence is a mermaid diagram, since a diagram is not evidence of a run (exit code)" "3" "$VERDICT_EXIT"
  assert_eq "should name the scenario missing its artifact when the only fence is mermaid (breakdown)" "1" "$(printf '%s\n' "$VERDICT_OUT" | grep -c 'scenario 1')"
}

it_should_fail_a_scenario_that_narrates_findings_in_prose_bullets_only() {
  local fixture
  fixture=$(write_body "regression-narrated-findings" '## Evidences

<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — kit-less collection shapes against Oracle EBS and SGE</summary>

Ran four kit-less-collection shapes against Oracle EBS and three against SGE
directly on stage, 2026-09-18, reading back each ERP response.

- Oracle EBS accepted all four shapes and returned the professor lines.
- SGE rejected the kit-less shape and returned a validation error.
- No duplicate agreements were created by either ERP.

</details>')
  run_script "$fixture"
  assert_eq "REGRESSION: should fail a scenario that narrates findings in prose bullets only, with no request, response body or pasted artifact (exit code)" "3" "$VERDICT_EXIT"
  assert_eq "REGRESSION: should name the narrated scenario in the breakdown rather than only a total (breakdown)" "1" "$(printf '%s\n' "$VERDICT_OUT" | grep -c 'scenario 1')"
}

it_should_fail_a_scenario_link_that_points_at_no_anchor() {
  local fixture
  fixture=$(write_body "dangling-scenario-link" '## Acceptance criteria

> Covered by [manual tests](#scenario-2).

## Evidences

<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — kit-less collection against Oracle EBS on stage</summary>

Ran it on stage, 2026-09-18.

```text
201 Created
```

</details>')
  run_script "$fixture"
  assert_eq "should fail a scenario link that points at no anchor (exit code)" "3" "$VERDICT_EXIT"
  assert_eq "should name the dangling link target in the breakdown (breakdown)" "1" "$(printf '%s\n' "$VERDICT_OUT" | grep -c 'scenario 2')"
}

it_should_warn_when_a_scenario_carries_an_artifact_but_no_date() {
  local fixture
  fixture=$(write_body "artifact-without-date" '## Evidences

<a id="scenario-1"></a>
<details>
<summary>Scenario 1 — kit-less collection against Oracle EBS on stage</summary>

`POST /v1/collections` → `201 Created`:

```json
{ "collectionId": 88421 }
```

</details>')
  run_script "$fixture"
  assert_eq "should warn when a scenario carries an artifact but no date anywhere in its block (exit code)" "2" "$VERDICT_EXIT"
}

it_should_pass_a_fully_automated_body_with_no_scenario_anchors() {
  local fixture
  fixture=$(write_body "fully-automated" '## Evidences

12 tests added, covering the 5 acceptance criteria in the appendix.')
  run_script "$fixture"
  assert_eq "should pass a fully automated body whose Evidences carries only the counted-tests line (exit code)" "0" "$VERDICT_EXIT"
}

it_should_exit_1_when_the_file_does_not_exist() {
  run_script "$work_dir/does-not-exist.md"
  assert_eq "should exit 1 when the file does not exist" "1" "$VERDICT_EXIT"
  assert_eq "should exit 1 when the file does not exist (nothing on stdout)" "" "$VERDICT_OUT"
}

it_should_exit_1_when_called_with_no_argument() {
  run_script
  assert_eq "should exit 1 when called with no argument" "1" "$VERDICT_EXIT"
}

it_should_pass_a_scenario_whose_block_pastes_a_fenced_response_body
it_should_pass_a_scenario_whose_only_artifact_is_a_screenshot
it_should_pass_a_fully_automated_body_with_no_scenario_anchors
it_should_fail_a_scenario_whose_only_fence_is_a_mermaid_diagram
it_should_fail_a_scenario_that_narrates_findings_in_prose_bullets_only
it_should_fail_a_scenario_link_that_points_at_no_anchor
it_should_warn_when_a_scenario_carries_an_artifact_but_no_date
it_should_exit_1_when_the_file_does_not_exist
it_should_exit_1_when_called_with_no_argument

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
