#!/usr/bin/env bash

# test-statusline-tier.sh - plain-bash test file for
# statusline-tier.sh, the tier-read and pacing-arithmetic
# segment behind the ccstatusline Custom Command widget.
#
# That widget is the only custom code the
# claude-cost-controls plan adds.

# Usage:
#   bash test-statusline-tier.sh

# No bats dependency by design — same precedent as these
# sibling suites under configs/ai-docs/claude/:
#
# - hooks/tests/test-claude-git-guard.sh
# - tests/test-global-config-invariants.sh

# Every fixture below runs under a scratch $HOME plus explicit
# STATUSLINE_* path overrides, and PATH is prepended with a
# fake `security` binary per test.
#
# The real ~/.claude/.credentials.json, the real login
# Keychain, and the real ~/.claude/.statusline-tier-cache are
# never touched.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_UNDER_TEST="$script_dir/../statusline-tier.sh"
repo_root="$(cd "$script_dir/../../../../.." && pwd)"
SETTINGS_JSON="$repo_root/configs/ai-docs/claude/settings.json"
CCSTATUSLINE_CONFIG_SRC="$repo_root/configs/ai-docs/claude/ccstatusline/settings.json"

# snapshot_statusline_command - copy <src>'s
# statusLine.command into <dest>, the file every later read
# in this suite is served from.
#
# Usage:
#   snapshot_statusline_command <src> <dest>
#
# stdout: none
# exit: 0 once <dest> holds the command, 1 without writing
#   <dest> when <src> carries no readable statusLine.command
#
# Why a snapshot rather than a read per assertion: this
# settings.json is rewritten under the suite by every
# concurrent Claude Code session, because /model, /effort
# and /advisor each write it mid-session. Re-reading it nine
# times made the render assertions depend on whether a
# sibling session happened to be mid-write - three failed
# inside one full run and the same three passed in an
# isolated re-run seconds later.
snapshot_statusline_command() {
  local src="$1" dest="$2" statusline_command
  statusline_command="$(jq -r '.statusLine.command // empty' "$src" 2>/dev/null)"

  # Empty covers both halves of the rename window a writer
  # opens: the path resolving to nothing, and a file that
  # parses but has no statusLine yet. Failing here turns
  # either into one startup error rather than a dozen render
  # assertions comparing against an empty command.
  [ -n "$statusline_command" ] || return 1
  printf '%s\n' "$statusline_command" >"$dest"
}

# configured_statusline_command - the snapshotted
# statusLine.command.
#
# Snapshotting the working tree rather than HEAD keeps what
# the live read was there for: the StatusLineRender tests go
# RED before the wiring commit lands and GREEN right after
# the Edit, with no commit in between.
configured_statusline_command() {
  cat "$SETTINGS_COMMAND_SNAPSHOT"
}

SETTINGS_COMMAND_SNAPSHOT="$(mktemp "${TMPDIR:-/tmp}/statusline-tier-command.XXXXXX")"
if ! snapshot_statusline_command "$SETTINGS_JSON" "$SETTINGS_COMMAND_SNAPSHOT"; then
  printf 'no readable .statusLine.command in %s\n' "$SETTINGS_JSON" >&2
  exit 1
fi

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

# fresh_sandbox - a scratch dir for one test's $HOME,
# cache, credentials file and fake-binary PATH prepend,
# torn down by the caller when done.
fresh_sandbox() {
  mktemp -d "${TMPDIR:-/tmp}/statusline-tier-test.XXXXXX"
}

it_should_keep_serving_the_snapshotted_statusline_command_after_the_source_settings_file_is_rewritten() {
  local sandbox source_settings snapshot
  sandbox="$(fresh_sandbox)"
  source_settings="$sandbox/settings.json"
  snapshot="$sandbox/statusline-command"
  printf '{"statusLine":{"command":"echo snapshotted-command"}}\n' >"$source_settings"

  snapshot_statusline_command "$source_settings" "$snapshot"

  # What a concurrent Claude Code session does to this file
  # mid-suite: /model, /effort and /advisor each rewrite
  # settings.json, and one landed between two assertions is
  # what turned three StatusLineRender tests red inside a
  # full run that passed on its isolated re-run.
  printf '{"statusLine":{"command":"echo a-sibling-sessions-command"}}\n' >"$source_settings"

  assert_eq \
    "SettingsSnapshot > should keep serving the snapshotted statusline command after the source settings file is rewritten" \
    "echo snapshotted-command" \
    "$(SETTINGS_COMMAND_SNAPSHOT="$snapshot" configured_statusline_command)"
  rm -rf "$sandbox"
}

it_should_report_failure_and_write_no_snapshot_when_the_source_settings_file_is_unreadable() {
  local sandbox snapshot status snapshot_state
  sandbox="$(fresh_sandbox)"
  snapshot="$sandbox/statusline-command"

  # Every settings.json writer swaps the file in by rename,
  # so the path resolves to nothing for the width of that
  # swap. Serving an empty command from that window is what
  # made the flake read as a dozen wrong render assertions
  # instead of one unreadable-source error.
  snapshot_statusline_command "$sandbox/never-written.json" "$snapshot"
  status=$?
  snapshot_state=absent
  [ -e "$snapshot" ] && snapshot_state=present

  assert_eq \
    "SettingsSnapshot > should report failure when the source settings file is unreadable" \
    "1" "$status"
  assert_eq \
    "SettingsSnapshot > should write no snapshot when the source settings file is unreadable" \
    "absent" "$snapshot_state"
  rm -rf "$sandbox"
}

it_should_keep_serving_the_snapshotted_statusline_command_after_the_source_settings_file_is_rewritten
it_should_report_failure_and_write_no_snapshot_when_the_source_settings_file_is_unreadable

# One `security` fake serves every test, symlinked into
# each sandbox, because an endpoint-security agent
# (SentinelOne on this machine) scans a newly written
# script the FIRST time it is executed.
#
# Measured here: 7.8-12.3s for a fresh shell script,
# against 0.04s for every exec after it, and 0.05s through
# a symlink to an already-scanned one.
#
# The scan keys on the file, not its bytes, so writing the
# same fake into a fresh sandbox per test pays full price
# every time (measured: 8.5s for a byte-identical copy).
#
# That matters because the production Keychain read is
# bounded at 3s (STATUSLINE_KEYCHAIN_TIMEOUT_SECS): a
# per-test fake gets scanned INSIDE that window, so the
# watchdog kills it before it ever prints.
#
# Five tests failed exactly that way - four on an empty
# read, one on elapsed=5s - and the suite spent ~1m50s of
# its runtime being scanned.
#
# Production never pays this: the real `security` is a
# Mach-O binary macOS scanned long ago (measured: 0.03s).
SHARED_FAKE_BIN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/statusline-tier-shared-fakes.XXXXXX")"
# One EXIT trap serves every suite-scoped temp path, because
# a second `trap ... EXIT` would replace this one rather than
# run beside it.
trap 'rm -rf "$SHARED_FAKE_BIN_DIR" "$SETTINGS_COMMAND_SNAPSHOT"' EXIT

# The per-test fixture is read from the directory the fake
# was invoked THROUGH rather than baked into its text,
# which is what lets a single scanned file serve every
# test.
#
# $0 is the symlink PATH resolved to, not its target, so
# dirname lands on the calling test's own sandbox.
#
# Fields are read positionally, one per line, so a JSON
# secret carrying quotes needs no escaping on either side.
cat >"$SHARED_FAKE_BIN_DIR/security" <<'SHARED_FAKE_SECURITY'
#!/usr/bin/env bash
{
  read -r fake_mdat
  read -r fake_kill_parent
  read -r fake_delay_after_secret_secs
  read -r fake_secret_read_sentinel
  read -r fake_mode
} < "$(dirname "$0")/security-fixture"

case "$*" in
  *" -w"*)
    if [ "$fake_mode" = "hang" ]; then
      exec sleep 999999
    fi
    [ -n "$fake_secret_read_sentinel" ] && touch "$fake_secret_read_sentinel"
    printf '%s' "$fake_mode"
    if [ "$fake_kill_parent" = "kill-parent" ]; then
      kill -TERM "$PPID" 2>/dev/null
      sleep 1
    fi
    if [ "$fake_delay_after_secret_secs" != "0" ]; then
      sleep "$fake_delay_after_secret_secs"
    fi
    ;;
  *)
    printf 'keychain: "Claude Code-credentials"\nclass: "genp"\nattributes:\n    "cdat"<timedate>=%s\n    "mdat"<timedate>=%s\n' "$fake_mdat" "$fake_mdat"
    ;;
esac
SHARED_FAKE_SECURITY
chmod +x "$SHARED_FAKE_BIN_DIR/security"

# Pay the scan once, here, outside any bounded read.
#
# The warm-up argument must not contain " -w", so it takes
# the attribute branch and runs none of the mode-specific
# paths a real test selects.
printf '\n\n0\n\n\n' >"$SHARED_FAKE_BIN_DIR/security-fixture"
"$SHARED_FAKE_BIN_DIR/security" warm-up >/dev/null 2>&1 </dev/null

# write_fake_security - points "$bin_dir/security" at the
# shared fake above, ahead of PATH, so tests never shell
# out to the real macOS Keychain.
#
# $mdat is the attribute-read fixture value
# (YYYYMMDDHHMMSSZ format matching real
# `security find-generic-password` output).
#
# $mode selects the -w (secret) response: a literal JSON
# blob, or "hang" to simulate a blocking Keychain
# password-prompt dialog.
#
# $kill_parent, when passed the literal "kill-parent",
# makes the fake send SIGTERM to its own parent PID right
# after writing the secret to stdout, then sleep briefly
# before exiting.
#
# This deterministically simulates an external kill
# (e.g. ccstatusline's own execSync timeout).
#
# The kill lands on the reading process after the secret
# has already left `security` but before any cleanup on
# the caller's side has run.
#
# No sleep-based race is needed, since the signal is sent
# while the fake is still alive (sleeping), guaranteeing
# delivery precedes its own exit.
#
# $delay_after_secret_secs, when non-zero, keeps the fake
# alive (and its stdout pipe open) for that many seconds
# right after handing over the secret, before it exits
# normally.
#
# This widens the window a concurrent watcher gets to observe
# filesystem state while the read is still in flight, rather
# than only after it returns - existing callers omit it and
# see no behavior change (default 0 = no delay).
#
# $secret_read_sentinel, when non-empty, is touched on the
# -w read only, so a test can prove whether a cache hit
# reached the secret read at all - the attribute read
# happens either way and must not be mistaken for it.
write_fake_security() {
  local bin_dir="$1" mdat="$2" mode="$3" kill_parent="${4:-}" delay_after_secret_secs="${5:-0}" secret_read_sentinel="${6:-}"
  printf '%s\n%s\n%s\n%s\n%s\n' \
    "$mdat" "$kill_parent" "$delay_after_secret_secs" "$secret_read_sentinel" "$mode" \
    >"$bin_dir/security-fixture"
  ln -sf "$SHARED_FAKE_BIN_DIR/security" "$bin_dir/security"
}

# write_fake_mktemp_scoped_to_tmpdir - installs a fake
# `mktemp` binary at "$bin_dir/mktemp" ahead of PATH,
# forwarding to the real one but forcing a no-template call
# into $TMPDIR.
#
# This works around a real discovery made while testing the
# F7 fix: BSD mktemp on macOS (unlike GNU mktemp) ignores
# the $TMPDIR env var for a bare `mktemp` call and always
# resolves the OS-assigned per-user temp dir instead.
#
# So a test that scopes TMPDIR to a sandbox and then greps
# that sandbox for a leaked file would silently miss it on
# macOS, passing for the wrong reason.
write_fake_mktemp_scoped_to_tmpdir() {
  local bin_dir="$1"
  cat >"$bin_dir/mktemp" <<'EOF'
#!/usr/bin/env bash
if [ "$#" -eq 0 ]; then
  exec /usr/bin/mktemp "${TMPDIR:-/tmp}/tmp.XXXXXXXXXX"
fi
exec /usr/bin/mktemp "$@"
EOF
  chmod +x "$bin_dir/mktemp"
}

# write_fake_ccburn - installs a fake `ccburn` binary that
# mirrors the real one's confirmed contract.
#
# That contract: `ccburn collect` reads Claude Code's stdin
# JSON, side-effects a usage snapshot, and passes the same
# JSON through on stdout unchanged.
#
# The fake is reduced to the pass-through half, since the
# snapshot write is ccburn's own tested behavior, not this
# repo's.
write_fake_ccburn() {
  local bin_dir="$1"
  cat >"$bin_dir/ccburn" <<'EOF'
#!/usr/bin/env bash
cat
EOF
  chmod +x "$bin_dir/ccburn"
}

