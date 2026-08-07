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
repo_root="$(cd "$script_dir/../../../../.." && pwd)"
SETTINGS_JSON="$repo_root/configs/ai-docs/claude/settings.json"
CCSTATUSLINE_CONFIG_SRC="$repo_root/configs/ai-docs/claude/ccstatusline/settings.json"

# configured_statusline_command - the live (working-tree, not committed)
# statusLine.command from settings.json. Reading the working tree rather
# than HEAD lets the StatusLineRender tests go RED before the wiring
# commit lands and GREEN right after the Edit, with no commit in between.
configured_statusline_command() {
  jq -r '.statusLine.command' "$SETTINGS_JSON"
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

# write_fake_ccburn - installs a fake `ccburn` binary that mirrors the real
# one's confirmed contract (`ccburn collect` reads Claude Code's stdin JSON,
# side-effects a usage snapshot, and passes the same JSON through on
# stdout unchanged) — here reduced to the pass-through half, since the
# snapshot write is ccburn's own tested behavior, not this repo's.
write_fake_ccburn() {
  local bin_dir="$1"
  cat >"$bin_dir/ccburn" <<'EOF'
#!/usr/bin/env bash
cat
EOF
  chmod +x "$bin_dir/ccburn"
}

# write_fake_ccstatusline - installs a fake `ccstatusline` binary that
# reads the SAME config shape the real one reads from
# "$HOME/.config/ccstatusline/settings.json" (confirmed via
# ccstatusline.js's DEFAULT_SETTINGS_PATH) and the same stdin JSON payload
# a Custom Command widget receives (confirmed via CustomCommand.tsx's
# render(): the full payload piped to item.commandPath's stdin). For each
# configured widget it either execs the real commandPath (custom-command
# widgets — this is what actually proves our config wires statusline-tier.sh
# correctly) or extracts a fixed jq path for the handful of built-in widget
# types this repo's config uses (a stand-in for ccstatusline's own,
# out-of-scope rendering). Each present value is emitted as "[id-or-type:
# value]"; a widget whose value is empty is omitted entirely, mirroring the
# real widget's documented "empty output -> segment omitted" behavior
# (AC-11) without needing the real npm package as a test dependency.
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

# marker_value - extracts "value" from one "[marker:value]" chunk in a
# render_status_line output string, or prints nothing if the marker is
# absent (an omitted segment).
marker_value() {
  local output="$1" marker="$2"
  printf '%s' "$output" | grep -oE "\[${marker}:[^]]*\]" | sed -E "s/\[${marker}:([^]]*)\]/\1/"
}

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
  resets_5h=$((now + 5040))   # elapsed 12960s of an 18000s window -> expected 72%
  resets_7d=$((now + 453600)) # elapsed 151200s of a 604800s window -> expected 25%
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

  local tier advisor duration exp5h exp7d builtins_present marker
  tier=$(marker_value "$output" "tier")
  advisor=$(marker_value "$output" "advisor")
  duration=$(marker_value "$output" "duration")
  exp5h=$(marker_value "$output" "expected5h")
  exp7d=$(marker_value "$output" "expected7d")

  builtins_present=true
  for marker in model thinking-effort context-length context-percentage \
    session-cost session-usage reset-timer weekly-usage weekly-reset-timer; do
    [ -n "$(marker_value "$output" "$marker")" ] || builtins_present=false
  done

  assert_eq \
    "StatusLineRender > happy > should render tier, model, effort, context window, advisor, context percent, cost, duration and both windows" \
    "Max opus 2 72 25 true" "$tier $advisor $duration $exp5h $exp7d $builtins_present"
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
  # Deliberately no $sandbox/.claude/settings.json at all: read_advisor_field
  # falls back to "none" when the file is missing, matching this repo's own
  # committed default (no advisorModel key).
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

  # No "cost" key at all: the session-cost segment's data is unavailable.
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

it_should_render_tier_model_effort_context_window_advisor_context_percent_cost_duration_and_both_windows
it_should_render_the_literal_none_for_the_advisor_field_when_no_advisormodel_is_configured
it_should_render_the_remaining_segments_when_the_cost_segment_has_no_data_yet
it_should_render_nothing_and_exit_zero_when_ccstatusline_or_ccburn_is_not_installed

# ============================================================
# describe("StatusLineRealRender")
# ============================================================
# Unlike StatusLineRender above (which drives a FAKE ccstatusline that
# extracts one raw value per widget into "[marker:value]" markers), this
# test drives the REAL, installed `ccstatusline` npm binary against the
# committed config. The fake binary models widget composition rather than
# performing it, so it cannot catch a bug IN composition — a built-in
# widget rendering its own label (e.g. "Ctx: ") alongside this config's
# custom-text label, or a padding "merge" landing on the wrong widget. Only
# the real binary's actual stdout proves those are absent.
#
# ccburn is still faked (pass-through) per this repo's hard rule: `ccburn
# collect` reads and writes the maintainer's real usage-history file, so no
# test may invoke it for real. The synthetic payload below supplies
# rate_limits directly on stdin, which the real ccstatusline widgets read
# straight from that JSON with no network fetch — confirmed by reading
# ccstatusline's own extractUsageDataFromRateLimits()/
# prefetchUsageDataIfNeeded(): the network path only runs when a
# rate_limits field is still missing after this check.

# real_ccstatusline_dir - the directory holding the actually-installed
# ccstatusline binary (from install.sh's `npm install -g ccstatusline`), or
# empty when it is not on PATH. Resolved once at file load, not inside the
# test, so every use sees the same value.
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

  now=$(date +%s)
  resets_5h=$((now + 5040))   # elapsed 12960s of an 18000s window -> expected 72%
  resets_7d=$((now + 453600)) # elapsed 151200s of a 604800s window -> expected 25%
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
  # Strip ANSI color/style codes (colorLevel:3 in the committed config), then
  # normalize ccstatusline's own padding character - confirmed via a raw
  # byte dump to be U+00A0 NO-BREAK SPACE (UTF-8 0xC2 0xA0), not a plain
  # ASCII space - down to a plain space. A real terminal renders both
  # identically, but a byte-literal " " pattern below would silently never
  # match the actual output without this normalization.
  output=$(
    printf '%s\n' "$raw_output" \
      | sed -E 's/\x1b\[[0-9;]*m//g' \
      | sed $'s/\xc2\xa0/ /g'
  )
  line2=$(printf '%s\n' "$output" | sed -n '2p')

  local doubled_labels stray_percent_space stray_duration_space six_h_present
  # Each of these is a built-in widget's own label, rendered only when the
  # widget lacks rawValue:true. None may appear: this config supplies its
  # own custom-text labels ("Context", "Advisor", "$", "5h", "7d", ...)
  # instead.
  doubled_labels=$(printf '%s' "$output" | grep -cE \
    'Ctx: |Ctx Used: |Ctx Left: |Cost: |Session: |Weekly: |Reset: |Weekly Reset: ')
  # A digit followed by 1+ spaces then "%" is the
  # merge:"no-padding"-is-missing symptom on expected5h/expected7d (e.g.
  # the reported "29 %").
  stray_percent_space=$(printf '%s' "$output" | grep -cE '[0-9][[:space:]]+%')
  # A digit followed by 2+ spaces then "h" at end of line is the
  # merge:"no-padding" flag sitting on the wrong widget (duration-unit, a
  # no-op there, instead of duration) — the reported "6  h". Anchored to
  # end-of-line so this doesn't false-positive on unrelated "<digit>  h..."
  # text elsewhere on the line (e.g. "Sonnet 5  high").
  stray_duration_space=$(printf '%s' "$output" | grep -cE '[0-9][[:space:]]{2,}h[[:space:]]*$')
  six_h_present=no
  printf '%s' "$output" | grep -qF '6h' && six_h_present=yes

  assert_eq \
    "StatusLineRealRender > happy > should render each builtin widget raw with no duplicate label and no stray padding" \
    "0 0 0 yes" "$doubled_labels $stray_percent_space $stray_duration_space $six_h_present"

  # ---- maintainer-reviewed formatting fixup (six exact changes) ----
  # Extended in place, on the same captured $output, rather than as
  # separate it_ functions: this test is the only one that pays the cost
  # of spinning up the real ccstatusline binary, and every assertion below
  # reads that one already-captured render, so a second function would
  # only duplicate the expensive setup for free extra assertions.
  local line1 no_decimal_percent rounds_up_correctly max_tight ctx_shape \
    duration_label_shape no_redundant_dollar_label token_count_untouched \
    cost_untouched pacing_5h_shape pacing_7d_shape line1_closes_clean \
    line2_closes_clean
  line1=$(printf '%s\n' "$output" | sed -n '1p')

  # 1. No "<digits>.<digits>%" survives anywhere: every percentage widget's
  # ccstatusline toFixed(1) output must have gone through the awk rounding
  # filter appended to statusLine.command.
  no_decimal_percent=$(printf '%s' "$output" | grep -cE '[0-9]+\.[0-9]+%')
  assert_eq \
    "StatusLineRealRender > happy > no <digits>.<digits>% survives anywhere" \
    "0" "$no_decimal_percent"

  # 2. Rounding is real, not truncation: context_window.used_percentage is
  # fed as 47.86, which ccstatusline's own toFixed(1) turns into "47.9" -
  # only a real round-half-up filter prints "48%"; a truncating one would
  # print "47%".
  rounds_up_correctly=no
  printf '%s' "$output" | grep -qF 'Ctx 48%' && rounds_up_correctly=yes
  assert_eq \
    "StatusLineRealRender > happy > rounding is real (a .5+ fixture rounds up, not truncates)" \
    "yes" "$rounds_up_correctly"

  # 3. [Max] replaces "[ max ]": capitalized, no padding inside the brackets.
  max_tight=no
  printf '%s' "$output" | grep -qF '[Max]' && max_tight=yes
  assert_eq \
    "StatusLineRealRender > happy > [Max] renders capitalized with no internal padding" \
    "yes" "$max_tight"

  # 4. Ctx replaces the Context label, tight single space before the value
  # (same fixture value as assertion 2, so this doubles as the Ctx shape
  # check).
  ctx_shape=no
  printf '%s' "$output" | grep -qF 'Ctx 48%' && ctx_shape=yes
  assert_eq \
    "StatusLineRealRender > happy > Ctx replaces Context with a tight single space" \
    "yes" "$ctx_shape"

  # 5. Duration gains a tight "⏱ " label ahead of it.
  duration_label_shape=no
  printf '%s' "$output" | grep -qF '⏱ 6h' && duration_label_shape=yes
  assert_eq \
    "StatusLineRealRender > happy > duration gains a tight ⏱ label" \
    "yes" "$duration_label_shape"

  # 6. The redundant "$" custom-text label is gone - session-cost's own "$"
  # prefix is the only one left, so "$" is never followed by whitespace
  # then another "$".
  no_redundant_dollar_label=yes
  printf '%s' "$output" | grep -qE '\$[[:space:]]+\$' && no_redundant_dollar_label=no
  assert_eq \
    "StatusLineRealRender > happy > the redundant \$ custom-text label is gone" \
    "yes" "$no_redundant_dollar_label"

  # 7. The token count (a "<digits>.<digits>k" shape, e.g. "95.7k") and the
  # 2-decimal cost survive the % filter untouched - the filter must only
  # ever match "<digits>.<digits>%", never a bare decimal with no percent
  # sign. Matched by shape rather than a literal number: the exact token
  # count is a function of this fixture's context_window_size/
  # used_percentage, not a value the filter itself produces.
  token_count_untouched=no
  printf '%s' "$output" | grep -qE '[0-9]+\.[0-9]+k' && token_count_untouched=yes
  cost_untouched=no
  # shellcheck disable=SC2016 # literal grep -F pattern, not a shell expansion
  printf '%s' "$output" | grep -qF '$1.23' && cost_untouched=yes
  assert_eq \
    "StatusLineRealRender > happy > the token-count decimal and the 2-decimal cost survive the % filter untouched" \
    "yes yes" "$token_count_untouched $cost_untouched"

  # 8. Pacing segments restructure to "<usage>% (of <expected>%, resets
  # <reset>)" - same widget order as before, different literal separators.
  pacing_5h_shape=no
  printf '%s' "$output" | grep -qE '40% \(of 72%, resets [^)]+\)' && pacing_5h_shape=yes
  pacing_7d_shape=no
  printf '%s' "$output" | grep -qE '55% \(of 25%, resets [^)]+\)' && pacing_7d_shape=yes
  assert_eq \
    "StatusLineRealRender > happy > pacing segments restructure to '<usage>% (of <expected>%, resets <reset>)'" \
    "yes yes" "$pacing_5h_shape $pacing_7d_shape"

  # 9. Neither line is truncated at a realistic width: each ends on its
  # actual last widget instead of being cut mid-token by ccstatusline's own
  # flex/compact mode.
  line1_closes_clean=no
  [[ "$line1" == *6h ]] && line1_closes_clean=yes
  line2_closes_clean=no
  [[ "$line2" == *')' ]] && line2_closes_clean=yes
  assert_eq \
    "StatusLineRealRender > happy > neither line is truncated at a realistic width" \
    "yes yes" "$line1_closes_clean $line2_closes_clean"

  printf '# line1 (%d chars): %s\n' "${#line1}" "$line1" >&2
  printf '# line2 (%d chars): %s\n' "${#line2}" "$line2" >&2
  rm -rf "$sandbox"
}

