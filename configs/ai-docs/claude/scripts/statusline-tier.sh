#!/usr/bin/env bash
# statusline-tier.sh - tier and pacing segment for the
# ccstatusline Custom Command widget.
#
# The only custom code the claude-cost-controls plan adds:
# the fields no community ccstatusline widget owns (tier,
# advisor, session duration, and the two expected% pacing
# figures).
#
# Usage (as a ccstatusline Custom Command, fed Claude Code's
# full statusline JSON on stdin).
#
#   statusline-tier.sh tier
#     cached/fresh subscriptionType.
#
#   statusline-tier.sh advisor
#     advisorModel, or the literal "none".
#
#   statusline-tier.sh duration
#     whole-hour session length, read from
#     cost.total_duration_ms on stdin.
#
#   statusline-tier.sh expected5h
#     5h-window expected-pace percent, from
#     rate_limits.five_hour.resets_at on stdin.
#
#   statusline-tier.sh expected7d
#     7d-window expected-pace percent, from
#     rate_limits.seven_day.resets_at on stdin.
#
# Tier source: if ~/.claude/.credentials.json exists (the
# Linux case), it is read directly and its mtime is the
# cache-invalidation signal.
#
# Otherwise (the macOS case: credentials live in the login
# Keychain, not that file), the tier comes from `security
# find-generic-password -s "Claude Code-credentials"`.
#
# That command supplies both the invalidation signal (the
# "mdat" attribute, read without a password prompt) and, via
# the `-w` flag, the actual secret.
#
# Branching is existence-based, not `uname`-based, so both
# code paths are exercised the same way regardless of host
# OS.
#
# SECURITY: the `-w` Keychain read returns a live secret.
#
# Only the derived tier string extracted from it ever leaves
# this script - the raw credential is never printed, logged,
# or left on disk, and it never touches disk at all:
# `security ... -w` is piped straight into `jq`.
#
# So there is no window - not even one an interrupted
# cleanup step could miss - where the secret exists as a
# file.
#
# Sourced (not executed) by its test file to unit-test each
# function in isolation, via the `(return 0 2>/dev/null)`
# sourced-detection idiom below - that only fires main()
# when the file is actually executed.

set -uo pipefail

readonly KEYCHAIN_SERVICE="Claude Code-credentials"
: "${STATUSLINE_KEYCHAIN_TIMEOUT_SECS:=3}"

# ----------------------------------------------------------
# Injectable paths - default to the real locations.
#
# Every path is overridable via env var so tests never touch
# the real ~/.claude/.credentials.json,
# ~/.claude/.statusline-tier-cache, Keychain, or settings.json.
# ----------------------------------------------------------

credentials_file_path() {
  printf '%s\n' "${STATUSLINE_CREDENTIALS_FILE:-$HOME/.claude/.credentials.json}"
}

tier_cache_path() {
  printf '%s\n' "${STATUSLINE_TIER_CACHE:-$HOME/.claude/.statusline-tier-cache}"
}

claude_settings_path() {
  printf '%s\n' "${STATUSLINE_SETTINGS_FILE:-$HOME/.claude/settings.json}"
}

# ----------------------------------------------------------
# run_with_timeout - portable bash-only timeout wrapper.
#
# It takes no `timeout`/`gtimeout` dependency, since a fresh
# macOS clone following this repo's own install.sh is not
# guaranteed to have coreutils installed.
#
# It backgrounds the command, races a watchdog subshell that
# SIGTERMs it after N seconds, and returns the command's own
# exit status when it finishes first.
#
# The watchdog is redirected to /dev/null on all three fds
# rather than left to inherit the caller's.
#
# Without that, a caller piping this function's stdout into
# another command (e.g. `security ... | jq`) hands the
# watchdog a copy of the pipe's write end.
#
# Killing the watchdog's own pid on the success path does
# not reach its `sleep` grandchild, which is then left
# orphaned still holding that write end open.
#
# So the downstream reader blocks for the full timeout
# waiting for EOF even though the real command already
# finished.
# ----------------------------------------------------------

run_with_timeout() {
  local timeout_secs="$1"
  shift
  "$@" &
  local cmd_pid=$!
  (
    sleep "$timeout_secs"
    kill -0 "$cmd_pid" 2>/dev/null && kill -TERM "$cmd_pid" 2>/dev/null
  ) </dev/null >/dev/null 2>&1 &
  local watchdog_pid=$!
  local status=0
  wait "$cmd_pid" 2>/dev/null || status=$?
  kill "$watchdog_pid" 2>/dev/null
  wait "$watchdog_pid" 2>/dev/null
  return "$status"
}