# write_usage_cache_fixture - seeds ccstatusline's own
# usage cache inside a sandbox $HOME, so the spend row
# renders from fixture data instead of the live API.
#
# ccstatusline fetches /api/oauth/usage for any configured
# extra-usage widget, because `extra_usage` never appears
# in the rate_limits the statusline JSON carries.
#
# Its fetch reads this file first and returns early when
# the file is newer than the 180s cache age, which writing
# it here satisfies.
#
# That early return only happens when the caller also
# installs a fake `security`.
#
# The cache is accepted only if the CURRENT token is null,
# and on macOS the token is read from the real login
# Keychain no matter what $HOME says.
#
# $used_cents and $limit_cents are the API's own units -
# `extra_usage.used_credits` and `extra_usage.monthly_limit`
# are both cents.
write_usage_cache_fixture() {
  local sandbox="$1" used_cents="$2" limit_cents="$3"
  mkdir -p "$sandbox/.cache/ccstatusline"
  cat >"$sandbox/.cache/ccstatusline/usage.json" <<EOF
{"sessionUsage":0,"weeklyUsage":0,"extraUsageEnabled":true,
 "extraUsageLimit":$limit_cents,"extraUsageUsed":$used_cents,
 "extraUsageCurrency":"USD"}
EOF
}

# write_fake_ccstatusline - installs a fake `ccstatusline`
# binary that reads the SAME config shape the real one
# reads from "$HOME/.config/ccstatusline/settings.json"
# (confirmed via ccstatusline.js's DEFAULT_SETTINGS_PATH).
#
# It also reads the same stdin JSON payload a Custom
# Command widget receives (confirmed via
# CustomCommand.tsx's render(): the full payload piped to
# item.commandPath's stdin).
#
# For each configured widget it either execs the real
# commandPath or extracts a fixed jq path.
#
# The exec branch covers custom-command widgets — that is
# what actually proves our config wires statusline-tier.sh
# correctly.
#
# The jq branch covers the handful of built-in widget types
# this repo's config uses, a stand-in for ccstatusline's
# own, out-of-scope rendering.
#
# Each present value is emitted as "[id-or-type: value]".
#
# For custom-command widgets specifically, this branches on
# EXIT STATUS, matching ccstatusline's own
# CustomCommandWidget.render().
#
# A non-zero exit makes the real widget's execSync() throw,
# and its catch block renders a visible "[Exit: N]" token
# regardless of any stdout the process produced.
#
# Only an exit-zero run with empty stdout reaches the real
# widget's "return output || null" omission path (AC-11
# auto-review finding F3).
#
# Branching on stdout emptiness alone let a script that
# exits non-zero on the unavailable path pass tests while
# the real widget would still render "[Exit: N]" on screen.
write_fake_ccstatusline() {
  local bin_dir="$1"
  cat >"$bin_dir/ccstatusline" <<'EOF'
#!/usr/bin/env bash
payload="$(cat)"
config_file="$HOME/.config/ccstatusline/settings.json"
out=""
while IFS= read -r widget; do
  type=$(printf '%s' "$widget" | jq -r '.type')
  case "$type" in
    custom-command)
      marker=$(printf '%s' "$widget" | jq -r '.id')
      cmd=$(printf '%s' "$widget" | jq -r '.commandPath')
      val=$(printf '%s' "$payload" | eval "$cmd" 2>/dev/null)
      status=$?
      [ "$status" -ne 0 ] && val="[Exit: ${status}]"
      ;;
    custom-text)
      marker="text"
      val=$(printf '%s' "$widget" | jq -r '.customText')
      ;;
    model)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.model.display_name // .model // empty')
      ;;
    thinking-effort)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.effort.level // empty')
      ;;
    context-length)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.context_window.context_window_size // empty')
      ;;
    context-percentage)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.context_window.used_percentage // empty')
      ;;
    session-cost)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.cost.total_cost_usd // empty')
      ;;
    session-usage)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.rate_limits.five_hour.used_percentage // empty')
      ;;
    reset-timer)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.rate_limits.five_hour.resets_at // empty')
      ;;
    weekly-usage)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.rate_limits.seven_day.used_percentage // empty')
      ;;
    weekly-reset-timer)
      marker="$type"
      val=$(printf '%s' "$payload" | jq -r '.rate_limits.seven_day.resets_at // empty')
      ;;
    *)
      marker="$type"
      val=""
      ;;
  esac
  [ -n "$val" ] && out="${out}[${marker}:${val}]"
done < <(jq -c '.lines[][]' "$config_file")
printf '%s\n' "$out"
EOF
  chmod +x "$bin_dir/ccstatusline"
}

# marker_value - extracts "value" from one "[marker:value]"
# chunk in a render_status_line output string, or prints
# nothing if the marker is absent (an omitted segment).
marker_value() {
  local output="$1" marker="$2"
  printf '%s' "$output" | grep -oE "\[${marker}:[^]]*\]" | sed -E "s/\[${marker}:([^]]*)\]/\1/"
}

# ============================================================
# describe("FakeCcstatuslineExitStatus")
# ============================================================

# Isolated, fast, synthetic-command proofs that
# write_fake_ccstatusline itself branches on the
# custom-command widget's EXIT STATUS the way the real
# ccstatusline widget does.
#
# The branch is on exit status, not on stdout emptiness
# (auto-review#F3).
#
# These are deliberately independent of statusline-tier.sh:
# they exercise only the fake's own branching logic, so a
# regression here is diagnosed without also needing to
# reason about Keychain timeouts or caching.

it_should_render_an_exit_n_token_when_a_custom_command_widget_exits_non_zero() {
  local sandbox bin_dir output
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.config/ccstatusline"
  write_fake_ccstatusline "$bin_dir"
  printf '{"lines":[[{"type":"custom-command","id":"broken","commandPath":"exit 3"}]]}' \
    >"$sandbox/.config/ccstatusline/settings.json"

  output=$(printf '{}' | HOME="$sandbox" PATH="$bin_dir:/usr/bin:/bin" ccstatusline)

  assert_eq \
    "FakeCcstatuslineExitStatus > failure > should render an [Exit: N]-shaped token when a custom-command widget exits non-zero, matching ccstatusline's real execSync catch behavior" \
    "[broken:[Exit: 3]]" "$output"
  rm -rf "$sandbox"
}

it_should_omit_a_custom_command_widget_that_exits_zero_with_empty_stdout() {
  local sandbox bin_dir output
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.config/ccstatusline"
  write_fake_ccstatusline "$bin_dir"
  printf '{"lines":[[{"type":"custom-command","id":"quiet","commandPath":"exit 0"}]]}' \
    >"$sandbox/.config/ccstatusline/settings.json"

  output=$(printf '{}' | HOME="$sandbox" PATH="$bin_dir:/usr/bin:/bin" ccstatusline)

  assert_eq \
    "FakeCcstatuslineExitStatus > happy > should omit a custom-command widget that exits zero with empty stdout, matching ccstatusline's real 'return output || null' path" \
    "" "$output"
  rm -rf "$sandbox"
}

it_should_render_an_exit_n_token_when_a_custom_command_widget_exits_non_zero
it_should_omit_a_custom_command_widget_that_exits_zero_with_empty_stdout

# ============================================================
# describe("StatusLineRender")
# ============================================================

it_should_render_tier_model_effort_context_window_advisor_context_percent_cost_duration_and_both_windows() {
  local sandbox bin_dir now resets_5h resets_7d payload output
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.claude/scripts" "$sandbox/.config/ccstatusline"
  ln -s "$SCRIPT_UNDER_TEST" "$sandbox/.claude/scripts/statusline-tier.sh"
  cp "$CCSTATUSLINE_CONFIG_SRC" "$sandbox/.config/ccstatusline/settings.json"
  printf '{"subscriptionType":"max"}' >"$sandbox/.claude/.credentials.json"
  printf '{"advisorModel":"opus"}' >"$sandbox/.claude/settings.json"
  write_fake_ccburn "$bin_dir"
  write_fake_ccstatusline "$bin_dir"

  now=$(date +%s)

  # elapsed 12960s of an 18000s window -> expected 72%
  resets_5h=$((now + 5040))

  # elapsed 151200s of a 604800s window -> expected 25%
  resets_7d=$((now + 453600))
  payload=$(cat <<JSON
{
  "model": {"display_name": "Sonnet 5"},
  "effort": {"level": "high"},
  "context_window": {"context_window_size": 200000, "used_percentage": 34},
  "cost": {"total_cost_usd": 1.23, "total_duration_ms": 7500000},
  "rate_limits": {
    "five_hour": {"used_percentage": 40, "resets_at": $resets_5h},
    "seven_day": {"used_percentage": 55, "resets_at": $resets_7d}
  }
}
JSON
  )

  output=$(
    printf '%s' "$payload" | HOME="$sandbox" PATH="$bin_dir:/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c "$(configured_statusline_command)"
  )

  local tier advisor duration builtins_present marker
  tier=$(marker_value "$output" "tier")
  advisor=$(marker_value "$output" "advisor")
  duration=$(marker_value "$output" "duration")

  builtins_present=true
  for marker in model thinking-effort context-length context-percentage \
    session-cost session-usage reset-timer weekly-usage weekly-reset-timer; do
    [ -n "$(marker_value "$output" "$marker")" ] || builtins_present=false
  done

  # Only tier/advisor/duration are asserted by value here.
  #
  # The expected-pace percentages this config once rendered
  # via two custom-command widgets are now drawn by the
  # built-in usage widgets' own cursor, so no custom-command
  # marker carries them any more.
  #
  # Their real values are pinned where they are now visible:
  # the cursor-position assertion in StatusLineRealRender.
  assert_eq \
    "StatusLineRender > happy > should render tier, model, effort, context window, advisor, context percent, cost, duration and both windows" \
    "Max opus · ⏱ 2h true" "$tier $advisor $duration $builtins_present"
  rm -rf "$sandbox"
}

it_should_render_the_literal_none_for_the_advisor_field_when_no_advisormodel_is_configured() {
  local sandbox bin_dir payload output advisor
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.claude/scripts" "$sandbox/.config/ccstatusline"
  ln -s "$SCRIPT_UNDER_TEST" "$sandbox/.claude/scripts/statusline-tier.sh"
  cp "$CCSTATUSLINE_CONFIG_SRC" "$sandbox/.config/ccstatusline/settings.json"
  printf '{"subscriptionType":"max"}' >"$sandbox/.claude/.credentials.json"

  # Deliberately no $sandbox/.claude/settings.json at all:
  # read_advisor_field falls back to "none" when the file is
  # missing, matching this repo's own committed default (no
  # advisorModel key).
  write_fake_ccburn "$bin_dir"
  write_fake_ccstatusline "$bin_dir"

  payload='{"model":{"display_name":"Sonnet 5"},"cost":{"total_duration_ms":0}}'
  output=$(
    printf '%s' "$payload" | HOME="$sandbox" PATH="$bin_dir:/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c "$(configured_statusline_command)"
  )
  advisor=$(marker_value "$output" "advisor")

  assert_eq \
    "StatusLineRender > happy > should render the literal none for the advisor field when no advisorModel is configured" \
    "none" "$advisor"
  rm -rf "$sandbox"
}

it_should_render_the_remaining_segments_when_the_cost_segment_has_no_data_yet() {
  local sandbox bin_dir payload output tier cost_present
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.claude/scripts" "$sandbox/.config/ccstatusline"
  ln -s "$SCRIPT_UNDER_TEST" "$sandbox/.claude/scripts/statusline-tier.sh"
  cp "$CCSTATUSLINE_CONFIG_SRC" "$sandbox/.config/ccstatusline/settings.json"
  printf '{"subscriptionType":"max"}' >"$sandbox/.claude/.credentials.json"
  write_fake_ccburn "$bin_dir"
  write_fake_ccstatusline "$bin_dir"

  # No "cost" key at all: the session-cost segment's data
  # is unavailable.
  payload='{"model":{"display_name":"Sonnet 5"},"effort":{"level":"high"}}'
  output=$(
    printf '%s' "$payload" | HOME="$sandbox" PATH="$bin_dir:/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c "$(configured_statusline_command)"
  )
  tier=$(marker_value "$output" "tier")
  cost_present=no
  [ -n "$(marker_value "$output" "session-cost")" ] && cost_present=yes

  assert_eq \
    "StatusLineRender > corner > should render the remaining segments when the cost segment has no data yet" \
    "Max no" "$tier $cost_present"
  rm -rf "$sandbox"
}

