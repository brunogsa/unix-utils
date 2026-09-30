#!/usr/bin/env bash

# test-detect-modules.sh - plain-bash test file for
# detect-modules.sh, the shared Arco/Linear presence check.

# Usage:
#   bash test-detect-modules.sh

# Every fixture is a throwaway settings file under a scratch
# dir, passed via CLAUDE_SETTINGS. The real settings.json is
# never read or written.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../detect-modules.sh"

scratch="$(mktemp -d "${TMPDIR:-/tmp}/detect-modules-test.XXXXXX")"
trap 'rm -rf "$scratch"' EXIT

pass_count=0
fail_count=0

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

# run_against - run the script with CLAUDE_SETTINGS=$1; sets
# $output (stdout, lines joined by a space) and $status.
run_against() {
  output="$(CLAUDE_SETTINGS="$1" bash "$SCRIPT_UNDER_TEST" 2>/dev/null | tr '\n' ' ')"
  status=${PIPESTATUS[0]}
}

write_fixture() {
  local name="$1" body="$2"
  printf '%s\n' "$body" > "$scratch/$name"
  printf '%s\n' "$scratch/$name"
}

fixture="$(write_fixture both-present.json '{"enabledPlugins":{"core@arco-ai-plugins":true,"audit@arco-ai-plugins":false,"linear@claude-plugins-official":true}}')"
run_against "$fixture"
assert_eq "should report Arco and Linear present when both plugins are enabled" "arco=true linear=true " "$output"
assert_eq "should exit 0 when both modules are present" "0" "$status"

fixture="$(write_fixture neither-key.json '{"enabledPlugins":{"frontend-design@claude-plugins-official":true}}')"
run_against "$fixture"
assert_eq "should report both absent when neither module key exists" "arco=false linear=false " "$output"
assert_eq "should exit 0 when neither module key exists" "0" "$status"

fixture="$(write_fixture all-false.json '{"enabledPlugins":{"core@arco-ai-plugins":false,"sdd@arco-ai-plugins":false,"linear@claude-plugins-official":false}}')"
run_against "$fixture"
assert_eq "should report both absent when every module key is disabled" "arco=false linear=false " "$output"

fixture="$(write_fixture arco-only.json '{"enabledPlugins":{"audit@arco-ai-plugins":false,"sdk@arco-ai-plugins":true}}')"
run_against "$fixture"
assert_eq "should report Arco present and Linear absent when one Arco plugin is enabled among disabled ones" "arco=true linear=false " "$output"

fixture="$(write_fixture linear-only.json '{"enabledPlugins":{"linear@claude-plugins-official":true}}')"
run_against "$fixture"
assert_eq "should report Linear present and Arco absent when only the Linear plugin is enabled" "arco=false linear=true " "$output"

fixture="$(write_fixture no-enabled-plugins.json '{"model":"sonnet"}')"
run_against "$fixture"
assert_eq "should report both absent when enabledPlugins is missing" "arco=false linear=false " "$output"
assert_eq "should exit 0 when enabledPlugins is missing" "0" "$status"

run_against "$scratch/does-not-exist.json"
assert_eq "should report both absent when the settings file is missing" "arco=false linear=false " "$output"
assert_eq "should exit 0 when the settings file is missing" "0" "$status"

fixture="$(write_fixture malformed.json '{"enabledPlugins": {"core@arco-ai-plugins": tru')"
run_against "$fixture"
assert_eq "should report both absent when the settings file is malformed JSON" "arco=false linear=false " "$output"
assert_eq "should exit 0 when the settings file is malformed JSON" "0" "$status"

fixture="$(write_fixture unreadable.json '{"enabledPlugins":{"core@arco-ai-plugins":true}}')"
chmod 000 "$fixture"
run_against "$fixture"
chmod 600 "$fixture"
assert_eq "should report both absent when the settings file is unreadable" "arco=false linear=false " "$output"
assert_eq "should exit 0 when the settings file is unreadable" "0" "$status"

stderr_output="$(CLAUDE_SETTINGS="$scratch/malformed.json" bash "$SCRIPT_UNDER_TEST" 2>&1 >/dev/null)"
assert_eq "should warn on stderr that it cannot read the settings file when it is malformed JSON" "detect-modules.sh: cannot read $scratch/malformed.json - reporting both modules absent" "$stderr_output"

mkdir -p "$scratch/no-jq-bin"
stderr_output="$(PATH="$scratch/no-jq-bin" CLAUDE_SETTINGS="$scratch/both-present.json" "$BASH" "$SCRIPT_UNDER_TEST" 2>&1 >/dev/null)"
assert_eq "should warn on stderr that it cannot read the settings file when jq is not installed" "detect-modules.sh: cannot read $scratch/both-present.json - reporting both modules absent" "$stderr_output"

stderr_output="$(CLAUDE_SETTINGS="$scratch/both-present.json" bash "$SCRIPT_UNDER_TEST" 2>&1 >/dev/null)"
assert_eq "should stay silent on stderr when the settings file is readable" "" "$stderr_output"

stderr_output="$(CLAUDE_SETTINGS="$scratch/does-not-exist.json" bash "$SCRIPT_UNDER_TEST" 2>&1 >/dev/null)"
assert_eq "should stay silent on stderr when the settings file does not exist" "" "$stderr_output"

mkdir -p "$scratch/home/.claude"
printf '%s\n' '{"enabledPlugins":{"core@arco-ai-plugins":true}}' > "$scratch/home/.claude/settings.json"
output="$(HOME="$scratch/home" CLAUDE_SETTINGS= bash "$SCRIPT_UNDER_TEST" 2>/dev/null | tr '\n' ' ')"
assert_eq "should read the settings file under HOME when CLAUDE_SETTINGS is unset" "arco=true linear=false " "$output"

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
