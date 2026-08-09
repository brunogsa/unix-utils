#!/usr/bin/env bash
# test-global-config-invariants.sh - plain-bash test file
# guarding invariants spread across install.sh,
# settings.json, and the global CLAUDE.md.
#
# Usage:
#   bash test-global-config-invariants.sh

# Exits 0 when every assertion passes, non-zero otherwise.
#
# No bats dependency by design — a handful of small checks
# don't justify a new cross-platform test-runner dependency
# in install.sh (same precedent as
# configs/ai-docs/claude/hooks/tests/test-claude-git-guard.sh).
#
# Each "describe(...)" comment below marks one test group;
# bash has no native describe/it, so the group name lives in
# a comment and each assertion's description string carries
# the full "Group > case > it" title.
#
# New groups append as a new "describe(...)" section plus a
# new run block, right above the final pass/fail summary.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../../.." && pwd)"
INSTALL_SH="$repo_root/install.sh"

# committed_settings - the last-committed settings.json
# content, so session-scoped /model, /effort and /advisor
# writes in the working tree (repo convention: never
# committed) can never flap these tests.
committed_settings() {
  git -C "$repo_root" show "HEAD:configs/ai-docs/claude/settings.json"
}

pass_count=0
fail_count=0

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

it_should_install_or_symlink_statusline_tier_sh_via_install_sh() {
  local statusline_tier_count
  statusline_tier_count=$(grep -c 'statusline-tier.sh' "$INSTALL_SH")
  assert_eq \
    "InstallScriptContract > happy > should install or symlink statusline-tier.sh via install.sh" \
    "true" "$([ "$statusline_tier_count" -gt 0 ] && echo true || echo false)"
}

it_should_stay_a_no_op_on_re_run_for_the_section_claude_hud_previously_occupied() {
  local marketplace_add plugin_install mkdir_line symlink_line manual_echo
  marketplace_add=$(grep -c 'claude plugin marketplace add jarrodwatts/claude-hud' "$INSTALL_SH")
  plugin_install=$(grep -c 'claude plugin install claude-hud@claude-hud' "$INSTALL_SH")
  mkdir_line=$(grep -c 'mkdir -p ~/.claude/plugins/claude-hud' "$INSTALL_SH")
  symlink_line=$(grep -c 'plugins/claude-hud/config.json' "$INSTALL_SH")
  manual_echo=$(grep -c 'claude-hud:setup' "$INSTALL_SH")
  assert_eq \
    "InstallScriptContract > corner > should stay a no-op on re-run for the section claude-hud previously occupied" \
    "0 0 0 0 0" "$marketplace_add $plugin_install $mkdir_line $symlink_line $manual_echo"
}

it_should_fail_when_any_claude_hud_marketplace_plugin_or_symlink_step_survives() {
  local any_claude_hud
  any_claude_hud=$(grep -ci 'claude-hud' "$INSTALL_SH")
  assert_eq \
    "InstallScriptContract > failure > should fail when any claude-hud marketplace, plugin, or symlink step survives" \
    "0" "$any_claude_hud"
}

it_should_install_ccstatusline_and_ccburn_as_npm_globals
it_should_fail_when_the_orphaned_codeburn_npm_global_install_line_survives
it_should_install_or_symlink_statusline_tier_sh_via_install_sh
it_should_stay_a_no_op_on_re_run_for_the_section_claude_hud_previously_occupied
it_should_fail_when_any_claude_hud_marketplace_plugin_or_symlink_step_survives

# ============================================================
# describe("SettingsEnvContract")
# ============================================================

it_should_set_max_concurrent_subagents_to_the_string_16_in_the_committed_env_block() {
  local actual
  actual=$(committed_settings | jq -r '.env.CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS')
  assert_eq \
    "SettingsEnvContract > happy > should set CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS to the string 16 in the committed env block" \
    "16" "$actual"
}

it_should_keep_the_three_pre_existing_env_keys_intact_alongside_the_new_cap() {
  local actual
  actual=$(committed_settings | jq -r \
    '[.env.CLAUDE_CODE_DISABLE_1M_CONTEXT, .env.CLAUDE_CODE_AUTO_COMPACT_WINDOW, .env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH] | join(" ")')
  assert_eq \
    "SettingsEnvContract > corner > should keep the three pre-existing env keys intact alongside the new cap" \
    "1 200000 4" "$actual"
}