it_should_render_nothing_and_exit_zero_when_ccstatusline_or_ccburn_is_not_installed() {
  local output status
  output=$(
    printf '{}' | PATH="/usr/bin:/bin" \
      bash -c "$(configured_statusline_command)"
  )
  status=$?

  assert_eq \
    "StatusLineRender > failure > should render nothing and exit zero when ccstatusline or ccburn is not installed" \
    " 0" "$output $status"
}

# The integration-level proof for AC-11/AC-12
# (auto-review#F3).
#
# It drives the committed config and the real
# statusline-tier.sh through the (now exit-status-aware)
# fake ccstatusline, with the Keychain read forced past its
# timeout so the tier segment's data is unavailable.
#
# Before the F3 fix, resolve_tier's internal failure
# propagated all the way out to the script's own exit
# status.
#
# So the fixed fake would render "[tier:[Exit: 1]]" here -
# exactly the "[Exit: 1]" the maintainer's screenshot
# showed on screen.
#
# This is what proves the production fix, not just the fake
# fix: the CLI-boundary test below already proves the
# script's own exit code/stdout contract in isolation.
#
# This test proves that contract is what the real
# widget-composition pipeline actually renders.
it_should_omit_the_tier_segment_rather_than_surface_an_exit_n_token_when_tier_data_is_unavailable() {
  local sandbox bin_dir payload output tier_marker model_marker
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.claude/scripts" "$sandbox/.config/ccstatusline"
  ln -s "$SCRIPT_UNDER_TEST" "$sandbox/.claude/scripts/statusline-tier.sh"
  cp "$CCSTATUSLINE_CONFIG_SRC" "$sandbox/.config/ccstatusline/settings.json"

  # No credentials file: forces the Keychain branch.
  #
  # The fake `security` hangs on the -w (secret) read, so
  # resolve_tier only succeeds if the bounded timeout below
  # is honored.
  #
  # It fails either way, exercising the code path AC-12
  # requires the tier segment to be omitted for.
  write_fake_security "$sandbox" "20260730082118Z" "hang"
  write_fake_ccburn "$bin_dir"
  write_fake_ccstatusline "$bin_dir"

  payload='{"model":{"display_name":"Sonnet 5"}}'
  output=$(
    printf '%s' "$payload" | HOME="$sandbox" STATUSLINE_KEYCHAIN_TIMEOUT_SECS=1 \
      PATH="$bin_dir:$sandbox:/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c "$(configured_statusline_command)"
  )

  tier_marker="absent"
  printf '%s' "$output" | grep -q '\[tier:' && tier_marker="present:$(marker_value "$output" tier)"

  assert_eq \
    "StatusLineRender > failure > should omit the tier segment rather than surface an [Exit: N] token when tier data is unavailable" \
    "absent" "$tier_marker"

  # AC-11 is two-sided: "omitted while the rest of the line
  # still renders".
  #
  # The assertion above only pins the omission half - it
  # would also pass on a totally empty render (e.g. the
  # whole pipeline crashing), which is a regression AC-11
  # forbids just as much as an [Exit: N] token.
  #
  # This sibling assertion pins the other half: an unrelated
  # widget (model, fed from the payload above and never
  # touching the unavailable Keychain path) must still
  # render.
  model_marker="absent"
  printf '%s' "$output" | grep -q '\[model:' && model_marker="present:$(marker_value "$output" model)"

  assert_eq \
    "StatusLineRender > failure > should still render the model segment while the tier segment is omitted" \
    "present:Sonnet 5" "$model_marker"
  rm -rf "$sandbox"
}

it_should_render_tier_model_effort_context_window_advisor_context_percent_cost_duration_and_both_windows
it_should_render_the_literal_none_for_the_advisor_field_when_no_advisormodel_is_configured
it_should_render_the_remaining_segments_when_the_cost_segment_has_no_data_yet
it_should_render_nothing_and_exit_zero_when_ccstatusline_or_ccburn_is_not_installed
it_should_omit_the_tier_segment_rather_than_surface_an_exit_n_token_when_tier_data_is_unavailable

# ============================================================
# describe("StatusLineRealRender")
# ============================================================

# Unlike StatusLineRender above, this test drives the REAL,
# installed `ccstatusline` npm binary against the committed
# config.
#
# StatusLineRender instead drives a FAKE ccstatusline that
# extracts one raw value per widget into "[marker:value]"
# markers.
#
# The fake binary models widget composition rather than
# performing it, so it cannot catch a bug IN composition.
#
# Such a bug would be a built-in widget rendering its own
# label (e.g. "Ctx: ") alongside this config's custom-text
# label, or a padding "merge" landing on the wrong widget.
#
# Only the real binary's actual stdout proves those are
# absent.
#
# ccburn is still faked (pass-through) per this repo's hard
# rule: `ccburn collect` reads and writes the maintainer's
# real usage-history file, so no test may invoke it for
# real.
#
# The synthetic payload below supplies rate_limits directly
# on stdin, which the real ccstatusline widgets read
# straight from that JSON with no network fetch.
#
# Confirmed by reading ccstatusline's own
# extractUsageDataFromRateLimits() and
# prefetchUsageDataIfNeeded().
#
# The network path only runs when a rate_limits field is
# still missing after this check.

# real_ccstatusline_dir - the directory holding the
# actually-installed ccstatusline binary (from install.sh's
# `npm install -g ccstatusline`), or empty when it is not
# on PATH.
#
# Resolved once at file load, not inside the test, so every
# use sees the same value.
real_ccstatusline_dir() {
  local bin
  bin="$(command -v ccstatusline 2>/dev/null)" || return 0
  dirname "$bin"
}
REAL_CCSTATUSLINE_DIR="$(real_ccstatusline_dir)"

