#!/usr/bin/env bash
# test-statusline-tier.sh - plain-bash test file for statusline-tier.sh, the
# tier-read and pacing-arithmetic segment behind the ccstatusline Custom
# Command widget (the only custom code the claude-cost-controls plan adds).
#
# Usage:
#   bash test-statusline-tier.sh
#
# No bats dependency by design — same precedent as
# configs/ai-docs/claude/hooks/tests/test-claude-git-guard.sh and
# configs/ai-docs/claude/tests/test-global-config-invariants.sh.
#
# Every fixture below runs under a scratch $HOME plus explicit
# STATUSLINE_* path overrides, and PATH is prepended with a fake `security`
# binary per test — the real ~/.claude/.credentials.json, the real login
# Keychain, and the real ~/.claude/.statusline-tier-cache are never touched.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../statusline-tier.sh"

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

# fresh_sandbox - a scratch dir for one test's $HOME, cache, credentials
# file and fake-binary PATH prepend, torn down by the caller when done.
fresh_sandbox() {
  mktemp -d "${TMPDIR:-/tmp}/statusline-tier-test.XXXXXX"
}

# write_fake_security - installs a fake `security` binary at
# "$bin_dir/security" ahead of PATH so tests never shell out to the real
# macOS Keychain. $mdat is the attribute-read fixture value (YYYYMMDDHHMMSSZ
# format matching real `security find-generic-password` output). $mode
# selects the -w (secret) response: a literal JSON blob, or "hang" to
# simulate a blocking Keychain password-prompt dialog.
write_fake_security() {
  local bin_dir="$1" mdat="$2" mode="$3"
  cat >"$bin_dir/security" <<EOF
#!/usr/bin/env bash
case "\$*" in
  *" -w"*)
    if [ "$mode" = "hang" ]; then
      exec sleep 999999
    fi
    printf '%s' '$mode'
    ;;
  *)
    printf 'keychain: "Claude Code-credentials"\nclass: "genp"\nattributes:\n    "cdat"<timedate>=$mdat\n    "mdat"<timedate>=$mdat\n'
    ;;
esac
EOF
  chmod +x "$bin_dir/security"
}

# ============================================================
# describe("StatusLineTierSegment")
# ============================================================

it_should_read_subscriptiontype_from_the_credentials_file_when_one_exists() {
  local sandbox actual
  sandbox="$(fresh_sandbox)"
  printf '{"subscriptionType":"enterprise"}' >"$sandbox/credentials.json"

  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/credentials.json" \
      PATH="/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c 'source "$0"; read_subscription_tier' "$SCRIPT_UNDER_TEST"
  )

  assert_eq \
    "StatusLineTierSegment > happy > should read subscriptionType from the credentials file when one exists" \
    "enterprise" "$actual"
  rm -rf "$sandbox"
}

it_should_read_subscriptiontype_from_the_login_keychain_when_no_credentials_file_exists() {
  local sandbox actual
  sandbox="$(fresh_sandbox)"
  write_fake_security "$sandbox" "20260730082118Z" '{"subscriptionType":"max"}'

  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; read_subscription_tier' "$SCRIPT_UNDER_TEST"
  )

  assert_eq \
    "StatusLineTierSegment > happy > should read subscriptionType from the login Keychain when no credentials file exists" \
    "max" "$actual"
  rm -rf "$sandbox"
}

it_should_invalidate_the_cached_tier_against_the_keychain_mdat_attribute_on_macos() {
  local sandbox actual
  sandbox="$(fresh_sandbox)"
  # No credentials file at all: this host-independent, existence-based
  # branch is what actually forces the Keychain/mdat code path — see
  # decision #3 in /tmp/implement_substeps_claude-cost-controls_6.md for
  # why this is not gated on `uname`.
  write_fake_security "$sandbox" "20260730082118Z" '{"subscriptionType":"max"}'
  printf '100 stale-tier\n' >"$sandbox/tier-cache"

  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/tier-cache" \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )

  assert_eq \
    "StatusLineTierSegment > corner > should invalidate the cached tier against the Keychain mdat attribute on macOS" \
    "max" "$actual"
  rm -rf "$sandbox"
}

it_should_invalidate_the_cached_tier_against_the_credentials_file_mtime_on_linux() {
  local sandbox actual
  sandbox="$(fresh_sandbox)"
  # This exercises the credentials-file/mtime branch via a faked file, not
  # a live Linux run (this dev host is macOS) — see decision #3.
  printf '{"subscriptionType":"pro"}' >"$sandbox/credentials.json"
  printf '100 stale-tier\n' >"$sandbox/tier-cache"
  touch -t "203001010000" "$sandbox/tier-cache" >/dev/null 2>&1
  touch "$sandbox/credentials.json"

  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/tier-cache" \
      PATH="/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )

  assert_eq \
    "StatusLineTierSegment > corner > should invalidate the cached tier against the credentials file mtime on Linux" \
    "pro" "$actual"
  rm -rf "$sandbox"
}

it_should_treat_a_missing_cache_as_infinitely_stale_and_perform_a_fresh_read() {
  local sandbox actual cache_contents
  sandbox="$(fresh_sandbox)"
  printf '{"subscriptionType":"team"}' >"$sandbox/credentials.json"

  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/nonexistent-cache" \
      PATH="/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )
  cache_contents=$(cat "$sandbox/nonexistent-cache" 2>/dev/null | awk '{print $2}')

  assert_eq \
    "StatusLineTierSegment > corner > should treat a missing ~/.claude/.statusline-tier-cache as infinitely stale and perform a fresh read" \
    "team team" "$actual $cache_contents"
  rm -rf "$sandbox"
}