# ----------------------------------------------------------
# Keychain-backed tier read (macOS)
# ----------------------------------------------------------

# parse_keychain_timestamp - converts a Keychain
# "mdat"/"cdat" timestamp (YYYYMMDDHHMMSSZ, always UTC) to
# epoch seconds.
#
# It tries macOS's BSD `date -j -f` first, and falls back to
# GNU `date -d` so this also works if ever run under a Linux
# host that happens to have Keychain-shaped fixtures (e.g.
# this repo's own faked-fixture tests).
parse_keychain_timestamp() {
  local raw="$1" y m d H M S
  y="${raw:0:4}"
  m="${raw:4:2}"
  d="${raw:6:2}"
  H="${raw:8:2}"
  M="${raw:10:2}"
  S="${raw:12:2}"
  date -u -j -f '%Y-%m-%d %H:%M:%S' "$y-$m-$d $H:$M:$S" '+%s' 2>/dev/null \
    || date -u -d "$y-$m-$d $H:$M:$S" '+%s' 2>/dev/null
}

# keychain_mdat_epoch - the Keychain entry's "mdat"
# (modification date) attribute as epoch seconds.
#
# It is read without the -w flag so this never prompts for a
# password (attribute reads don't require unlocking the
# secret itself).
keychain_mdat_epoch() {
  local attrs status mdat_raw
  attrs="$(run_with_timeout "$STATUSLINE_KEYCHAIN_TIMEOUT_SECS" \
    security find-generic-password -s "$KEYCHAIN_SERVICE" 2>&1 </dev/null)"
  status=$?
  [ "$status" -ne 0 ] && return 1
  mdat_raw="$(printf '%s\n' "$attrs" | grep '"mdat"' | grep -oE '[0-9]{14}Z' | head -1)"
  [ -z "$mdat_raw" ] && return 1
  parse_keychain_timestamp "$mdat_raw"
}

# read_subscription_tier_from_keychain - the one place in
# this script that uses the -w flag to read the actual
# secret.
#
# The secret is piped straight from `security` into `jq` and
# never touches disk, closing a gap an earlier
# chmod-600-mktemp-file version had.
#
# An external SIGTERM (e.g. ccstatusline's own execSync
# timeout) landing between the write and an explicit `rm -f`
# cleanup step would have left the secret on disk, since
# bash runs no cleanup at all once a signal kills it.
#
# `set -o pipefail` (set once, at file scope) is what makes
# `status=$?` below reflect either side of the pipe failing,
# not just jq's own.
#
# Nothing derived from the secret other than the tier string
# is ever assigned to a variable, printed, or left on disk.
read_subscription_tier_from_keychain() {
  local tier status
  tier="$(
    run_with_timeout "$STATUSLINE_KEYCHAIN_TIMEOUT_SECS" \
      security find-generic-password -s "$KEYCHAIN_SERVICE" -w \
      </dev/null 2>/dev/null \
      | jq -r '.claudeAiOauth.subscriptionType // .subscriptionType // empty' 2>/dev/null
  )"
  status=$?
  [ "$status" -ne 0 ] && return 1
  [ -z "$tier" ] && return 1
  printf '%s\n' "$tier"
}

# ----------------------------------------------------------
# Credentials-file-backed tier read (Linux, or any host
# where the file happens to exist)
# ----------------------------------------------------------

stat_mtime_epoch() {
  local path="$1"

  # GNU coreutils first: its `-c %Y` fails cleanly on BSD
  # (`-c` isn't a BSD stat flag), so BSD falls through to
  # `-f %m` below.
  #
  # The reverse order is unsafe: GNU's `-f` isn't a format
  # flag, it's the boolean `--file-system` flag, which
  # succeeds and prints a multi-line filesystem dump instead
  # of failing into the fallback.
  stat -c %Y "$path" 2>/dev/null || stat -f %m "$path" 2>/dev/null
}

# credential_store_timestamp - the OS-appropriate
# invalidation signal: the credentials file's mtime if it
# exists, else the Keychain entry's mdat.
#
# Branching is existence-based (matches this segment's own
# fallback rule below), not a `uname` check.
credential_store_timestamp() {
  local creds_file
  creds_file="$(credentials_file_path)"
  if [ -f "$creds_file" ]; then
    stat_mtime_epoch "$creds_file"
  else
    keychain_mdat_epoch
  fi
}