it_should_render_each_builtin_widget_raw_with_no_duplicate_label_and_no_stray_padding() {
  if [ -z "$REAL_CCSTATUSLINE_DIR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - StatusLineRealRender > happy > should render each builtin widget raw with no duplicate label and no stray padding # SKIP ccstatusline is not installed (run install.sh)\n'
    return
  fi

  local sandbox bin_dir now resets_5h resets_7d payload raw_output output line2
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.claude/scripts" "$sandbox/.config/ccstatusline"
  ln -s "$SCRIPT_UNDER_TEST" "$sandbox/.claude/scripts/statusline-tier.sh"
  cp "$CCSTATUSLINE_CONFIG_SRC" "$sandbox/.config/ccstatusline/settings.json"
  printf '{"subscriptionType":"max"}' >"$sandbox/.claude/.credentials.json"
  printf '{"advisorModel":"opus"}' >"$sandbox/.claude/settings.json"
  write_fake_ccburn "$bin_dir"
  write_fake_security "$bin_dir" "20260730082118Z" \
    '{"claudeAiOauth":{"subscriptionType":"max"}}'

  # Seeded even though this account's spend row gets
  # dropped, so assertion 12 proves the filter drops a row
  # that HAD data to render.
  #
  # Without the fixture the row would render empty anyway
  # and the assertion would pass for the wrong reason.
  write_usage_cache_fixture "$sandbox" 20901 100000

  now=$(date +%s)

  # elapsed 12960s of an 18000s window -> expected 72%
  resets_5h=$((now + 5040))

  # elapsed 151200s of a 604800s window -> expected 25%
  resets_7d=$((now + 453600))
  payload=$(cat <<JSON
{
  "model": {"display_name": "Sonnet 5"},
  "effort": {"level": "high"},
  "context_window": {"context_window_size": 200000, "used_percentage": 47.86},
  "cost": {"total_cost_usd": 1.23, "total_duration_ms": 21600000},
  "rate_limits": {
    "five_hour": {"used_percentage": 40, "resets_at": $resets_5h},
    "seven_day": {"used_percentage": 55, "resets_at": $resets_7d}
  }
}
JSON
  )

  raw_output=$(
    printf '%s' "$payload" | HOME="$sandbox" \
      PATH="$bin_dir:$REAL_CCSTATUSLINE_DIR:/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c "$(configured_statusline_command)"
  )
  # Strip ANSI color/style codes (colorLevel:3 in the
  # committed config), then normalize ccstatusline's own
  # padding character down to a plain space.
  #
  # That padding character was confirmed via a raw byte dump
  # to be U+00A0 NO-BREAK SPACE (UTF-8 0xC2 0xA0), not a
  # plain ASCII space.
  #
  # A real terminal renders both identically, but a
  # byte-literal " " pattern below would silently never
  # match the actual output without this normalization.
  output=$(
    printf '%s\n' "$raw_output" \
      | sed -E 's/\x1b\[[0-9;]*m//g' \
      | sed $'s/\xc2\xa0/ /g'
  )
  line2=$(printf '%s\n' "$output" | sed -n '2p')

  local doubled_labels stray_percent_space stray_duration_space six_h_present

  # Each of these is a built-in widget's own label,
  # rendered only when the widget lacks rawValue:true.
  #
  # None may appear: this config supplies its own
  # custom-text labels ("Ctx ", "⏱ ", "5h", "7d", ...)
  # instead.
  doubled_labels=$(printf '%s' "$output" | grep -cE \
    'Ctx: |Ctx Used: |Ctx Left: |Cost: |Session: |Weekly: |Reset: |Weekly Reset: ')
  # A digit followed by 1+ spaces then "%" is the
  # merge:"no-padding"-is-missing symptom on
  # expected5h/expected7d (e.g. the reported "29 %").
  stray_percent_space=$(printf '%s' "$output" | grep -cE '[0-9][[:space:]]+%')
  # A digit followed by 2+ spaces then "h" at end of line
  # is the merge:"no-padding" flag sitting on the wrong
  # widget (duration-unit, a no-op there, instead of
  # duration) — the reported "6  h".
  #
  # Anchored to end-of-line so this doesn't false-positive
  # on unrelated "<digit>  h..." text elsewhere on the line
  # (e.g. "Sonnet 5  high").
  stray_duration_space=$(printf '%s' "$output" | grep -cE '[0-9][[:space:]]{2,}h[[:space:]]*$')
  six_h_present=no
  printf '%s' "$output" | grep -qF '6h' && six_h_present=yes

  assert_eq \
    "StatusLineRealRender > happy > should render each builtin widget raw with no duplicate label and no stray padding" \
    "0 0 0 yes" "$doubled_labels $stray_percent_space $stray_duration_space $six_h_present"

  # ---- maintainer-reviewed formatting fixup (six exact
  # changes) ----

  # Extended in place, on the same captured $output, rather
  # than as separate it_ functions.
  #
  # This test is the only one that pays the cost of spinning
  # up the real ccstatusline binary.
  #
  # Every assertion below reads that one already-captured
  # render, so a second function would only duplicate the
  # expensive setup for free extra assertions.
  local line1 no_decimal_percent rounds_up_correctly max_tight ctx_shape \
    duration_label_shape no_redundant_dollar_label token_count_untouched \
    cost_untouched pacing_5h_shape pacing_7d_shape line1_closes_clean \
    line2_closes_clean no_redundant_advisor_label single_spaced edges_clean \
    line
  line1=$(printf '%s\n' "$output" | sed -n '1p')

  # 1. No "<digits>.<digits>%" survives anywhere: every
  # percentage widget's ccstatusline toFixed(1) output must
  # have gone through the awk rounding filter appended to
  # statusLine.command.
  no_decimal_percent=$(printf '%s' "$output" | grep -cE '[0-9]+\.[0-9]+%')
  assert_eq \
    "StatusLineRealRender > happy > no <digits>.<digits>% survives anywhere" \
    "0" "$no_decimal_percent"

  # 2. Rounding is real, not truncation:
  # context_window.used_percentage is fed as 47.86, which
  # ccstatusline's own toFixed(1) turns into "47.9".
  #
  # Only a real round-half-up filter prints "48%"; a
  # truncating one would print "47%".
  #
  # The token count sits between the Ctx label and the
  # percentage, matched by shape (see assertion 7) so the
  # fixture's exact value stays free to change.
  rounds_up_correctly=no
  printf '%s' "$output" \
    | grep -qE 'Ctx [0-9]+\.[0-9]+k[[:space:]]+48%' \
    && rounds_up_correctly=yes
  assert_eq \
    "StatusLineRealRender > happy > rounding is real (a .5+ fixture rounds up, not truncates)" \
    "yes" "$rounds_up_correctly"

  # 3. [Max] replaces "[ max ]": capitalized, no padding
  # inside the brackets.
  max_tight=no
  printf '%s' "$output" | grep -qF '[Max]' && max_tight=yes
  assert_eq \
    "StatusLineRealRender > happy > [Max] renders capitalized with no internal padding" \
    "yes" "$max_tight"

  # 4. Ctx replaces the Context label, tight single space
  # before the value it now leads: the token count.
  #
  # One literal space in the pattern, so the doubled
  # padding a missing merge:"no-padding" would produce
  # fails this.
  ctx_shape=no
  printf '%s' "$output" | grep -qE 'Ctx [0-9]+\.[0-9]+k' && ctx_shape=yes
  assert_eq \
    "StatusLineRealRender > happy > Ctx replaces Context with a tight single space" \
    "yes" "$ctx_shape"

  # 5. Duration gains a tight "⏱ " label ahead of it.
  duration_label_shape=no
  printf '%s' "$output" | grep -qF '⏱ 6h' && duration_label_shape=yes
  assert_eq \
    "StatusLineRealRender > happy > duration gains a tight ⏱ label" \
    "yes" "$duration_label_shape"

  # 6. The redundant "$" custom-text label is gone -
  # session-cost's own "$" prefix is the only one left, so
  # "$" is never followed by whitespace then another "$".
  no_redundant_dollar_label=yes
  printf '%s' "$output" | grep -qE '\$[[:space:]]+\$' && no_redundant_dollar_label=no
  assert_eq \
    "StatusLineRealRender > happy > the redundant \$ custom-text label is gone" \
    "yes" "$no_redundant_dollar_label"

  # 7. The token count (a "<digits>.<digits>k" shape, e.g.
  # "95.7k") and the 2-decimal cost survive the % filter
  # untouched.
  #
  # The filter must only ever match "<digits>.<digits>%",
  # never a bare decimal with no percent sign.
  #
  # Matched by shape rather than a literal number: the exact
  # token count is a function of this fixture's
  # context_window_size/used_percentage, not a value the
  # filter itself produces.
  token_count_untouched=no
  printf '%s' "$output" | grep -qE '[0-9]+\.[0-9]+k' && token_count_untouched=yes
  cost_untouched=no

  # literal grep -F pattern, not a shell expansion
  # shellcheck disable=SC2016
  printf '%s' "$output" | grep -qF '$1.23' && cost_untouched=yes
  assert_eq \
    "StatusLineRealRender > happy > the token-count decimal and the 2-decimal cost survive the % filter untouched" \
    "yes yes" "$token_count_untouched $cost_untouched"

  # 8. Each pacing segment renders "<usage>% <bar> in
  # <reset>".
  #
  # The bar fills one cell per 10% used and draws a cursor
  # at the window's elapsed percentage, so fill short of
  # the cursor reads as under pace and fill past it as
  # over pace.
  #
  # Pinned as exact bars rather than a loose shape: the
  # cursor position is the whole feature, and it comes
  # from ccstatusline's own window resolution - a second
  # implementation of what statusline-tier.sh computes.
  #
  # This fixture is 40% used at 72% elapsed on 5h, and 55%
  # used at 25% elapsed on 7d, so a drift between the two
  # implementations moves a cursor and fails here.
  pacing_5h_shape=no
  printf '%s' "$output" | grep -qF '5h 40% ▓▓▓▓░░░│░░ in ' && pacing_5h_shape=yes
  pacing_7d_shape=no
  printf '%s' "$output" | grep -qF '7d 55% ▓▓│▓▓▓░░░░ in ' && pacing_7d_shape=yes
  assert_eq \
    "StatusLineRealRender > happy > each pacing segment renders usage% then a bar whose cursor marks the expected pace" \
    "yes yes" "$pacing_5h_shape $pacing_7d_shape"

  # 9. Neither line is truncated at a realistic width: each
  # ends on its actual last widget instead of being cut
  # mid-token by ccstatusline's own flex/compact mode.
  #
  # Line 2's last widget is the weekly reset countdown, so
  # its clean close is a whole duration unit rather than a
  # number stripped of its unit.
  line1_closes_clean=no
  [[ "$line1" == *6h ]] && line1_closes_clean=yes
  line2_closes_clean=no
  [[ "$line2" =~ [0-9]+(d|hr|m)$ ]] && line2_closes_clean=yes
  assert_eq \
    "StatusLineRealRender > happy > neither line is truncated at a realistic width" \
    "yes yes" "$line1_closes_clean $line2_closes_clean"

  # 10. The redundant "Advisor" custom-text label is gone -
  # advisor sits inside the tier/model/effort run, which
  # reads without per-field labels.
  #
  # Same defect class assertion 6 guards for "$": a label
  # duplicating what its neighbour already conveys. Both
  # were caught by maintainer eyeball, not by the widget-
  # label loop above, which only knows built-in labels.
  no_redundant_advisor_label=yes
  printf '%s' "$output" | grep -qF 'Advisor' && no_redundant_advisor_label=no
  assert_eq \
    "StatusLineRealRender > happy > the redundant Advisor custom-text label is gone" \
    "yes" "$no_redundant_advisor_label"

  # 11. Widgets are separated by exactly one space, and
  # neither line is padded at its own edges.
  #
  # ccstatusline pads every widget on both sides by default,
  # which doubles every separator and leaves one pad hanging
  # off each end.
  #
  # defaultPaddingSide:"left" halves it; the
  # statusLine.command filter strips the edge pad it leaves.
  single_spaced=yes
  printf '%s' "$output" | grep -qE '[^[:space:]][[:space:]]{2,}[^[:space:]]' \
    && single_spaced=no
  edges_clean=yes
  for line in "$line1" "$line2"; do
    [[ "$line" == [[:space:]]* || "$line" == *[[:space:]] ]] && edges_clean=no
  done
  assert_eq \
    "StatusLineRealRender > happy > widgets are single-spaced and neither line is edge-padded" \
    "yes yes" "$single_spaced $edges_clean"

  # 12. The monthly-spend row is dropped, leaving the tier
  # row and the pacing row.
  #
  # A plan billed against 5h/7d windows has no
  # pay-as-you-go cap to spend against, so that row is dead
  # weight here - the mirror of the Enterprise case, where
  # the pacing row is the dead one.
  #
  # The fixture above gave the row real data, so a surviving
  # row would carry the cap and fail this.
  local spend_row_dropped line_count
  spend_row_dropped=yes

  # literal grep -F pattern, not a shell expansion
  # shellcheck disable=SC2016
  printf '%s' "$output" | grep -qF 'of $1000' && spend_row_dropped=no
  line_count=$(printf '%s\n' "$output" | wc -l | tr -d ' ')
  assert_eq \
    "StatusLineRealRender > happy > the monthly-spend row is dropped for a plan billed against 5h/7d windows" \
    "yes 2" "$spend_row_dropped $line_count"

  printf '# line1 (%d chars): %s\n' "${#line1}" "$line1" >&2
  printf '# line2 (%d chars): %s\n' "${#line2}" "$line2" >&2
  rm -rf "$sandbox"
}

it_should_render_each_builtin_widget_raw_with_no_duplicate_label_and_no_stray_padding

it_should_omit_the_pacing_row_for_an_enterprise_account() {
  if [ -z "$REAL_CCSTATUSLINE_DIR" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - StatusLineRealRender > enterprise > should omit the 5h/7d pacing row for an Enterprise account # SKIP ccstatusline is not installed (run install.sh)\n'
    return
  fi

  local sandbox bin_dir payload raw_output output
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir" "$sandbox/.claude/scripts" "$sandbox/.config/ccstatusline"
  ln -s "$SCRIPT_UNDER_TEST" "$sandbox/.claude/scripts/statusline-tier.sh"
  cp "$CCSTATUSLINE_CONFIG_SRC" "$sandbox/.config/ccstatusline/settings.json"
  printf '{"subscriptionType":"enterprise"}' >"$sandbox/.claude/.credentials.json"
  printf '{"advisorModel":"opus"}' >"$sandbox/.claude/settings.json"
  write_fake_ccburn "$bin_dir"
  write_fake_security "$bin_dir" "20260730082118Z" \
    '{"claudeAiOauth":{"subscriptionType":"enterprise"}}'

  # $209.01 of $1000 - the live account's own shape, kept
  # because both halves exercise a branch a round number
  # would skip.
  #
  # The spend is non-round, so a lost cent shows up, and the
  # cap divides evenly, so the whole-dollar path is the one
  # under test.
  write_usage_cache_fixture "$sandbox" 20901 100000

  # rate_limits is omitted deliberately: an Enterprise plan
  # has no 5h/7d budget, so Claude Code sends no such key.
  #
  # That absence is exactly what makes the row worth
  # dropping - every widget on it renders a zeroed bar
  # beside a reset timer that never resolves.
  payload=$(cat <<'JSON'
{
  "model": {"display_name": "Sonnet 5"},
  "effort": {"level": "high"},
  "context_window": {"context_window_size": 200000, "used_percentage": 47.86},
  "cost": {"total_cost_usd": 1.23, "total_duration_ms": 21600000}
}
JSON
  )

  raw_output=$(
    printf '%s' "$payload" | HOME="$sandbox" \
      PATH="$bin_dir:$REAL_CCSTATUSLINE_DIR:/usr/bin:/bin:/opt/homebrew/bin" \
      bash -c "$(configured_statusline_command)"
  )
  output=$(
    printf '%s\n' "$raw_output" \
      | sed -E 's/\x1b\[[0-9;]*m//g' \
      | sed $'s/\xc2\xa0/ /g'
  )

  local line_count pacing_tokens tier_rendered spend_rendered line2

  # 1. The pacing row is gone, leaving the tier row and the
  # spend row.
  #
  # Both halves are checked because either alone would pass
  # against a broken filter: a line count of 2 could also
  # come from dropping the wrong line, and an absent "5h"
  # could come from the row rendering empty but present.
  line_count=$(printf '%s\n' "$output" | wc -l | tr -d ' ')
  pacing_tokens=$(printf '%s' "$output" | grep -cE '5h|7d|Loading')
  assert_eq \
    "StatusLineRealRender > enterprise > should omit the 5h/7d pacing row for an Enterprise account" \
    "2 0" "$line_count $pacing_tokens"

  # 2. The first surviving line is the tier/model/cost row,
  # not a stray fragment of the row that was dropped.
  tier_rendered=no
  printf '%s' "$output" | grep -qF '[Enterprise]' && tier_rendered=yes
  assert_eq \
    "StatusLineRealRender > enterprise > the tier row survives when the pacing row is dropped" \
    "yes" "$tier_rendered"

  # 3. The spend row reads "<spent> of <monthly cap>".
  #
  # Pinned as the exact rendered string rather than a loose
  # shape, because the two halves come from different
  # sources and only their agreement is worth asserting.
  #
  # "$209.01" is ccstatusline's own extra-usage-used widget
  # formatting the cache's used_credits, while "$1000" is
  # this repo's spend-limit subcommand formatting the same
  # file's monthly_limit.
  #
  # A shape-only match would pass while one side silently
  # read a different field or dropped the cents.
  line2=$(printf '%s\n' "$output" | sed -n '2p')
  spend_rendered=no

  # literal dollar signs, not a shell expansion
  # shellcheck disable=SC2016
  [ "$line2" = '$209.01 of $1000' ] && spend_rendered=yes
  assert_eq \
    "StatusLineRealRender > enterprise > the spend row renders the month's extra usage against its cap" \
    "yes" "$spend_rendered"

  printf '# enterprise render:\n%s\n' "$output" >&2
  rm -rf "$sandbox"
}

it_should_omit_the_pacing_row_for_an_enterprise_account

# A real-binary proof for AC-11/AC-12 (driving the actual
# installed npm ccstatusline, not the fake) was attempted
# here and dropped.
#
# It drove the tier segment's unavailable path (fake
# `security -w` simulating a hung Keychain prompt) through
# the real `execSync()` pipeline and hung indefinitely.
#
# The fake's `sleep 999999` grandchild kept node's stdout
# pipe held open after being SIGTERM'd, so the downstream
# `perl` stage never saw EOF.
#
# A bounding timeout can't rescue this test either - its
# assertion is "no [Exit: N] token present".
#
# A timeout-killed, empty pipeline also satisfies that
# assertion, so it would go green whether or not the
# production fix is correct.
#
# Filed as a Scout (run_with_timeout leaves an orphaned
# grandchild that outlives its SIGTERM) rather than fixed
# here - out of scope for F3, and unproven against the real
# `security` binary, only against this test's fake.
#
# The StatusLineRender-level test above (via the corrected
# fake) and the CLI-boundary test below already prove both
# AC-11/AC-12 halves without touching the real npm binary.

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
  write_fake_security "$sandbox" "20260730082118Z" '{"claudeAiOauth":{"subscriptionType":"max"}}'

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

  # No credentials file at all: this forces the Keychain/mdat
  # code path.
  #
  # Branching on the file's existence (not `uname`) means
  # absence alone forces this path on any host — a `uname`
  # guard would need the host OS faked too.
  write_fake_security "$sandbox" "20260730082118Z" '{"claudeAiOauth":{"subscriptionType":"max"}}'
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

  # This exercises the credentials-file/mtime branch via a
  # faked file, not a live Linux run (this dev host is macOS)
  # — the branch is existence-based, not `uname`-based, so
  # faking file presence is enough to force it on any host.
  printf '{"claudeAiOauth":{"subscriptionType":"pro"}}' >"$sandbox/credentials.json"
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
  cache_contents=$(awk '{print $2}' "$sandbox/nonexistent-cache" 2>/dev/null)

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

  # Cache epoch equal to the credentials file's own mtime:
  # NOT older, so a correct implementation must serve the
  # cache unchanged rather than re-read.
  #
  # That proves the comparison is conditional, not an
  # unconditional re-read every call.
  printf '%s old-tier\n' "$(stat -f %m "$sandbox/credentials.json" 2>/dev/null || stat -c %Y "$sandbox/credentials.json")" \
    >"$sandbox/tier-cache"

  first=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/tier-cache" \
      PATH="/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )

  # Now advance the credentials file's mtime strictly past
  # the cached epoch, and change its content: a correct
  # implementation must re-read.
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

it_should_serve_the_cached_tier_without_re_reading_the_credential_store_when_the_cache_is_not_stale() {
  local sandbox secret_read_sentinel actual
  sandbox="$(fresh_sandbox)"
  secret_read_sentinel="$sandbox/secret-read-sentinel"

  # No credentials file: forces the Keychain branch, same
  # fixture shape as the macOS-invalidation test above.
  #
  # The sentinel is touched on the -w secret read only, not
  # on the plain mdat attribute read that
  # credential_store_timestamp() performs on every call,
  # cache hit or not.
  #
  # So its absence proves the cache-hit branch never
  # reached read_subscription_tier_from_keychain.
  write_fake_security "$sandbox" "20260730082118Z" \
    '{"claudeAiOauth":{"subscriptionType":"max"}}' "" "0" "$secret_read_sentinel"

  # Cache epoch set far in the future: guaranteed not older
  # than the Keychain mdat above (2026-07-30).
  #
  # So resolve_tier's "$store_ts" -le "$cached_epoch"
  # comparison must take the cache-hit branch regardless of
  # exact mdat-to-epoch parsing.
  printf '9999999999 cached-tier\n' >"$sandbox/tier-cache"

  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/tier-cache" \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; resolve_tier' "$SCRIPT_UNDER_TEST"
  )

  if [ -f "$secret_read_sentinel" ]; then
    actual="CACHE-BYPASSED:$actual"
  fi

  assert_eq \
    "StatusLineTierSegment > corner > should serve the cached tier without re-reading the credential store when the cache is not stale" \
    "cached-tier" "$actual"
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

# The direct CLI-boundary proof for AC-11/AC-12
# (auto-review#F3).
#
# The test above only checks that the internal
# read_subscription_tier_from_keychain helper is bounded
# and fails - that helper returning non-zero to its own
# caller is fine and was never the bug.
#
# What ccstatusline actually observes is this script's own
# process exit status when invoked as
# `statusline-tier.sh tier`, which is what this test
# executes (not sources).
#
# So a `return 1` anywhere inside main's "tier" case would
# fail it exactly as it would fail against the real widget.
it_should_exit_zero_with_no_output_when_the_tier_is_unavailable() {
  local sandbox output status
  sandbox="$(fresh_sandbox)"
  write_fake_security "$sandbox" "20260730082118Z" "hang"

  output=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      STATUSLINE_TIER_CACHE="$sandbox/nonexistent-cache" \
      STATUSLINE_KEYCHAIN_TIMEOUT_SECS=1 \
      PATH="$sandbox:/usr/bin:/bin" \
      "$SCRIPT_UNDER_TEST" tier
  )
  status=$?

  assert_eq \
    "StatusLineTierSegment > failure > should exit zero with no output when the tier segment's data is unavailable (AC-11/AC-12 omission contract)" \
    " 0" "$output $status"
  rm -rf "$sandbox"
}