it_should_fail_when_the_committed_env_block_defines_claude_code_subagent_model() {
  local actual
  actual=$(committed_settings | jq -r '.env | has("CLAUDE_CODE_SUBAGENT_MODEL")')
  assert_eq \
    "SettingsEnvContract > failure > should fail when the committed env block defines CLAUDE_CODE_SUBAGENT_MODEL" \
    "false" "$actual"
}

it_should_set_max_concurrent_subagents_to_the_string_16_in_the_committed_env_block
it_should_keep_the_three_pre_existing_env_keys_intact_alongside_the_new_cap
it_should_fail_when_the_committed_env_block_defines_claude_code_subagent_model

# ============================================================
# describe("SubagentCostGuidance")
# ============================================================

CLAUDE_MD="$repo_root/configs/ai-docs/claude/CLAUDE.md"

# subagents_section - the body of CLAUDE.md's "### Subagents"
# section, from its heading to the next heading of any level.
#
# Scoped to the section rather than to the fan-out bullet
# alone: the cost guidance has already been split into a
# second bullet once, and a fixed one-line lookahead from the
# fan-out instruction stopped covering the facts the moment
# it moved. What these assertions actually guard is that the
# subagent guidance states the real cost multiplier and never
# resurrects a debunked lever — wherever in the section it is
# written.
subagents_section() {
  awk '/^### Subagents$/ { inside = 1; next } inside && /^#/ { exit } inside' "$CLAUDE_MD"
}

it_should_state_the_subagent_count_times_per_subagent_cost_multiplier() {
  local has_subagent_count has_per_subagent_cost
  subagents_section | grep -q "subagent count" && has_subagent_count=true || has_subagent_count=false
  subagents_section | grep -q "per-subagent cost" && has_per_subagent_cost=true || has_per_subagent_cost=false
  assert_eq \
    "SubagentCostGuidance > happy > should state the subagent-count times per-subagent-cost multiplier" \
    "true true" "$has_subagent_count $has_per_subagent_cost"
}

it_should_fail_when_the_subagent_guidance_claims_max_thinking_tokens_is_a_usable_cost_lever() {
  local actual
  subagents_section | grep -q "MAX_THINKING_TOKENS" && actual=true || actual=false
  assert_eq \
    "SubagentCostGuidance > failure > should fail when the subagent guidance claims MAX_THINKING_TOKENS is a usable cost lever" \
    "false" "$actual"
}

it_should_fail_when_the_subagent_guidance_claims_effortlevel_high_is_an_above_default_multiplier() {
  local actual
  subagents_section | grep -q "effortLevel" && actual=true || actual=false
  assert_eq \
    "SubagentCostGuidance > failure > should fail when the subagent guidance claims effortLevel high is an above-default multiplier" \
    "false" "$actual"
}

it_should_fail_when_the_subagent_guidance_claims_the_native_rate_limits_stdin_field_is_missing_data() {
  local actual
  subagents_section | grep -q "rate_limits" && actual=true || actual=false
  assert_eq \
    "SubagentCostGuidance > failure > should fail when the subagent guidance claims the native rate_limits stdin field is missing data" \
    "false" "$actual"
}

it_should_state_the_subagent_count_times_per_subagent_cost_multiplier
it_should_fail_when_the_subagent_guidance_claims_max_thinking_tokens_is_a_usable_cost_lever
it_should_fail_when_the_subagent_guidance_claims_effortlevel_high_is_an_above_default_multiplier
it_should_fail_when_the_subagent_guidance_claims_the_native_rate_limits_stdin_field_is_missing_data

# ============================================================
# describe("SettingsModelDefaults")
# ============================================================

it_should_record_model_as_sonnet_in_the_committed_settings_json() {
  local actual
  actual=$(committed_settings | jq -r '.model')
  assert_eq \
    "SettingsModelDefaults > happy > should record model as sonnet in the committed settings.json" \
    "sonnet" "$actual"
}

