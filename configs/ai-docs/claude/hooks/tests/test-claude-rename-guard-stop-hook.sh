#!/usr/bin/env bash
# Plain-bash test file for claude-rename-guard-stop-hook.sh.
#
# Usage:
#   bash test-claude-rename-guard-stop-hook.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
#
# Same no-bats rationale as the sibling test files.
#
# How the hook is exercised: it forwards its own extra
# args straight to check-rename-references.py, so each
# case pins --repo/--settings to an isolated fixture
# instead of this machine's real corpus. The one exception
# is the real-corpus case below, matching the checker's
# own 2-second-budget test's fixtures-only exception.
#
# The checker itself is NOT stubbed: these tests assert
# the hook's exit-code-to-JSON translation and its
# loop/fail-open guards, and a stubbed checker would
# assert that translation away.

set -uo pipefail

hooks_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$hooks_dir/claude-rename-guard-stop-hook.sh"

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

# assert_true - inline assert helper: fails unless condition (a shell test
# expression string, eval'd) is true.
assert_true() {
  local description="$1" condition="$2"
  if eval "$condition"; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  condition: %s\n' "$description" "$condition"
  fi
}

# no_settings - a --settings path that never exists, so a case not about
# settings.json content gets a clean, empty scan of that source. Mirrors
# check-rename-references.test.py's _no_settings helper.
no_settings() {
  printf '%s' "$work_dir/no-settings.json"
}

# run_hook - runs the real hook with the given stdin JSON, forwarding any
# extra args straight through to check-rename-references.py. Captures
# stdout in HOOK_OUT.
run_hook() {
  local stdin_json="$1"; shift
  HOOK_OUT=$(printf '%s' "$stdin_json" | bash "$HOOK" "$@" 2>/dev/null)
}

it_should_stay_silent_when_the_repo_has_no_dangling_reference() {
  local repo="$work_dir/clean-repo"
  mkdir -p "$repo/hooks"
  printf '#!/usr/bin/env bash\necho one\n' > "$repo/hooks/foo.sh"
  printf 'See hooks/foo.sh for details.\n' > "$repo/README.md"

  run_hook '{"session_id": "sess-rg-clean", "stop_hook_active": false}' \
    --repo "$repo" --settings "$(no_settings)"

  assert_eq "should stay silent when the repo has no dangling reference" "" "$HOOK_OUT"
}

it_should_stay_silent_when_only_a_markdown_warn_finding_exists() {
  local repo="$work_dir/warn-only-repo"
  mkdir -p "$repo"
  # The backticks are literal markdown inline-code syntax written into the
  # fixture file, not a shell command substitution.
  # shellcheck disable=SC2016
  printf 'Prose example: run `example-script.sh` to see how it works.\n' > "$repo/README.md"

  run_hook '{"session_id": "sess-rg-warn", "stop_hook_active": false}' \
    --repo "$repo" --settings "$(no_settings)"

  assert_eq "should stay silent when only a markdown WARN finding exists (AC2 pass-through)" "" "$HOOK_OUT"
}

it_should_block_when_the_checker_finds_a_dangling_fail_reference() {
  local repo="$work_dir/fail-repo"
  local settings="$repo/settings.json"
  mkdir -p "$repo"
  printf '{"hooks": {}, "note": "%s/hooks/renamed-away.sh"}' "$repo" > "$settings"

  run_hook '{"session_id": "sess-rg-fail", "stop_hook_active": false}' \
    --repo "$repo" --settings "$settings"

  assert_eq "should block when the checker finds a dangling FAIL reference (decision)" \
    "block" "$(printf '%s' "$HOOK_OUT" | jq -r '.decision // empty')"
  assert_true "should block when the checker finds a dangling FAIL reference (reason names the path)" \
    "printf '%s' \"\$HOOK_OUT\" | jq -r '.reason' | grep -qF 'renamed-away.sh'"
}

it_should_stay_silent_when_its_own_block_caused_this_stop() {
  local repo="$work_dir/fail-repo-loop"
  local settings="$repo/settings.json"
  mkdir -p "$repo"
  printf '{"hooks": {}, "note": "%s/hooks/renamed-away.sh"}' "$repo" > "$settings"

  run_hook '{"session_id": "sess-rg-loop", "stop_hook_active": true}' \
    --repo "$repo" --settings "$settings"

  assert_eq "should stay silent when its own block caused this stop, even with a FAIL fixture" "" "$HOOK_OUT"
}

it_should_stay_silent_when_the_checker_script_is_missing() {
  local isolated_dir="$work_dir/isolated-hooks"
  mkdir -p "$isolated_dir"
  cp "$HOOK" "$isolated_dir/claude-rename-guard-stop-hook.sh"
  # No check-rename-references.py copied alongside -- the wrapper's own
  # dirname-based resolution must find it missing and fail open.

  local repo="$work_dir/fail-repo-missing-checker"
  local settings="$repo/settings.json"
  mkdir -p "$repo"
  printf '{"hooks": {}, "note": "%s/hooks/renamed-away.sh"}' "$repo" > "$settings"

  HOOK_OUT=$(printf '%s' '{"session_id": "sess-rg-nochecker", "stop_hook_active": false}' \
    | bash "$isolated_dir/claude-rename-guard-stop-hook.sh" --repo "$repo" --settings "$settings" 2>/dev/null)

  assert_eq "should stay silent (fail open) when the checker script is missing beside the wrapper" "" "$HOOK_OUT"
}

it_should_stay_silent_on_the_real_corpus_within_the_2_second_budget() {
  # [Fixtures exception] mirrors check-rename-references.test.py's own
  # 2-second-budget corner test: runs against THIS machine's real
  # unix-utils checkout (no --repo/--settings override), proving AC2's
  # pass-through on the actual ~240-WARN corpus with a real test, not by
  # reading the code.
  local start end elapsed
  start=$(date +%s.%N)
  run_hook '{"session_id": "sess-rg-real", "stop_hook_active": false}'
  end=$(date +%s.%N)
  elapsed=$(awk -v s="$start" -v e="$end" 'BEGIN { printf "%.2f", e - s }')

  assert_eq "should stay silent on the real corpus's current WARN-only state" "" "$HOOK_OUT"
  assert_true "should finish the real-corpus scan within the 2-second budget" \
    "awk -v e=\"$elapsed\" 'BEGIN{exit !(e<2.0)}'"
}

it_should_stay_silent_when_the_repo_has_no_dangling_reference
it_should_stay_silent_when_only_a_markdown_warn_finding_exists
it_should_block_when_the_checker_finds_a_dangling_fail_reference
it_should_stay_silent_when_its_own_block_caused_this_stop
it_should_stay_silent_when_the_checker_script_is_missing
it_should_stay_silent_on_the_real_corpus_within_the_2_second_budget

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