it_should_never_write_the_raw_credential_value_anywhere() {
  local sandbox marker sentinel watch_pid captured
  local observed_during_run leaked_in_output leaked_in_tmp
  sandbox="$(fresh_sandbox)"
  marker="RAW-SECRET-MARKER-do-not-leak-9f31"

  # A post-hoc scan of TMPDIR after the read returns
  # only proves "absent after cleanup" - the exact
  # shape of the historical F7 bug: it wrote the secret
  # to a mktemp file and cleaned up on the return path.
  #
  # That cleanup runs fine on an uninterrupted read, so
  # a scan taken only after the read completes would
  # have stayed green through F7 too.
  #
  # This test instead watches the scoped TMPDIR
  # while the read is in flight:
  # write_fake_mktemp_scoped_to_tmpdir forces any
  # reintroduced bare `mktemp` into a known directory.
  #
  # The fake `security`'s delay_after_secret_secs
  # keeps its stdout pipe open for 0.3s after handing
  # over the secret, so the read can't return until
  # that pipe closes.
  #
  # That gives a concurrent poller many chances to
  # observe a transient file before cleanup removes it.
  write_fake_security "$sandbox" "20260730082118Z" \
    "{\"claudeAiOauth\":{\"subscriptionType\":\"max\",\"raw\":\"$marker\"}}" "" "0.3"
  write_fake_mktemp_scoped_to_tmpdir "$sandbox"

  mkdir -p "$sandbox/scoped-tmp"
  sentinel="$sandbox/observed-marker-on-disk"
  rm -f "$sandbox/read-done" "$sentinel"

  (
    while [ ! -f "$sandbox/read-done" ]; do
      grep -rl "$marker" "$sandbox/scoped-tmp" >/dev/null 2>&1 && touch "$sentinel"
      sleep 0.01
    done
  ) &
  watch_pid=$!

  captured=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      TMPDIR="$sandbox/scoped-tmp" \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; read_subscription_tier_from_keychain' "$SCRIPT_UNDER_TEST" 2>&1
  )
  touch "$sandbox/read-done"
  wait "$watch_pid" 2>/dev/null

  observed_during_run="no"
  [ -f "$sentinel" ] && observed_during_run="yes"

  leaked_in_output="no"
  printf '%s' "$captured" | grep -q "$marker" && leaked_in_output="yes"

  leaked_in_tmp="no"
  grep -rl "$marker" "$sandbox/scoped-tmp" >/dev/null 2>&1 && leaked_in_tmp="yes"

  assert_eq \
    "StatusLineTierSegment > failure > should never write the raw credential value to disk, even transiently, at any point during the read" \
    "max no no no" "$captured $observed_during_run $leaked_in_output $leaked_in_tmp"
  rm -rf "$sandbox"
}

# The test above only proves the happy/failure paths never
# write the secret to disk; it says nothing about a read
# that gets interrupted partway through.
#
# auto-review flagged that the prior implementation wrote
# the secret to a mktemp file and relied on explicit
# `rm -f` cleanup on each return path.
#
# That cleanup never runs if the process itself is killed
# first (the realistic trigger: ccstatusline's own execSync
# sends SIGTERM on its own timeout).
#
# This test reproduces exactly that: the fake `security`
# sends SIGTERM to its own parent right after handing over
# the secret, then the test checks whether anything under
# the scoped TMPDIR ever held the marker.
it_should_never_leave_the_raw_credential_on_disk_when_the_reading_process_is_killed_mid_read() {
  local sandbox marker leaked_in_tmp
  sandbox="$(fresh_sandbox)"
  marker="RAW-SECRET-MARKER-do-not-leak-interrupted-4f2c"
  write_fake_security "$sandbox" "20260730082118Z" \
    "{\"claudeAiOauth\":{\"subscriptionType\":\"max\",\"raw\":\"$marker\"}}" \
    "kill-parent"
  write_fake_mktemp_scoped_to_tmpdir "$sandbox"

  mkdir -p "$sandbox/scoped-tmp"

  # Backgrounded + waited inside its own subshell, rather
  # than run directly.
  #
  # A directly-run foreground command that dies by signal
  # makes bash print an unsuppressable "Terminated: 15"
  # job-control notice to the CALLING shell's own stderr,
  # which no redirect on the command itself can catch.
  #
  # Wrapping in `( cmd & wait $! ) 2>/dev/null` makes the
  # subshell (not this test function's shell) the one that
  # waits, so its own redirect catches the notice instead.
  (
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      TMPDIR="$sandbox/scoped-tmp" \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; read_subscription_tier_from_keychain' \
      "$SCRIPT_UNDER_TEST" &
    wait $!
  ) >/dev/null 2>&1

  leaked_in_tmp="no"
  grep -rl "$marker" "$sandbox/scoped-tmp" >/dev/null 2>&1 && leaked_in_tmp="yes"

  assert_eq \
    "StatusLineTierSegment > failure > should never leave the raw credential on disk when the reading process is killed mid-read (e.g. ccstatusline's own execSync timeout)" \
    "no" "$leaked_in_tmp"
  rm -rf "$sandbox"
}

# Discovered while verifying the fix above
# (auto-review#F7): piping `security ... -w` straight into
# `jq` (instead of writing it to a temp file first) exposed
# a latent bug in run_with_timeout's watchdog subshell.
#
# That subshell inherited this function's stdout
# unredirected.
#
# On the success path, `kill "$watchdog_pid"` kills the
# subshell but not its own `sleep "$timeout_secs"`
# grandchild, which is left orphaned still holding the
# pipe's write end open.
#
# So `jq` never saw EOF until the orphaned sleep elapsed,
# and a routine successful Keychain read (rendered on every
# prompt) silently took the full configured timeout instead
# of returning immediately.
#
# This test proves a successful read stays fast regardless
# of how large the configured timeout is.
#
# It is the same bounded-elapsed-time pattern already used
# above for the password-prompt-hang test, just asserting
# the opposite direction (fast-on-success rather than
# bounded-on-hang).
it_should_return_well_under_the_timeout_on_a_successful_keychain_read() {
  local sandbox start end elapsed actual
  sandbox="$(fresh_sandbox)"
  write_fake_security "$sandbox" "20260730082118Z" '{"claudeAiOauth":{"subscriptionType":"max"}}'

  start=$(date +%s)
  actual=$(
    STATUSLINE_CREDENTIALS_FILE="$sandbox/nonexistent-credentials.json" \
      STATUSLINE_KEYCHAIN_TIMEOUT_SECS=5 \
      PATH="$sandbox:/usr/bin:/bin" \
      bash -c 'source "$0"; read_subscription_tier_from_keychain' "$SCRIPT_UNDER_TEST"
  )
  end=$(date +%s)
  elapsed=$((end - start))

  if [ "$elapsed" -le 2 ] && [ "$actual" = "max" ]; then
    actual="fast-and-correct"
  else
    actual="elapsed=${elapsed}s value=$actual"
  fi

  assert_eq \
    "StatusLineTierSegment > happy > should return well under the configured timeout on a successful Keychain read" \
    "fast-and-correct" "$actual"
  rm -rf "$sandbox"
}

it_should_read_subscriptiontype_from_the_credentials_file_when_one_exists
it_should_read_subscriptiontype_from_the_login_keychain_when_no_credentials_file_exists
it_should_invalidate_the_cached_tier_against_the_keychain_mdat_attribute_on_macos
it_should_invalidate_the_cached_tier_against_the_credentials_file_mtime_on_linux
it_should_treat_a_missing_cache_as_infinitely_stale_and_perform_a_fresh_read
it_should_re_read_subscriptiontype_when_the_invalidation_timestamp_is_newer_than_the_cache
it_should_serve_the_cached_tier_without_re_reading_the_credential_store_when_the_cache_is_not_stale
it_should_omit_the_tier_segment_rather_than_block_on_a_password_prompt
it_should_exit_zero_with_no_output_when_the_tier_is_unavailable
it_should_never_write_the_raw_credential_value_anywhere
it_should_never_leave_the_raw_credential_on_disk_when_the_reading_process_is_killed_mid_read
it_should_return_well_under_the_timeout_on_a_successful_keychain_read

# ============================================================
# describe("StatMtimeEpoch")
# ============================================================

# stat_mtime_epoch tries BSD's `stat -f %m` before GNU's
# `stat -c %Y`.
#
# On GNU coreutils, `-f` is not a format flag - it means the
# boolean `--file-system` flag.
#
# So `stat -f %m path` succeeds (printing a multi-line
# filesystem dump) and the `||` fallback to `stat -c %Y`
# never fires (auto-review#F2).
#
# write_fake_gnu_stat reproduces that divergence on this
# BSD/macOS dev host via a fake `stat` shim.