# read_subscription_tier - reads subscriptionType from
# ~/.claude/.credentials.json when it exists, else falls
# back to the Keychain.
read_subscription_tier() {
  local creds_file
  creds_file="$(credentials_file_path)"
  if [ -f "$creds_file" ]; then
    jq -r '.claudeAiOauth.subscriptionType // .subscriptionType // empty' "$creds_file" 2>/dev/null
  else
    read_subscription_tier_from_keychain
  fi
}

# ----------------------------------------------------------
# Cache: <credential-store-timestamp> <tier-string>, one line
# ----------------------------------------------------------

write_tier_cache() {
  local epoch="$1" tier="$2" cache_file tmp
  cache_file="$(tier_cache_path)"
  tmp="$(mktemp "${cache_file}.XXXXXX")" || return 1
  printf '%s %s\n' "$epoch" "$tier" >"$tmp"
  mv -f "$tmp" "$cache_file"
}

# resolve_tier - the full read: compares the credential
# store's invalidation timestamp against the cached epoch.
#
# A missing cache file is infinitely stale (cached_epoch
# stays empty, so the "not newer" guard below can never be
# true) and always forces a fresh read.
#
# A store timestamp newer than the cache re-reads and
# rewrites the cache; an equal-or-older one serves the
# cached tier unchanged.
resolve_tier() {
  local cache_file store_ts cached_epoch cached_tier fresh_tier

  store_ts="$(credential_store_timestamp)"
  [ -z "$store_ts" ] && return 1

  cache_file="$(tier_cache_path)"
  cached_epoch=""
  cached_tier=""
  if [ -f "$cache_file" ]; then
    read -r cached_epoch cached_tier <"$cache_file"
  fi

  if [ -n "$cached_epoch" ] && [ "$store_ts" -le "$cached_epoch" ]; then
    printf '%s\n' "$cached_tier"
    return 0
  fi

  fresh_tier="$(read_subscription_tier)" || return 1
  [ -z "$fresh_tier" ] && return 1
  write_tier_cache "$store_ts" "$fresh_tier"
  printf '%s\n' "$fresh_tier"
}

# ----------------------------------------------------------
# Advisor field
# ----------------------------------------------------------

# read_advisor_field - the configured advisorModel, or the
# literal string "none" when unset (matches this repo's own
# default: the committed settings.json carries no
# advisorModel key).
read_advisor_field() {
  local settings_file
  settings_file="$(claude_settings_path)"
  if [ -f "$settings_file" ]; then
    jq -r '.advisorModel // "none"' "$settings_file" 2>/dev/null || printf 'none\n'
  else
    printf 'none\n'
  fi
}

# ----------------------------------------------------------
# Pacing arithmetic (pure functions, no I/O)
# ----------------------------------------------------------

# compute_expected_percent - (elapsed time in the rolling
# window / total window length) x 100, as a whole-number
# percent.
#
# Zero window length (should never happen, but a defensive
# guard beats a divide-by-zero) reports 0 rather than
# erroring.
compute_expected_percent() {
  local elapsed_secs="$1" window_secs="$2"
  if [ "$window_secs" -le 0 ]; then
    printf '0\n'
    return
  fi
  awk -v e="$elapsed_secs" -v w="$window_secs" 'BEGIN { printf "%.0f\n", (e / w) * 100 }'
}

# expected_percent_from_resets_at - converts a rolling
# window's `resets_at` epoch into elapsed-so-far seconds,
# then delegates to compute_expected_percent.
#
# `resets_at` is the only timestamp Claude Code's stdin
# payload carries for rate_limits.{five_hour,seven_day} -
# confirmed by reading ccstatusline's own StatusJSONSchema,
# no elapsed/window-start field exists.
#
# A resets_at already in the past (elapsed would exceed
# window_secs, e.g. a stale/late read) is clamped to
# window_secs rather than reporting over 100%.
expected_percent_from_resets_at() {
  local resets_at="$1" window_secs="$2" now elapsed
  now="$(date +%s)"
  elapsed=$((window_secs - (resets_at - now)))
  [ "$elapsed" -lt 0 ] && elapsed=0
  [ "$elapsed" -gt "$window_secs" ] && elapsed="$window_secs"
  compute_expected_percent "$elapsed" "$window_secs"
}

