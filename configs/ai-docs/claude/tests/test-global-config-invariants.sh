#!/usr/bin/env bash
# test-global-config-invariants.sh - plain-bash test file
# guarding invariants spread across install.sh and
# settings.json.
#
# Scoped to files an interpreter reads. A group asserting
# CLAUDE.md's prose lived here and was dropped: the actor
# reading a CLAUDE.md is an LLM, so such a check catches an
# edit to the wording and never the behavior it asks for.
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

it_should_record_model_as_sonnet_in_the_committed_settings_json
it_should_fail_when_the_committed_settings_json_carries_an_advisormodel_key

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

# ============================================================
# describe("SubagentCompactionCounterWiring")
# ============================================================

HOOKS_DIR="$repo_root/configs/ai-docs/claude/hooks"
SUBAGENT_BUMP_HOOK="$HOOKS_DIR/resolve-subagent-compaction-bump.py"
DEAD_COMPACT_ROUTER="$HOOKS_DIR/claude-tmux-compact-bump.py"
DEAD_COMPACT_ROUTER_HARNESS="$HOOKS_DIR/tests/test-claude-tmux-compact-bump.sh"

# working_settings - the WORKING-TREE settings.json, unlike the
# committed_settings helper above.
#
# Hook wiring and permissions are never written session by
# session (only /model, /effort and /advisor are), so the
# working tree carries no noise for these keys — and reading it
# is what lets a wiring change be red before its commit lands
# instead of only after.
working_settings() {
  cat "$repo_root/configs/ai-docs/claude/settings.json"
}

subagent_stop_commands() {
  working_settings | jq -r '.hooks.SubagentStop // [] | .[].hooks[].command'
}

session_start_compact_commands() {
  working_settings | jq -r \
    '.hooks.SessionStart[] | select(.matcher == "compact") | .hooks[].command'
}

it_should_run_the_subagent_compaction_bump_hook_when_a_subagent_stops() {
  local actual
  subagent_stop_commands | grep -q 'hooks/resolve-subagent-compaction-bump.py' \
    && actual=true || actual=false
  assert_eq \
    "SubagentCompactionCounterWiring > happy > should run the subagent compaction-bump hook when a subagent stops" \
    "true" "$actual"
}

it_should_ship_the_subagent_compaction_bump_hook_script_the_settings_command_names() {
  local exists
  [ -f "$SUBAGENT_BUMP_HOOK" ] && exists=true || exists=false
  assert_eq \
    "SubagentCompactionCounterWiring > happy > should ship the subagent compaction-bump hook script the settings command names" \
    "true" "$exists"
}

it_should_allow_the_subagent_compaction_bump_hook_path_on_both_macos_and_linux() {
  # Two entries per path form, not one: every other script here
  # is allowed both bare and interpreter-prefixed, because a
  # caller may write either and only the literal string matches.
  local macos linux tilde
  macos=$(working_settings | jq -r '[.permissions.allow[] | select(contains("/Users/brunoagostini/unix-utils/configs/ai-docs/claude/hooks/resolve-subagent-compaction-bump.py"))] | length')
  linux=$(working_settings | jq -r '[.permissions.allow[] | select(contains("/home/brunogsa/unix-utils/configs/ai-docs/claude/hooks/resolve-subagent-compaction-bump.py"))] | length')
  tilde=$(working_settings | jq -r '[.permissions.allow[] | select(contains("~/.claude/hooks/resolve-subagent-compaction-bump.py"))] | length')
  assert_eq \
    "SubagentCompactionCounterWiring > happy > should allow the subagent compaction-bump hook path bare and python3-prefixed on both macOS and Linux" \
    "2 2 2" "$macos $linux $tilde"
}

it_should_bump_the_main_compaction_counter_straight_from_the_title_script_on_a_main_session_compaction() {
  local actual
  session_start_compact_commands | grep -q 'tmux-window-title.sh --bump-counter' \
    && actual=true || actual=false
  assert_eq \
    "SubagentCompactionCounterWiring > happy > should bump the main compaction counter straight from the title script on a main-session compaction" \
    "true" "$actual"
}

it_should_fail_when_the_session_start_compaction_router_is_still_wired() {
  local actual
  session_start_compact_commands | grep -q 'claude-tmux-compact-bump.py' \
    && actual=true || actual=false
  assert_eq \
    "SubagentCompactionCounterWiring > failure > should fail when the SessionStart compaction router is still wired" \
    "false" "$actual"
}

it_should_fail_when_the_dead_session_start_compaction_router_script_survives() {
  local router_exists harness_exists
  [ -f "$DEAD_COMPACT_ROUTER" ] && router_exists=true || router_exists=false
  [ -f "$DEAD_COMPACT_ROUTER_HARNESS" ] && harness_exists=true || harness_exists=false
  assert_eq \
    "SubagentCompactionCounterWiring > failure > should fail when the dead SessionStart compaction router script or its harness survives" \
    "false false" "$router_exists $harness_exists"
}

it_should_run_the_subagent_compaction_bump_hook_when_a_subagent_stops
it_should_ship_the_subagent_compaction_bump_hook_script_the_settings_command_names
it_should_allow_the_subagent_compaction_bump_hook_path_on_both_macos_and_linux
it_should_bump_the_main_compaction_counter_straight_from_the_title_script_on_a_main_session_compaction
it_should_fail_when_the_session_start_compaction_router_is_still_wired
it_should_fail_when_the_dead_session_start_compaction_router_script_survives

# ============================================================
# describe("SuiteExecBitPermissions")
# ============================================================

# suite_exec_bit_violations - tracked suites under the four
# glob trees run-tests.sh discovers by, whose git INDEX mode
# isn't 100755.
#
# A fresh clone materializes exactly the index mode, so a
# filesystem-only chmod would still leave a clone broken.
#
# Enumerated by the same four globs run-tests.sh itself uses
# (never a hardcoded file list) — a hardcoded list reproduces
# the exact registration gap run-tests.sh exists to close.
suite_exec_bit_violations() {
  (cd "$repo_root" && git ls-files -s \
    configs/ai-docs/claude/tests/test-*.sh \
    configs/ai-docs/claude/scripts/tests/test-*.sh \
    configs/ai-docs/claude/hooks/tests/test-*.sh \
    configs/ai-docs/claude/skills/*/scripts/tests/test-*.sh) \
    | awk '$1 != "100755" { print $4 }'
}

it_should_mark_every_run_tests_discovered_suite_executable_in_the_git_index() {
  local actual
  actual=$(suite_exec_bit_violations | sort | tr '\n' ' ' | sed 's/ *$//')
  assert_eq \
    "SuiteExecBitPermissions > happy > should mark every run-tests.sh-discovered suite executable in the git index" \
    "" "$actual"
}

it_should_mark_every_run_tests_discovered_suite_executable_in_the_git_index

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