# write_fake_gnu_stat - installs a fake `stat` binary at
# "$bin_dir/stat" that mirrors GNU coreutils' own argument
# parsing.
#
# `-f` succeeds as the boolean --file-system flag (a
# multi-line dump, exit 0) while `-c %Y` is the real
# mtime-epoch format read.
write_fake_gnu_stat() {
  local bin_dir="$1"
  cat >"$bin_dir/stat" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "-f" ]; then
  cat <<'DUMP'
  File: "%m"
    ID: 0        Namelen: 255     Type: fakefs
Block size: 4096       Fundamental block size: 4096
Blocks: Total: 100     Free: 50      Available: 50
Inodes: Total: 100     Free: 50
DUMP
  exit 0
elif [ "$1" = "-c" ] && [ "$2" = "%Y" ]; then
  printf '1700000000\n'
  exit 0
fi
exit 1
EOF
  chmod +x "$bin_dir/stat"
}

it_should_return_a_single_line_integer_epoch_when_the_hosts_stat_treats_dash_f_as_a_gnu_boolean_flag() {
  local sandbox bin_dir target_file actual
  sandbox="$(fresh_sandbox)"
  bin_dir="$sandbox/bin"
  mkdir -p "$bin_dir"
  write_fake_gnu_stat "$bin_dir"
  target_file="$sandbox/some-file"
  printf 'irrelevant' >"$target_file"

  actual=$(
    PATH="$bin_dir:/usr/bin:/bin" \
      bash -c 'source "$0"; stat_mtime_epoch "$1"' "$SCRIPT_UNDER_TEST" "$target_file"
  )

  assert_eq \
    "StatMtimeEpoch > corner > should return a single-line integer epoch when the host's stat treats -f as a GNU boolean flag that succeeds" \
    "1700000000" "$actual"
  rm -rf "$sandbox"
}

it_should_return_a_single_line_integer_epoch_from_the_real_stat_on_this_bsd_macos_host() {
  local sandbox target_file expected actual
  sandbox="$(fresh_sandbox)"
  target_file="$sandbox/some-file"
  printf 'irrelevant' >"$target_file"
  expected=$(stat -f %m "$target_file" 2>/dev/null || stat -c %Y "$target_file" 2>/dev/null)

  actual=$(
    PATH="/usr/bin:/bin" \
      bash -c 'source "$0"; stat_mtime_epoch "$1"' "$SCRIPT_UNDER_TEST" "$target_file"
  )

  assert_eq \
    "StatMtimeEpoch > happy > should return a single-line integer epoch from the real stat on this BSD/macOS host" \
    "$expected" "$actual"
  rm -rf "$sandbox"
}

it_should_return_a_single_line_integer_epoch_when_the_hosts_stat_treats_dash_f_as_a_gnu_boolean_flag
it_should_return_a_single_line_integer_epoch_from_the_real_stat_on_this_bsd_macos_host

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

# ============================================================
# describe("StatusLineSpendLimit")
# ============================================================

# read_monthly_spend_limit reads the pay-as-you-go cap out of
# ccstatusline's own usage cache and renders it as dollars.
#
# The cache stores it in cents, so every case below is
# expressed in the API's own units.
#
# STATUSLINE_USAGE_CACHE overrides the cache path so each
# test drives a fixture instead of the maintainer's live
# account data.

# write_spend_limit_fixture - writes a usage cache carrying
# just the two fields read_monthly_spend_limit consults.
write_spend_limit_fixture() {
  local path="$1" enabled="$2" limit_cents="$3"
  cat >"$path" <<EOF
{"extraUsageEnabled":$enabled,"extraUsageLimit":$limit_cents}
EOF
}

it_should_render_a_whole_dollar_cap_without_cents() {
  local sandbox cache actual
  sandbox="$(fresh_sandbox)"
  cache="$sandbox/usage.json"
  write_spend_limit_fixture "$cache" true 100000

  actual=$(
    STATUSLINE_USAGE_CACHE="$cache" \
      bash -c 'source "$0"; read_monthly_spend_limit' "$SCRIPT_UNDER_TEST"
  )

  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSpendLimit > happy > should render a whole-dollar cap with no trailing cents" \
    '$1000' "$actual"
  rm -rf "$sandbox"
}

it_should_render_a_cap_that_does_not_divide_evenly_with_both_cents() {
  local sandbox cache actual
  sandbox="$(fresh_sandbox)"
  cache="$sandbox/usage.json"
  write_spend_limit_fixture "$cache" true 123456

  actual=$(
    STATUSLINE_USAGE_CACHE="$cache" \
      bash -c 'source "$0"; read_monthly_spend_limit' "$SCRIPT_UNDER_TEST"
  )

  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSpendLimit > corner > should keep both cents on a cap that does not divide evenly into dollars" \
    '$1234.56' "$actual"
  rm -rf "$sandbox"
}

it_should_render_nothing_when_the_account_has_extra_usage_disabled() {
  local sandbox cache actual status
  sandbox="$(fresh_sandbox)"
  cache="$sandbox/usage.json"

  # A disabled account still carries a limit value, so
  # omitting the segment has to key off the enabled flag
  # rather than off a missing cap.
  write_spend_limit_fixture "$cache" false 100000

  actual=$(
    STATUSLINE_USAGE_CACHE="$cache" \
      bash -c 'source "$0"; read_monthly_spend_limit' "$SCRIPT_UNDER_TEST"
  )
  status=$?

  assert_eq \
    "StatusLineSpendLimit > corner > should render nothing and exit zero when the account has extra usage disabled" \
    " 0" "$actual $status"
  rm -rf "$sandbox"
}

it_should_render_nothing_when_the_usage_cache_has_not_been_written_yet() {
  local sandbox actual status
  sandbox="$(fresh_sandbox)"

  # ccstatusline writes this file only once it has fetched
  # usage, so a first render on a cold cache must omit the
  # segment instead of surfacing an "[Exit: N]" token.
  actual=$(
    STATUSLINE_USAGE_CACHE="$sandbox/never-written.json" \
      bash -c 'source "$0"; read_monthly_spend_limit' "$SCRIPT_UNDER_TEST"
  )
  status=$?

  assert_eq \
    "StatusLineSpendLimit > failure > should render nothing and exit zero when the usage cache has not been written yet" \
    " 0" "$actual $status"
  rm -rf "$sandbox"
}

it_should_render_a_whole_dollar_cap_without_cents
it_should_render_a_cap_that_does_not_divide_evenly_with_both_cents
it_should_render_nothing_when_the_account_has_extra_usage_disabled
it_should_render_nothing_when_the_usage_cache_has_not_been_written_yet

# ============================================================
# describe("StatusLineSubagentCost")
# ============================================================

# render_subagent_cost reports what this session's sub-agents
# have spent, as an addendum to the main-session figure
# ccstatusline's own Session Cost widget renders.
#
# Each test drives a whole fake project directory, so the
# maintainer's live transcripts are never read.

# write_session_fixture - lays out one session's transcript
# path plus the sub-agent directory that belongs to it, and
# prints the main transcript path for the caller to feed in.
write_session_fixture() {
  local sandbox="$1"
  mkdir -p "$sandbox/projects/a-project/a-session/subagents"
  : >"$sandbox/projects/a-project/a-session.jsonl"
  printf '%s\n' "$sandbox/projects/a-project/a-session.jsonl"
}

# statusline_json - the fields the two cost subcommands read
# out of the payload Claude Code pipes into the status line.
#
# The reported cost stays in the payload because
# render_session_cost falls back to it whenever the
# transcript cannot be priced.
statusline_json() {
  local main_cost="$1" transcript_path="$2"
  jq -nc --argjson c "$main_cost" --arg t "$transcript_path" \
    '{cost: {total_cost_usd: $c}, transcript_path: $t}'
}

# write_subagent_transcript - one sub-agent's transcript,
# repeating the same reply shape under distinct message ids.
#
# Repeating a realistic reply is what lets a fixture reach a
# realistic session total, rather than inventing a single
# reply larger than any model could actually return.
write_subagent_transcript() {
  local path="$1" model="$2" usage_json="$3" reply_count="$4" i
  : >"$path"
  for ((i = 1; i <= reply_count; i++)); do
    printf '{"type":"assistant","message":{"id":"msg_%s_%02d","model":"%s","usage":%s}}\n' \
      "$(basename "$path" .jsonl)" "$i" "$model" "$usage_json" >>"$path"
  done
}

render_subagent_cost_for() {
  local main_cost="$1" transcript_path="$2"
  statusline_json "$main_cost" "$transcript_path" \
    | bash "$SCRIPT_UNDER_TEST" subagent-cost
}

it_should_report_every_subagents_spend_as_one_addendum() {
  local sandbox transcript subagents actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  subagents="$sandbox/projects/a-project/a-session/subagents"

  write_subagent_transcript "$subagents/agent-aa11.jsonl" claude-sonnet-5 \
    '{"input_tokens":137,"output_tokens":4213,"cache_creation_input_tokens":38093,"cache_read_input_tokens":55125}' 6
  write_subagent_transcript "$subagents/agent-bb22.jsonl" claude-haiku-4-5 \
    '{"input_tokens":89,"output_tokens":1247,"cache_creation_input_tokens":17032,"cache_read_input_tokens":21908}' 4

  actual="$(render_subagent_cost_for 1.37 "$transcript")"

  # The two sub-agents are summed into one term, kept apart
  # from the $1.37 Claude Code reports for the orchestrator.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > happy > should report every sub-agent's spend as a single addendum term" \
    '+ $1.46' "$actual"
  rm -rf "$sandbox"
}

it_should_bill_a_streamed_reply_once_at_its_final_token_count() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-cc33.jsonl"

  # Claude Code appends a reply once per flush while it
  # streams, so the same message id lands several times with
  # a growing output count and unchanged cache counts.
  printf '%s\n' \
    '{"type":"assistant","message":{"id":"msg_stream","model":"claude-sonnet-5","usage":{"cache_read_input_tokens":190000,"output_tokens":8}}}' \
    '{"type":"assistant","message":{"id":"msg_stream","model":"claude-sonnet-5","usage":{"cache_read_input_tokens":190000,"output_tokens":4213}}}' \
    >"$agent"

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # Billing both flushes would double the cache read and
  # reach $0.18 instead.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should bill a streamed reply once, at its final token count" \
    '+ $0.12' "$actual"
  rm -rf "$sandbox"
}

it_should_price_a_dated_model_alias_at_its_base_models_rate() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-dd44.jsonl"

  write_subagent_transcript "$agent" claude-haiku-4-5-20251001 \
    '{"output_tokens":2800,"cache_read_input_tokens":190000}' 4

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # Sonnet's rate would triple this to $0.40, and no rate at
  # all would report $0.00 with a floor marker.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should price a dated model alias at its base model's rate" \
    '+ $0.13' "$actual"
  rm -rf "$sandbox"
}

it_should_mark_the_total_as_a_floor_when_a_model_has_no_known_rate() {
  local sandbox transcript subagents actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  subagents="$sandbox/projects/a-project/a-session/subagents"

  write_subagent_transcript "$subagents/agent-ee55.jsonl" claude-sonnet-5 \
    '{"output_tokens":4213,"cache_read_input_tokens":55125}' 2
  write_subagent_transcript "$subagents/agent-ff66.jsonl" a-model-released-after-this-rate-table \
    '{"output_tokens":4213,"cache_read_input_tokens":55125}' 3

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # Reporting a bare $0.11 would read as the whole truth,
  # which is how a stale rate table hides a whole sub-agent's
  # spend behind a confident-looking number.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should mark the total as a floor when a sub-agent ran on a model with no known rate" \
    '+ ~$0.16' "$actual"
  rm -rf "$sandbox"
}

it_should_bill_only_the_subagents_belonging_to_this_session() {
  local sandbox transcript actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  write_subagent_transcript \
    "$sandbox/projects/a-project/a-session/subagents/agent-1177.jsonl" \
    claude-sonnet-5 '{"output_tokens":31000}' 2

  # Every session in a project shares this directory, so
  # anything found here belongs to sibling sessions.
  mkdir -p "$sandbox/projects/a-project/subagents"
  write_subagent_transcript \
    "$sandbox/projects/a-project/subagents/agent-2288.jsonl" \
    claude-sonnet-5 '{"output_tokens":31000}' 2

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should bill only the sub-agents belonging to this session, not a sibling session's" \
    '+ $0.93' "$actual"
  rm -rf "$sandbox"
}

it_should_skip_a_request_that_came_back_as_an_api_error() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-3399.jsonl"

  write_subagent_transcript "$agent" claude-sonnet-5 '{"output_tokens":31000}' 2
  printf '%s\n' \
    '{"type":"assistant","isApiErrorMessage":true,"message":{"id":"msg_failed","model":"claude-sonnet-5","usage":{"output_tokens":31000}}}' \
    >>"$agent"

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should skip a request that came back as an API error" \
    '+ $0.93' "$actual"
  rm -rf "$sandbox"
}