# compute_session_duration_hours - whole hours elapsed
# between the session's start and now, floored (not rounded)
# to match ccstatusline's own convention of truncating
# partial units.
compute_session_duration_hours() {
  local start_epoch="$1" now_epoch="$2" elapsed_secs
  elapsed_secs=$((now_epoch - start_epoch))
  [ "$elapsed_secs" -lt 0 ] && elapsed_secs=0
  printf '%d\n' $((elapsed_secs / 3600))
}

# ----------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------

usage() {
  cat <<'EOF'
statusline-tier.sh - tier and pacing segment for the ccstatusline Custom
Command widget

Usage:
  statusline-tier.sh tier       Print the cached/fresh subscriptionType.
  statusline-tier.sh advisor    Print advisorModel, or "none" if unset.
  statusline-tier.sh duration   Print whole-hour session duration, reading
                                 cost.total_duration_ms from the Claude
                                 Code statusline JSON on stdin.
  statusline-tier.sh expected5h Print the 5h-window expected-pace percent,
                                 reading rate_limits.five_hour.resets_at
                                 from stdin.
  statusline-tier.sh expected7d Print the 7d-window expected-pace percent,
                                 reading rate_limits.seven_day.resets_at
                                 from stdin.

Examples:
  statusline-tier.sh tier
  echo '{"cost":{"total_duration_ms":7500000}}' | statusline-tier.sh duration
  echo '{"rate_limits":{"five_hour":{"resets_at":1785405040}}}' \
    | statusline-tier.sh expected5h
EOF
}

main() {
  case "${1:-}" in
    tier)
      # Capitalized here, not inside resolve_tier(), so the
      # cached/compared value stays lowercase (matching
      # read_subscription_tier's raw subscriptionType) and
      # only the CLI's rendered output changes.
      #
      # `awk` rather than bash's `${var^}` since this script
      # targets both macOS's stock bash 3.2 (no `^`
      # capitalization operator) and Linux.
      #
      # resolve_tier's failure exits 0 here, not 1:
      # ccstatusline's Custom Command widget runs this
      # script via execSync(), which THROWS on a non-zero
      # exit.
      #
      # Its catch block then renders a visible "[Exit: N]"
      # token, so only an exit-zero run with empty stdout
      # reaches the widget's omission path.
      #
      # AC-11/AC-12 require the tier segment to be omitted
      # (not surfaced as an error token) when its data is
      # unavailable, so this CLI-boundary exit code must
      # stay 0.
      #
      # It stays 0 even though resolve_tier's own internal
      # failure return (1) is correct and unchanged
      # (auto-review finding F3).
      local raw_tier
      raw_tier="$(resolve_tier)" || return 0
      printf '%s\n' "$raw_tier" | awk '{print toupper(substr($0,1,1)) substr($0,2)}'
      ;;
    advisor)
      read_advisor_field
      ;;
    duration)
      local payload duration_ms now start_epoch
      payload="$(cat)"
      duration_ms="$(printf '%s' "$payload" | jq -r '.cost.total_duration_ms // 0' 2>/dev/null)"
      now="$(date +%s)"
      start_epoch=$((now - duration_ms / 1000))
      compute_session_duration_hours "$start_epoch" "$now"
      ;;
    expected5h)
      local payload resets_at
      payload="$(cat)"
      resets_at="$(printf '%s' "$payload" | jq -r '.rate_limits.five_hour.resets_at // empty' 2>/dev/null)"
      [ -z "$resets_at" ] && return 0
      expected_percent_from_resets_at "$resets_at" 18000
      ;;
    expected7d)
      local payload resets_at
      payload="$(cat)"
      resets_at="$(printf '%s' "$payload" | jq -r '.rate_limits.seven_day.resets_at // empty' 2>/dev/null)"
      [ -z "$resets_at" ] && return 0
      expected_percent_from_resets_at "$resets_at" 604800
      ;;
    -h | --help)
      usage
      ;;
    *)
      usage >&2
      return 1
      ;;
  esac
}

# Only auto-run main when this file is actually executed,
# not when it is sourced (as the test file does to unit-test
# each function in isolation).
#
# `(return 0 2>/dev/null)` succeeds only when the current
# context was reached via `source`/`.`, regardless of what
# $0 happens to be set to by the caller.
if ! (return 0 2>/dev/null); then
  main "$@"
fi