it_should_re_read_subscriptiontype_when_the_invalidation_timestamp_is_newer_than_the_cache() {
  local sandbox first second
  sandbox="$(fresh_sandbox)"
  printf '{"subscriptionType":"old-tier"}' >"$sandbox/credentials.json"
  touch -t "202001010000" "$sandbox/credentials.json"
  # Cache epoch equal to the credentials file's own mtime: NOT older, so a
  # correct implementation must serve the cache unchanged rather than
  # re-read (proves the comparison is conditional, not an unconditional
  # re-read every call).
  printf '%s old-tier\n' "$(stat -f %m "$sandbox/credentials.json" 2>/dev/null || stat -c %Y "$sandbox/credentials.json")" \
    >"$sandbox/tier-cache"

  first=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/tier-cache" \
      PATH="/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )

  # Now advance the credentials file's mtime strictly past the cached
  # epoch, and change its content: a correct implementation must re-read.
  sleep 1
  printf '{"subscriptionType":"new-tier"}' >"$sandbox/credentials.json"

  second=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/tier-cache" \
      PATH="/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )

  assert_eq \
    "StatusLineTierSegment > corner > should re-read subscriptionType when the invalidation timestamp is newer than the cache" \
    "old-tier new-tier" "$first $second"
  rm -rf "$sandbox"
}

it_should_omit_the_tier_segment_rather_than_block_on_a_password_prompt() {
  local sandbox start end elapsed actual status
  sandbox="$(fresh_sandbox)"
  write_fake_security "$sandbox" "20260730082118Z" "hang"

  start=$(date +%s)
  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      STATUSLINE_KEYCHAIN_TIMEOUT_SECS=1 \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; read_subscription_tier_from_keychain; echo "status=$?"' "$SCRIPT_UNDER_TEST"
  )
  end=$(date +%s)
  elapsed=$((end - start))
  status=$(printf '%s\n' "$actual" | grep -o 'status=[0-9]*')

  if [ "$elapsed" -le 3 ] && [ "$status" != "status=0" ]; then
    actual="bounded-and-failed"
  else
    actual="elapsed=${elapsed}s $status"
  fi

  assert_eq \
    "StatusLineTierSegment > failure > should omit the tier segment rather than block when the Keychain read would prompt for a password" \
    "bounded-and-failed" "$actual"
  rm -rf "$sandbox"
}

it_should_never_write_the_raw_credential_value_anywhere() {
  local sandbox marker captured leaked_in_output leaked_in_tmp
  sandbox="$(fresh_sandbox)"
  marker="RAW-SECRET-MARKER-do-not-leak-9f31"
  write_fake_security "$sandbox" "20260730082118Z" "{\"subscriptionType\":\"max\",\"raw\":\"$marker\"}"

  mkdir -p "$sandbox/scoped-tmp"
  captured=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      TMPDIR="$sandbox/scoped-tmp" \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; read_subscription_tier_from_keychain' "$SCRIPT_UNDER_TEST" 2>&1
  )

  leaked_in_output="no"
  printf '%s' "$captured" | grep -q "$marker" && leaked_in_output="yes"

  leaked_in_tmp="no"
  grep -rl "$marker" "$sandbox/scoped-tmp" >/dev/null 2>&1 && leaked_in_tmp="yes"

  assert_eq \
    "StatusLineTierSegment > failure > should never write the raw credential value to stdout, stderr or any log" \
    "max no no" "$captured $leaked_in_output $leaked_in_tmp"
  rm -rf "$sandbox"
}

it_should_read_subscriptiontype_from_the_credentials_file_when_one_exists
it_should_read_subscriptiontype_from_the_login_keychain_when_no_credentials_file_exists
it_should_invalidate_the_cached_tier_against_the_keychain_mdat_attribute_on_macos
it_should_invalidate_the_cached_tier_against_the_credentials_file_mtime_on_linux
it_should_treat_a_missing_cache_as_infinitely_stale_and_perform_a_fresh_read
it_should_re_read_subscriptiontype_when_the_invalidation_timestamp_is_newer_than_the_cache
it_should_omit_the_tier_segment_rather_than_block_on_a_password_prompt
it_should_never_write_the_raw_credential_value_anywhere

# ============================================================
# describe("StatusLinePacingSegment")
# ============================================================

it_should_compute_expected_percent_as_elapsed_divided_by_window_length() {
  local actual
  actual=$(bash -c 'source "$0"; compute_expected_percent 12960 18000' "$SCRIPT_UNDER_TEST")
  assert_eq \
    "StatusLinePacingSegment > should compute expected percent as elapsed window time divided by total window length" \
    "72" "$actual"
}

it_should_report_expected_percent_as_zero_at_a_rolling_window_reset() {
  local actual
  actual=$(bash -c 'source "$0"; compute_expected_percent 0 18000' "$SCRIPT_UNDER_TEST")
  assert_eq \
    "StatusLinePacingSegment > should report expected percent as zero at the instant a rolling window resets" \
    "0" "$actual"
}

it_should_report_session_duration_in_whole_hours_from_the_session_start_time() {
  local start now actual
  now=1785400000
  start=$((now - 2 * 3600 - 1500))
  actual=$(bash -c 'source "$0"; compute_session_duration_hours "$1" "$2"' "$SCRIPT_UNDER_TEST" "$start" "$now")
  assert_eq \
    "StatusLinePacingSegment > should report session duration in whole hours from the session start time" \
    "2" "$actual"
}

it_should_compute_expected_percent_as_elapsed_divided_by_window_length
it_should_report_expected_percent_as_zero_at_a_rolling_window_reset
it_should_report_session_duration_in_whole_hours_from_the_session_start_time

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