it_should_keep_summing_when_a_live_transcripts_last_line_is_half_written() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-44aa.jsonl"

  write_subagent_transcript "$agent" claude-sonnet-5 '{"output_tokens":31000}' 2

  # The status line renders while a sub-agent is still
  # writing, so it can catch a reply mid-append.
  printf '%s' '{"type":"assistant","message":{"id":"msg_partial","mod' >>"$agent"

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should keep summing when a live transcript's last line is only half written" \
    '+ $0.93' "$actual"
  rm -rf "$sandbox"
}

it_should_render_nothing_when_the_session_spawned_no_subagents() {
  local sandbox transcript actual status
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  actual="$(render_subagent_cost_for 2.25 "$transcript")"
  status=$?

  # The main figure is the Session Cost widget's to render,
  # so a session that never fanned out shows it alone rather
  # than trailing a "+ $0.00" that reports no spend.
  assert_eq \
    "StatusLineSubagentCost > happy > should render nothing when the session spawned no sub-agents" \
    " 0" "$actual $status"
  rm -rf "$sandbox"
}

it_should_render_nothing_when_priced_subagents_cost_under_a_cent() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-66cc.jsonl"

  # A single short reply, priced but far below the cent the
  # row can actually show.
  write_subagent_transcript "$agent" claude-sonnet-5 '{"output_tokens":100}' 1

  actual="$(render_subagent_cost_for 2.25 "$transcript")"

  assert_eq \
    "StatusLineSubagentCost > corner > should render nothing when every sub-agent is priced and together they cost under a cent" \
    "" "$actual"
  rm -rf "$sandbox"
}

it_should_still_report_a_floor_when_unpriced_subagents_cost_under_a_cent() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-77dd.jsonl"

  write_subagent_transcript "$agent" a-model-released-after-this-rate-table \
    '{"output_tokens":31000}' 2

  actual="$(render_subagent_cost_for 2.25 "$transcript")"

  # Suppressing this would read as "no sub-agents ran", when
  # what actually happened is that none of them could be
  # priced - the one case the marker exists to report.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should still report a floor when the only sub-agents that ran had no known rate" \
    '+ ~$0.00' "$actual"
  rm -rf "$sandbox"
}

it_should_render_no_addendum_when_the_session_has_no_transcript_to_price() {
  local actual status

  # The addendum needs a transcript path to locate the
  # sub-agent directory at all, and a non-zero exit would
  # render an "[Exit: N]" token in its place.
  #
  # This is also what keeps the addendum from rendering in
  # front of an empty main figure, since render_session_cost
  # is silent on the same missing field.
  actual="$(printf '{}' | bash "$SCRIPT_UNDER_TEST" subagent-cost)"
  status=$?

  assert_eq \
    "StatusLineSubagentCost > failure > should render nothing and exit zero when the session has no transcript to price" \
    " 0" "$actual $status"
}

it_should_carry_a_rate_for_every_model_subagents_run_on() {
  local actual expected

  # Pinned as a literal rather than read off the table,
  # because a test that asks the table which models it holds
  # can never notice one going missing.
  #
  # The list is what a sweep of every sub-agent transcript
  # on this setup actually turned up.
  #
  #   jq -r 'select(.type=="assistant")|.message.model' \
  #     ~/.claude/projects/*/*/subagents/*.jsonl | sort -u
  expected='claude-fable-5 claude-haiku-4-5 claude-opus-4-8 claude-opus-5 claude-sonnet-5'

  actual="$(bash -c 'source "$0"; printf "%s" "$MODEL_RATE_TABLE_JSON"' \
    "$SCRIPT_UNDER_TEST" | jq -r 'keys | join(" ")')"

  assert_eq \
    "StatusLineSubagentCost > happy > should carry a rate for every model this setup runs sub-agents on" \
    "$expected" "$actual"
}

it_should_price_every_model_the_rate_table_advertises() {
  local sandbox transcript subagents models model index actual has_marker
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  subagents="$sandbox/projects/a-project/a-session/subagents"

  # Reading the table back rather than listing models here
  # means a model added to it later is covered without
  # anyone remembering to touch this test.
  models="$(bash -c 'source "$0"; printf "%s" "$MODEL_RATE_TABLE_JSON"' \
    "$SCRIPT_UNDER_TEST" | jq -r 'keys[]')"

  index=0
  while IFS= read -r model; do
    index=$((index + 1))
    write_subagent_transcript "$subagents/agent-priced$index.jsonl" \
      "$model" '{"output_tokens":4213,"cache_read_input_tokens":55125}' 1
  done <<<"$models"

  actual="$(render_subagent_cost_for 0 "$transcript")"
  has_marker="no"
  case "$actual" in *"~"*) has_marker="yes" ;; esac

  assert_eq \
    "StatusLineSubagentCost > happy > should price every model the rate table advertises, with no floor marker" \
    "no" "$has_marker"
  rm -rf "$sandbox"
}

it_should_not_raise_the_floor_marker_for_a_turn_that_spent_no_tokens() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-55bb.jsonl"

  write_subagent_transcript "$agent" claude-sonnet-5 '{"output_tokens":31000}' 2

  # Claude Code logs a placeholder for a turn that never
  # reached the API, under a model name no rate table can
  # carry and with every token count at zero.
  printf '%s\n' \
    '{"type":"assistant","message":{"id":"msg_synthetic","model":"<synthetic>","usage":{"input_tokens":0,"output_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}' \
    >>"$agent"

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # Marking this total a floor would report a complete
  # figure as incomplete, and a marker that cries wolf is one
  # the reader learns to skip.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should not raise the floor marker for a turn that spent no tokens" \
    '+ $0.93' "$actual"
  rm -rf "$sandbox"
}

it_should_bill_a_1hour_cache_write_at_double_the_5minute_rate() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-1h88.jsonl"

  # The flat field carries 87 tokens above the nested 1-hour
  # bucket, mirroring the live transcript's own residue - the
  # untyped remainder still has to enter the sum, billed at
  # the 5-minute rate.
  printf '%s\n' \
    '{"type":"assistant","message":{"id":"msg_1h","model":"claude-sonnet-5","usage":{"input_tokens":53,"output_tokens":612,"cache_read_input_tokens":9188,"cache_creation_input_tokens":48300,"cache_creation":{"ephemeral_1h_input_tokens":48213,"ephemeral_5m_input_tokens":0}}}}' \
    >"$agent"

  actual="$(render_subagent_cost_for 0 "$transcript")"

  # A 1-hour cache write bills at 6e-6 (2x sonnet's input
  # rate). Billing it at the 5-minute rate (3.75e-6) instead
  # would under-price this entry to $0.19.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSubagentCost > corner > should bill a 1-hour cache write at double the 5-minute rate" \
    '+ $0.30' "$actual"
  rm -rf "$sandbox"
}

it_should_bill_a_5minute_cache_write_at_its_own_lower_rate() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-5m77.jsonl"

  printf '%s\n' \
    '{"type":"assistant","message":{"id":"msg_5m","model":"claude-sonnet-5","usage":{"input_tokens":41,"output_tokens":389,"cache_read_input_tokens":6720,"cache_creation_input_tokens":22150,"cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":22150}}}}' \
    >"$agent"

  actual="$(render_subagent_cost_for 0 "$transcript")"

  assert_eq \
    "StatusLineSubagentCost > corner > should bill a 5-minute cache write at its own lower rate" \
    '+ $0.09' "$actual"
  rm -rf "$sandbox"
}

it_should_bill_a_legacy_entrys_flat_cache_field_at_the_5minute_rate() {
  local sandbox transcript agent actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  agent="$sandbox/projects/a-project/a-session/subagents/agent-leg66.jsonl"

  # An older entry with no nested cache_creation breakdown at
  # all - the whole flat field has to land in the sum, or a
  # pre-TTL-split transcript's cache writes silently vanish.
  write_subagent_transcript "$agent" claude-sonnet-5 \
    '{"input_tokens":19,"output_tokens":274,"cache_read_input_tokens":5031,"cache_creation_input_tokens":15820}' 1

  actual="$(render_subagent_cost_for 0 "$transcript")"

  assert_eq \
    "StatusLineSubagentCost > corner > should bill a legacy entry's flat cache field at the 5-minute rate when it carries no TTL breakdown" \
    '+ $0.07' "$actual"
  rm -rf "$sandbox"
}

it_should_report_every_subagents_spend_as_one_addendum
it_should_bill_a_1hour_cache_write_at_double_the_5minute_rate
it_should_bill_a_5minute_cache_write_at_its_own_lower_rate
it_should_bill_a_legacy_entrys_flat_cache_field_at_the_5minute_rate
it_should_carry_a_rate_for_every_model_subagents_run_on
it_should_price_every_model_the_rate_table_advertises
it_should_render_nothing_when_the_session_spawned_no_subagents
it_should_bill_a_streamed_reply_once_at_its_final_token_count
it_should_not_raise_the_floor_marker_for_a_turn_that_spent_no_tokens
it_should_price_a_dated_model_alias_at_its_base_models_rate
it_should_mark_the_total_as_a_floor_when_a_model_has_no_known_rate
it_should_render_nothing_when_priced_subagents_cost_under_a_cent
it_should_still_report_a_floor_when_unpriced_subagents_cost_under_a_cent
it_should_bill_only_the_subagents_belonging_to_this_session
it_should_skip_a_request_that_came_back_as_an_api_error
it_should_keep_summing_when_a_live_transcripts_last_line_is_half_written
it_should_render_no_addendum_when_the_session_has_no_transcript_to_price

# ============================================================
# describe("StatusLineSessionCost")
# ============================================================

# render_session_cost prices this session's own transcript,
# because the figure Claude Code reports is an in-process
# counter that restarts at zero on "claude --continue" and
# then reads $0.00 for a session that has already spent.
#
# The transcript is the durable record of that spend, so
# pricing it is what makes the number survive a resume.

# write_main_transcript - the session's own transcript, in
# the same priced-reply shape a sub-agent's carries.
#
# Named apart from the sub-agent helper because which file a
# fixture lands in is the whole distinction the two disjoint
# scans rest on, and a call site reading "subagent" at the
# main transcript's path would hide that.
write_main_transcript() {
  write_subagent_transcript "$@"
}

render_session_cost_for() {
  local main_cost="$1" transcript_path="$2"
  statusline_json "$main_cost" "$transcript_path" \
    | bash "$SCRIPT_UNDER_TEST" session-cost
}

it_should_price_the_sessions_own_transcript_rather_than_trust_the_reported_figure() {
  local sandbox transcript actual status
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  write_main_transcript "$transcript" claude-sonnet-5 '{"output_tokens":31000}' 2

  actual="$(render_session_cost_for 0 "$transcript")"
  status=$?

  # The payload reports 0 - exactly what a resumed session
  # sends - so anything but the transcript's own $0.93 means
  # the reset counter won.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSessionCost > happy > should price the session's own transcript so a resumed session keeps its spend" \
    '$0.93 0' "$actual $status"
  rm -rf "$sandbox"
}

it_should_mark_the_session_total_as_a_floor_when_a_model_has_no_known_rate() {
  local sandbox transcript actual status
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  write_main_transcript "$transcript" claude-sonnet-5 '{"output_tokens":31000}' 2
  printf '%s\n' \
    '{"type":"assistant","message":{"id":"msg_main_unrated","model":"a-model-released-after-this-rate-table","usage":{"output_tokens":31000}}}' \
    >>"$transcript"

  actual="$(render_session_cost_for 0 "$transcript")"
  status=$?

  # The rate table ages every time Anthropic ships a model,
  # so the total has to say "at least this much" rather than
  # quietly bill the new model at nothing.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSessionCost > corner > should mark the session total as a floor when the session ran on a model with no known rate" \
    '~$0.93 0' "$actual $status"
  rm -rf "$sandbox"
}

it_should_report_the_cost_claude_code_sent_when_the_transcript_cannot_be_read() {
  local sandbox actual
  sandbox="$(fresh_sandbox)"

  actual="$(render_session_cost_for 4.75 "$sandbox/a-session-that-was-never-written.jsonl")"

  # Falling back keeps the widget on screen through a failed
  # scan. Dropping to nothing would be worse than the reset
  # figure this pricing replaces, because the reader cannot
  # tell a vanished widget from a free session.
  #
  # literal dollar sign, not a shell expansion
  # shellcheck disable=SC2016
  assert_eq \
    "StatusLineSessionCost > failure > should report the cost Claude Code sent when the session transcript cannot be read" \
    '$4.75' "$actual"
  rm -rf "$sandbox"
}