it_should_render_each_builtin_widget_raw_with_no_duplicate_label_and_no_stray_padding

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
  # No credentials file at all: this host-independent, existence-based
  # branch is what actually forces the Keychain/mdat code path — see
  # decision #3 in /tmp/implement_substeps_claude-cost-controls_6.md for
  # why this is not gated on `uname`.
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
  # This exercises the credentials-file/mtime branch via a faked file, not
  # a live Linux run (this dev host is macOS) — see decision #3.
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
  write_fake_security "$sandbox" "20260730082118Z" "{\"claudeAiOauth\":{\"subscriptionType\":\"max\",\"raw\":\"$marker\"}}"

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
# describe("StatMtimeEpoch")
# ============================================================
# stat_mtime_epoch tries BSD's `stat -f %m` before GNU's `stat -c %Y`.
# On GNU coreutils, `-f` is not a format flag - it means the boolean
# `--file-system` flag, so `stat -f %m path` succeeds (printing a
# multi-line filesystem dump) and the `||` fallback to `stat -c %Y`
# never fires (auto-review#F2). write_fake_gnu_stat reproduces that
# divergence on this BSD/macOS dev host via a fake `stat` shim.

# write_fake_gnu_stat - installs a fake `stat` binary at "$bin_dir/stat"
# that mirrors GNU coreutils' own argument parsing: `-f` succeeds as
# the boolean --file-system flag (a multi-line dump, exit 0) while
# `-c %Y` is the real mtime-epoch format read.
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

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
