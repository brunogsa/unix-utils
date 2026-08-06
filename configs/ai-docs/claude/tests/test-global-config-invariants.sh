#!/usr/bin/env bash
# test-global-config-invariants.sh - plain-bash test file guarding invariants
# spread across install.sh, settings.json, and the global CLAUDE.md.
#
# Usage:
#   bash test-global-config-invariants.sh
#
# Exits 0 when every assertion passes, non-zero otherwise. No bats dependency
# by design — a handful of small checks don't justify a new cross-platform
# test-runner dependency in install.sh (same precedent as
# configs/ai-docs/claude/hooks/tests/test-claude-git-guard.sh).
#
# Each "describe(...)" comment below marks one test group; bash has no
# native describe/it, so the group name lives in a comment and each
# assertion's description string carries the full "Group > case > it"
# title. New groups append as a new "describe(...)" section plus a new
# run block, right above the final pass/fail summary.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"
INSTALL_SH="$repo_root/install.sh"

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

# ============================================================
# describe("InstallScriptContract")
# ============================================================

it_should_install_ccstatusline_and_ccburn_as_npm_globals() {
  local ccstatusline_count ccburn_count
  ccstatusline_count=$(grep -c '^npm install -g ccstatusline$' "$INSTALL_SH")
  ccburn_count=$(grep -c '^npm install -g ccburn$' "$INSTALL_SH")
  assert_eq \
    "InstallScriptContract > happy > should install ccstatusline and ccburn as npm globals" \
    "1 1" "$ccstatusline_count $ccburn_count"
}

it_should_fail_when_the_orphaned_codeburn_npm_global_install_line_survives() {
  local codeburn_count
  codeburn_count=$(grep -c '^npm install -g codeburn$' "$INSTALL_SH")
  assert_eq \
    "InstallScriptContract > failure > should fail when the orphaned codeburn npm global install line survives" \
    "0" "$codeburn_count"
}

it_should_install_ccstatusline_and_ccburn_as_npm_globals
it_should_fail_when_the_orphaned_codeburn_npm_global_install_line_survives

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
