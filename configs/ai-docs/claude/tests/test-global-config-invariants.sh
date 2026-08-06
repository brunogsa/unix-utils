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

# committed_settings - the last-committed settings.json content, so
# session-scoped /model, /effort and /advisor writes in the working
# tree (repo convention: never committed) can never flap these tests.
committed_settings() {
  git -C "$repo_root" show "HEAD:configs/ai-docs/claude/settings.json"
}

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

# ============================================================
# describe("SettingsEnvContract")
# ============================================================

it_should_set_max_concurrent_subagents_to_the_string_8_in_the_committed_env_block() {
  local actual
  actual=$(committed_settings | jq -r '.env.CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS')
  assert_eq \
    "SettingsEnvContract > happy > should set CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS to the string 8 in the committed env block" \
    "8" "$actual"
}

it_should_keep_the_three_pre_existing_env_keys_intact_alongside_the_new_cap() {
  local actual
  actual=$(committed_settings | jq -r \
    '[.env.CLAUDE_CODE_DISABLE_1M_CONTEXT, .env.CLAUDE_CODE_AUTO_COMPACT_WINDOW, .env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH] | join(" ")')
  assert_eq \
    "SettingsEnvContract > corner > should keep the three pre-existing env keys intact alongside the new cap" \
    "1 200000 3" "$actual"
}

it_should_fail_when_the_committed_env_block_defines_claude_code_subagent_model() {
  local actual
  actual=$(committed_settings | jq -r '.env | has("CLAUDE_CODE_SUBAGENT_MODEL")')
  assert_eq \
    "SettingsEnvContract > failure > should fail when the committed env block defines CLAUDE_CODE_SUBAGENT_MODEL" \
    "false" "$actual"
}

it_should_set_max_concurrent_subagents_to_the_string_8_in_the_committed_env_block
it_should_keep_the_three_pre_existing_env_keys_intact_alongside_the_new_cap
it_should_fail_when_the_committed_env_block_defines_claude_code_subagent_model

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