it_should_render_no_session_cost_when_neither_the_transcript_nor_the_payload_has_one() {
  local actual status

  # Claude Code omits the cost block until the first reply
  # lands, and a non-zero exit would render an "[Exit: N]"
  # token in its place.
  actual="$(printf '{}' | bash "$SCRIPT_UNDER_TEST" session-cost)"
  status=$?

  assert_eq \
    "StatusLineSessionCost > failure > should render nothing and exit zero when neither the transcript nor Claude Code offers a cost" \
    " 0" "$actual $status"
}

it_should_price_nothing_rather_than_wait_on_stdin_when_given_no_transcripts() {
  local actual status

  # jq reads stdin when it is handed no file arguments, so an
  # empty transcript list would hang the widget until its
  # timeout rather than fail fast.
  actual="$(printf '' | bash -c 'source "$0"; price_transcripts' "$SCRIPT_UNDER_TEST")"
  status=$?

  assert_eq \
    "StatusLineSessionCost > failure > should price nothing rather than wait on stdin when asked to price no transcripts at all" \
    "1 " "$status $actual"
}

it_should_price_the_sessions_own_transcript_rather_than_trust_the_reported_figure
it_should_mark_the_session_total_as_a_floor_when_a_model_has_no_known_rate
it_should_report_the_cost_claude_code_sent_when_the_transcript_cannot_be_read
it_should_render_no_session_cost_when_neither_the_transcript_nor_the_payload_has_one
it_should_price_nothing_rather_than_wait_on_stdin_when_given_no_transcripts

# ============================================================
# describe("StatusLineSessionDuration")
# ============================================================

# The duration subcommand reads the session's start from its
# transcript for the same reason the cost does: the elapsed
# figure Claude Code reports sits in the same in-process
# block and restarts at zero on "claude --continue".

# iso8601_utc - an epoch second as the fractional-second UTC
# stamp Claude Code writes into a transcript entry.
#
# Both date flavours are tried because BSD date takes -r and
# GNU date takes -d, and the suites run on macOS and Linux.
iso8601_utc() {
  local epoch="$1"
  date -u -r "$epoch" '+%Y-%m-%dT%H:%M:%S.123Z' 2>/dev/null \
    || date -u -d "@$epoch" '+%Y-%m-%dT%H:%M:%S.123Z' 2>/dev/null
}

# write_timestamped_transcript - a transcript carrying one
# entry per given ISO-8601 stamp, in the order given.
#
# The literal "-" writes a file-history-snapshot entry
# instead. A real transcript often opens with one, and it
# carries no timestamp at all, so reading the first line
# rather than the earliest would find nothing there.
write_timestamped_transcript() {
  local path="$1" stamp
  shift
  : >"$path"
  for stamp in "$@"; do
    if [ "$stamp" = "-" ]; then
      printf '{"type":"file-history-snapshot","messageId":"msg_snapshot","snapshot":{}}\n' >>"$path"
    else
      printf '{"type":"assistant","timestamp":"%s","message":{"id":"msg_%s"}}\n' \
        "$stamp" "$stamp" >>"$path"
    fi
  done
}

render_duration_for() {
  local duration_ms="$1" transcript_path="$2"
  jq -nc --argjson d "$duration_ms" --arg t "$transcript_path" \
    '{cost: {total_duration_ms: $d}, transcript_path: $t}' \
    | bash "$SCRIPT_UNDER_TEST" duration
}

it_should_report_hours_since_the_transcripts_first_entry() {
  local sandbox transcript now start actual status
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  now="$(date +%s)"
  start=$((now - 3 * 3600 - 900))

  write_timestamped_transcript "$transcript" "$(iso8601_utc "$start")"

  actual="$(render_duration_for 0 "$transcript")"
  status=$?

  # The payload reports 0 ms - exactly what a resumed session
  # sends - so anything but 3h means the reset counter won.
  assert_eq \
    "StatusLineSessionDuration > happy > should render the decorated segment · ⏱ Nh with hours since the session's first transcript entry so a resumed session keeps its age" \
    "· ⏱ 3h 0" "$actual $status"
  rm -rf "$sandbox"
}

it_should_report_hours_from_the_earliest_entry_when_the_transcript_is_out_of_order() {
  local sandbox transcript now start actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  now="$(date +%s)"
  start=$((now - 3 * 3600 - 900))

  write_timestamped_transcript "$transcript" \
    "$(iso8601_utc $((start + 7200)))" \
    "$(iso8601_utc "$start")" \
    "$(iso8601_utc $((start + 3600)))"

  actual="$(render_duration_for 0 "$transcript")"

  # Concurrent sub-agent writes interleave entries, so the
  # first line is not reliably the earliest one.
  assert_eq \
    "StatusLineSessionDuration > corner > should render the decorated segment from the earliest entry when the transcript's entries are out of chronological order" \
    "· ⏱ 3h" "$actual"
  rm -rf "$sandbox"
}

it_should_report_hours_from_the_earliest_entry_when_the_transcript_opens_untimestamped() {
  local sandbox transcript now start actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"
  now="$(date +%s)"
  start=$((now - 3 * 3600 - 900))

  write_timestamped_transcript "$transcript" \
    "-" \
    "$(iso8601_utc "$start")" \
    "$(iso8601_utc $((start + 7200)))"

  actual="$(render_duration_for 0 "$transcript")"

  # A file-history-snapshot opening line carries no timestamp
  # field, so reading line 1 would find no start at all and
  # fall back to the reset counter.
  assert_eq \
    "StatusLineSessionDuration > corner > should render the decorated segment from the earliest timestamped entry when the transcript opens with an entry carrying none" \
    "· ⏱ 3h" "$actual"
  rm -rf "$sandbox"
}

it_should_report_the_duration_claude_code_sent_when_the_transcript_cannot_be_read() {
  local sandbox actual
  sandbox="$(fresh_sandbox)"

  actual="$(render_duration_for 21600000 "$sandbox/a-session-that-was-never-written.jsonl")"

  assert_eq \
    "StatusLineSessionDuration > failure > should render the decorated segment using the duration Claude Code sent when the session transcript cannot be read" \
    "· ⏱ 6h" "$actual"
  rm -rf "$sandbox"
}

it_should_render_no_duration_when_neither_the_transcript_nor_the_payload_has_one() {
  local actual status

  # Claude Code omits the cost block until the first reply
  # lands, and a non-zero exit would render an "[Exit: N]"
  # token in its place.
  actual="$(printf '{}' | bash "$SCRIPT_UNDER_TEST" duration)"
  status=$?

  # Regression guard: the whole decorated segment (separator,
  # clock label, figure, unit) must be absent, not merely the
  # figure - ccstatusline has no cross-widget dependency, so a
  # decoration-only widget left rendering on its own would
  # strand "· ⏱  h" on the line even though this figure is gone.
  assert_eq \
    "StatusLineSessionDuration > failure > should render the whole decorated segment as absent, not merely the figure, when neither the transcript nor Claude Code offers a duration" \
    " 0" "$actual $status"
}

it_should_report_hours_since_the_transcripts_first_entry
it_should_report_hours_from_the_earliest_entry_when_the_transcript_is_out_of_order
it_should_report_hours_from_the_earliest_entry_when_the_transcript_opens_untimestamped
it_should_report_the_duration_claude_code_sent_when_the_transcript_cannot_be_read
it_should_render_no_duration_when_neither_the_transcript_nor_the_payload_has_one

# ============================================================
# describe("StatusLineAdvisorSegment")
# ============================================================

# The advisor field reports the advisor that actually ran on
# this session's newest turn, read out of the session
# transcript rather than the advisorModel setting.
#
# Each test drives a whole fake project directory plus an
# explicit settings-file override, so the maintainer's live
# transcripts and real settings.json are never read.

# read_advisor_for - the advisor field as ccstatusline would
# render it, for one transcript and one settings file.
read_advisor_for() {
  local transcript_path="$1" settings_file="$2"
  jq -nc --arg t "$transcript_path" '{transcript_path: $t}' \
    | STATUSLINE_SETTINGS_FILE="$settings_file" bash "$SCRIPT_UNDER_TEST" advisor
}

it_should_report_the_advisor_that_ran_on_the_most_recent_turn() {
  local sandbox transcript actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  printf '%s\n' \
    '{"type":"user","isSidechain":false,"message":{"role":"user"}}' \
    '{"type":"assistant","isSidechain":false,"advisorModel":"claude-opus-5","message":{"id":"msg_014Qk"}}' \
    '{"type":"assistant","isSidechain":false,"advisorModel":"claude-opus-5","message":{"id":"msg_015Rm"}}' \
    >"$transcript"

  # Deliberately a settings file carrying a different value:
  # a stale settings read would surface "sonnet" here.
  printf '{"advisorModel":"sonnet"}' >"$sandbox/settings.json"

  actual="$(read_advisor_for "$transcript" "$sandbox/settings.json")"

  assert_eq \
    "StatusLineAdvisorSegment > happy > should report the advisor that ran on the session's most recent turn" \
    "opus" "$actual"
  rm -rf "$sandbox"
}

it_should_report_no_advisor_after_the_advisor_is_turned_off_mid_session() {
  local sandbox transcript actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  # The turns before the operator ran /advisor off still carry
  # their advisor, and only the newest turn reports the state
  # the field is meant to show.
  printf '%s\n' \
    '{"type":"assistant","isSidechain":false,"advisorModel":"claude-opus-5","message":{"id":"msg_016Sn"}}' \
    '{"type":"assistant","isSidechain":false,"message":{"id":"msg_017To"}}' \
    >"$transcript"

  printf '{"advisorModel":"opus"}' >"$sandbox/settings.json"

  actual="$(read_advisor_for "$transcript" "$sandbox/settings.json")"

  assert_eq \
    "StatusLineAdvisorSegment > corner > should report no advisor once the operator turns the advisor off mid-session" \
    "none" "$actual"
  rm -rf "$sandbox"
}

it_should_report_the_main_sessions_advisor_rather_than_a_subagents() {
  local sandbox transcript actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  # A sub-agent's turns land in this same transcript and can
  # be the newest entries in it, while running an advisor of
  # their own that says nothing about the main session.
  printf '%s\n' \
    '{"type":"assistant","isSidechain":false,"advisorModel":"claude-opus-5","message":{"id":"msg_018Up"}}' \
    '{"type":"assistant","isSidechain":true,"advisorModel":"claude-sonnet-5","message":{"id":"msg_019Vq"}}' \
    >"$transcript"

  actual="$(read_advisor_for "$transcript" "$sandbox/absent-settings.json")"

  assert_eq \
    "StatusLineAdvisorSegment > corner > should report the main session's own advisor rather than a sub-agent's" \
    "opus" "$actual"
  rm -rf "$sandbox"
}

it_should_fall_back_to_the_configured_advisor_before_the_first_reply_lands() {
  local sandbox transcript actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  # A session's whole first turn has no reply in its
  # transcript yet, so the configured value is the only answer
  # available.
  printf '%s\n' \
    '{"type":"user","isSidechain":false,"message":{"role":"user"}}' \
    >"$transcript"

  printf '{"advisorModel":"opus"}' >"$sandbox/settings.json"

  actual="$(read_advisor_for "$transcript" "$sandbox/settings.json")"

  assert_eq \
    "StatusLineAdvisorSegment > corner > should fall back to the configured advisor before the session's first reply lands" \
    "opus" "$actual"
  rm -rf "$sandbox"
}

it_should_keep_reading_the_advisor_when_the_live_transcripts_last_line_is_half_written() {
  local sandbox transcript actual
  sandbox="$(fresh_sandbox)"
  transcript="$(write_session_fixture "$sandbox")"

  # The status line re-renders while Claude Code is appending,
  # so the tail can be a fragment.
  #
  # Aborting on it would drop the field to the settings value
  # for exactly as long as the write is in flight.
  printf '%s\n' \
    '{"type":"assistant","isSidechain":false,"advisorModel":"claude-opus-5","message":{"id":"msg_020Wr"}}' \
    >"$transcript"
  printf '{"type":"assistant","isSidechain":false,"advis' >>"$transcript"

  actual="$(read_advisor_for "$transcript" "$sandbox/absent-settings.json")"

  assert_eq \
    "StatusLineAdvisorSegment > corner > should keep reading the advisor when the live transcript's last line is half-written" \
    "opus" "$actual"
  rm -rf "$sandbox"
}

it_should_report_the_advisor_that_ran_on_the_most_recent_turn
it_should_report_no_advisor_after_the_advisor_is_turned_off_mid_session
it_should_report_the_main_sessions_advisor_rather_than_a_subagents
it_should_fall_back_to_the_configured_advisor_before_the_first_reply_lands
it_should_keep_reading_the_advisor_when_the_live_transcripts_last_line_is_half_written

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