it_should_fail_when_the_committed_settings_json_carries_an_advisormodel_key() {
  local actual
  actual=$(committed_settings | jq -r 'has("advisorModel")')
  assert_eq \
    "SettingsModelDefaults > failure > should fail when the committed settings.json carries an advisorModel key" \
    "false" "$actual"
}

ROOT_CLAUDE_MD="$repo_root/CLAUDE.md"

# declared_defaults_line - the "declared defaults" sentence
# in the repo's own CLAUDE.md Editing section;
#
# /model, /effort and /advisor writes are expected to
# diverge from it session by session, so only this one
# sentence documents the checked-in baseline.
declared_defaults_line() {
  grep 'declared defaults' "$ROOT_CLAUDE_MD"
}

it_should_fail_when_the_repo_claude_md_declared_defaults_line_still_names_advisormodel_opus() {
  local actual
  declared_defaults_line | grep -q "advisorModel" && actual=true || actual=false
  assert_eq \
    "SettingsModelDefaults > failure > should fail when the repo CLAUDE.md declared-defaults line still names advisorModel opus" \
    "false" "$actual"
}

it_should_record_model_as_sonnet_in_the_committed_settings_json
it_should_fail_when_the_committed_settings_json_carries_an_advisormodel_key
it_should_fail_when_the_repo_claude_md_declared_defaults_line_still_names_advisormodel_opus

# ============================================================
# describe("ClaudeHudRemoval")
# ============================================================

STATUSLINE_SH="$repo_root/configs/ai-docs/claude/scripts/statusline.sh"
CLAUDE_HUD_CONFIG="$repo_root/configs/ai-docs/claude/plugins/claude-hud/config.json"

it_should_point_statuslinecommand_at_the_ccstatusline_invocation() {
  local command has_ccburn has_ccstatusline no_wrapper
  command=$(committed_settings | jq -r '.statusLine.command')
  printf '%s' "$command" | grep -q 'ccburn' && has_ccburn=true || has_ccburn=false
  printf '%s' "$command" | grep -q 'ccstatusline' && has_ccstatusline=true || has_ccstatusline=false
  printf '%s' "$command" | grep -q 'statusline.sh' && no_wrapper=false || no_wrapper=true
  assert_eq \
    "ClaudeHudRemoval > happy > should point statusLine.command at the ccstatusline invocation" \
    "true true true" "$has_ccburn $has_ccstatusline $no_wrapper"
}

it_should_fail_when_scripts_statusline_sh_still_exists() {
  local exists
  [ -f "$STATUSLINE_SH" ] && exists=true || exists=false
  assert_eq \
    "ClaudeHudRemoval > failure > should fail when scripts/statusline.sh still exists" \
    "false" "$exists"
}

it_should_fail_when_enabledplugins_still_lists_claude_hud() {
  local actual
  actual=$(committed_settings | jq -r '.enabledPlugins | has("claude-hud@claude-hud")')
  assert_eq \
    "ClaudeHudRemoval > failure > should fail when enabledPlugins still lists claude-hud" \
    "false" "$actual"
}

it_should_fail_when_the_plugins_claude_hud_config_file_still_exists() {
  local exists
  [ -f "$CLAUDE_HUD_CONFIG" ] && exists=true || exists=false
  assert_eq \
    "ClaudeHudRemoval > failure > should fail when the plugins claude-hud config file still exists" \
    "false" "$exists"
}

it_should_fail_when_extraknownmarketplaces_still_lists_claude_hud() {
  local actual
  actual=$(committed_settings | jq -r '.extraKnownMarketplaces | has("claude-hud")')
  assert_eq \
    "ClaudeHudRemoval > failure > should fail when extraKnownMarketplaces still lists claude-hud" \
    "false" "$actual"
}

it_should_point_statuslinecommand_at_the_ccstatusline_invocation
it_should_fail_when_scripts_statusline_sh_still_exists
it_should_fail_when_enabledplugins_still_lists_claude_hud
it_should_fail_when_the_plugins_claude_hud_config_file_still_exists
it_should_fail_when_extraknownmarketplaces_still_lists_claude_hud

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
