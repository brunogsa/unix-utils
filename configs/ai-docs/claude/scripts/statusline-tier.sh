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
#     the advisor family that ran on this session's newest
#     turn ("opus"), or the literal "none", read from the
#     transcript_path on stdin.
#
#   statusline-tier.sh duration
#     whole-hour session length, read from
#     cost.total_duration_ms on stdin.
#
#   statusline-tier.sh spend-limit
#     the org's monthly extra-usage cap in dollars, read
#     from ccstatusline's own usage cache.
#
#   statusline-tier.sh subagent-cost
#     what every sub-agent this session spawned has spent,
#     as an addendum to ccstatusline's own Session Cost
#     widget: "+ $19.01".
#
# Usage (as the last stage of the statusLine.command pipe,
# fed ccstatusline's RENDERED output rather than JSON).
#
#   ccstatusline | statusline-tier.sh filter
#     rounds percents, trims edge padding, and keeps whichever
#     second row the account's tier can actually populate.
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

usage_cache_path() {
  printf '%s\n' "${STATUSLINE_USAGE_CACHE:-$HOME/.cache/ccstatusline/usage.json}"
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
#
# `$@` itself is started in its own process group (`set -m`
# around the background start, restored right after) so the
# TERM on timeout reaches its whole descendant tree via
# `kill -TERM -$cmd_pid`, not just the direct child.
#
# Confirmed empirically, not merely reasoned: a command
# that backgrounds a grandchild and exits leaves that
# grandchild holding the caller's capture pipe open when
# only the direct child is signaled.
#
# The caller then hangs indefinitely, well past
# timeout_secs, instead of returning.
#
# Signaling the whole process group kills the grandchild
# too, and the caller returns immediately.
#
# `security find-generic-password` without `-w` was
# checked directly against this host's real binary and
# spawns no child process at all, so it cannot hit this
# path either way.
#
# Whether the `-w` secret read's interactive "Always
# Allow" prompt could ever exhibit this shape was not
# directly testable in a sandboxed environment.
#
# That prompt is handled out-of-process by SecurityAgent
# per Security.framework's XPC design, not by a fork of
# `security` itself - see `otool -L /usr/bin/security`.
#
# So the process-group fix is applied defensively for
# that path rather than left unproven.
# ----------------------------------------------------------

run_with_timeout() {
  local timeout_secs="$1"
  shift
  set -m
  "$@" &
  local cmd_pid=$!
  set +m
  (
    sleep "$timeout_secs"

    # The plain-pid fallback only fires if the negated-pgid
    # form fails outright (no such process group) - it never
    # runs after a successful group kill, so it can't
    # double-signal.
    kill -0 "$cmd_pid" 2>/dev/null \
      && { kill -TERM "-$cmd_pid" 2>/dev/null || kill -TERM "$cmd_pid" 2>/dev/null; }
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
# Rendered-output filter
# ----------------------------------------------------------

# PACING_ROW_LINE_NUMBER / SPEND_ROW_LINE_NUMBER - which
# rendered line carries the 5h/7d pacing segments and which
# carries the monthly spend, per the `lines` array in
# configs/ai-docs/claude/ccstatusline/settings.json.
PACING_ROW_LINE_NUMBER=2
SPEND_ROW_LINE_NUMBER=3

# KEEP_EVERY_ROW - the sentinel for "drop nothing".
#
# 0 is safe as a sentinel because perl's `$.` numbers input
# lines from 1, so it can never match a real row.
KEEP_EVERY_ROW=0

# filter_rendered_lines - post-processes ccstatusline's
# rendered stdout on the way to Claude Code's status line.
#
# It exists because ccstatusline's config language cannot
# express either of these.
#
# First, it rounds "NN.N%" down to "NN%" and strips the edge
# padding that `defaultPaddingSide: left` leaves on each
# line.
#
# Second, it keeps only the second row the account's plan can
# actually populate, since each row is dead weight on the
# other kind of plan.
#
# Enterprise gets no `rate_limits` in the statusline JSON, so
# every pacing widget renders a zeroed bar against a reset
# timer that never resolves - "5h 0% <empty bar> in
# [Loading]".
#
# A plan without pay-as-you-go extra usage has no monthly cap
# to spend against, so the spend row renders "n/a of "
# instead.
#
# Letting ccstatusline drop either row on its own is not an
# option: it only skips a line whose visible text is empty,
# and both rows carry custom-text labels ("5h", "in", "of")
# that always render.
#
# The tier comes from resolve_tier - the same cached read
# the `tier` subcommand uses - rather than from matching the
# rendered "[Enterprise]" token.
#
# Matching rendered text would re-break silently every time
# that label's format changes, and it has already changed
# twice.
filter_rendered_lines() {
  local tier drop_row="$KEEP_EVERY_ROW"

  tier="$(resolve_tier)" || tier=""

  # resolve_tier caches `subscriptionType` verbatim, which
  # the credential store currently spells lowercase.
  #
  # Comparing case-insensitively costs one call and keeps a
  # future casing change from silently swapping the rows,
  # which nothing else would surface.
  tier="$(printf '%s' "$tier" | tr '[:upper:]' '[:lower:]')"

  # A failed tier read keeps both rows: showing one row that
  # reads wrong beats hiding the only place either budget
  # appears, and nothing downstream could tell the user which
  # row went missing.
  if [ "$tier" = "enterprise" ]; then
    drop_row="$PACING_ROW_LINE_NUMBER"
  elif [ -n "$tier" ]; then
    drop_row="$SPEND_ROW_LINE_NUMBER"
  fi

  STATUSLINE_DROP_ROW_LINE="$drop_row" \
    perl -ne '
      next if $. == $ENV{STATUSLINE_DROP_ROW_LINE};
      s/(\d+\.\d+)%/int($1+0.5)."%"/ge;
      s/^((?:\x1b\[[0-9;]*m)*)\xc2\xa0+/$1/;
      s/\xc2\xa0(?=(?:\x1b\[[0-9;]*m)*$)//g;
      print;
    '
}

# ----------------------------------------------------------
# Advisor field
# ----------------------------------------------------------

# How much of a live transcript's tail the advisor read
# covers - enough for the newest main-chain assistant entry,
# whose tool_use blocks can run long.
#
# Bounded because a long session's transcript reaches tens
# of megabytes, and the status line re-renders constantly.
: "${STATUSLINE_ADVISOR_TAIL_BYTES:=1048576}"

# read_advisor_field - the advisor this session's newest turn
# actually ran, as a bare model family ("opus"), or "none".
#
# Reads the session transcript, not advisorModel in
# settings.json: /advisor in any other session rewrites that
# file, and every running session re-derives from it.
#
# So the setting answers "configured globally", never "ran
# here" - and --advisor at launch never writes it at all.
read_advisor_field() {
  local payload transcript_path advisor
  payload="$(cat)"
  transcript_path="$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null)"

  if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    advisor="$(read_effective_advisor "$transcript_path")"
    if [ -n "$advisor" ]; then
      model_family_label "$advisor"
      return 0
    fi
  fi

  model_family_label "$(read_configured_advisor)"
}

# read_effective_advisor - the advisorModel stamped on the
# newest main-chain assistant entry, "none" when that entry
# carries no advisor, and empty when the transcript holds no
# such entry yet.
#
# Claude Code stamps the RESOLVED advisor per assistant
# message, so the absent-field case also covers a configured
# advisor that could not advise that turn's request model.
read_effective_advisor() {
  local transcript_path="$1"

  # A sub-agent's turns land in this same file and can be the
  # newest entries in it, so isSidechain is what separates
  # the main session's own advisor from theirs.
  #
  # fromjson? skips both a tail-truncated first line and a
  # half-written last line rather than aborting the read
  # while Claude Code is mid-append.
  tail -c "$STATUSLINE_ADVISOR_TAIL_BYTES" "$transcript_path" 2>/dev/null \
    | jq -Rnr '
      reduce (inputs | fromjson? // empty) as $entry (null;
        if $entry.type == "assistant" and ($entry.isSidechain | not)
        then $entry
        else . end
      )
      | if . == null then empty else (.advisorModel // "none") end
    '
}

# read_configured_advisor - the advisorModel setting, or the
# literal string "none" when unset (matches this repo's own
# default: the committed settings.json carries no
# advisorModel key).
read_configured_advisor() {
  local settings_file
  settings_file="$(claude_settings_path)"
  if [ -f "$settings_file" ]; then
    jq -r '.advisorModel // "none"' "$settings_file" 2>/dev/null || printf 'none\n'
  else
    printf 'none\n'
  fi
}

# model_family_label - a model id reduced to its family, so
# the field reads at one width whichever source answered it:
# "claude-opus-5" and "opus" both render "opus".
#
# An id matching neither shape prints verbatim, surfacing
# something unrecognized instead of mangling it.
model_family_label() {
  local model="${1##*claude-}"
  printf '%s\n' "${model%%-[0-9]*}"
}

# ----------------------------------------------------------
# Monthly extra-usage spend cap
# ----------------------------------------------------------

# read_monthly_spend_limit - the org's monthly extra-usage
# cap, formatted as "$1000".
#
# ccstatusline ships `extra-usage-used`, which renders the
# dollars already spent, but no widget renders the cap on its
# own - so only this half needs custom code.
#
# The number comes from ccstatusline's own usage cache rather
# than a second call to /api/oauth/usage.
#
# That endpoint is rate-limited and lock-guarded, and the
# status line re-renders on every event, so a private fetch
# here would compete with ccstatusline's for the same quota.
#
# Whole dollars when the cap divides evenly, 2 decimals
# otherwise: an org cap is set in round dollars, and printing
# "$1000.00" beside a "$209.01" spend reads as false
# precision.
#
# Anything unreadable prints nothing and exits 0, which is
# ccstatusline's omit-this-widget contract - a non-zero exit
# would render a visible "[Exit: N]" token instead.
read_monthly_spend_limit() {
  local cache_file limit_cents
  cache_file="$(usage_cache_path)"
  [ -f "$cache_file" ] || return 0

  # An account with extra usage disabled has no cap to show,
  # so the `false` case must omit the segment rather than
  # print "$0".
  limit_cents="$(
    jq -r '
      select(.extraUsageEnabled == true)
      | .extraUsageLimit // empty
    ' "$cache_file" 2>/dev/null
  )"
  [ -z "$limit_cents" ] && return 0

  awk -v cents="$limit_cents" 'BEGIN {
    dollars = cents / 100
    if (dollars == int(dollars)) printf "$%d\n", dollars
    else printf "$%.2f\n", dollars
  }'
}

# ----------------------------------------------------------
# Session cost, including sub-agent spend
# ----------------------------------------------------------

# MODEL_RATE_TABLE_JSON - dollars per token, per model.
#
# Claude Code's own cost.total_cost_usd counts only the
# orchestrator's tokens.
#
# A sub-agent's tokens never reach that tracker, and
# Anthropic closed the request to change it as "not
# planned" (anthropics/claude-code#43945).
#
# So the sub-agent half has to be priced here from raw
# transcript usage, which needs a rate per model.
#
# The rates are vendored rather than shelled out to a
# local cost tool because ccusage, ccburn, and codeburn
# were each checked and none of them reads the subagents/
# directory at all.
#
# So none can produce this figure, whatever pricing data
# it carries.
#
# Values mirror the rate table those tools build from,
# model_prices_and_context_window.json in
# github.com/BerriAI/litellm.
#
# Anthropic bills a cache write at 1.25x its model's input
# rate and a cache read at 0.1x, which is why each pair
# tracks the input rate rather than varying on its own.
readonly MODEL_RATE_TABLE_JSON='{
  "claude-opus-5":    { "input": 5e-6,  "output": 25e-6, "cache_write": 6.25e-6, "cache_read": 0.5e-6 },
  "claude-opus-4-8":  { "input": 5e-6,  "output": 25e-6, "cache_write": 6.25e-6, "cache_read": 0.5e-6 },
  "claude-sonnet-5":  { "input": 2e-6,  "output": 10e-6, "cache_write": 2.5e-6,  "cache_read": 0.2e-6 },
  "claude-haiku-4-5": { "input": 1e-6,  "output": 5e-6,  "cache_write": 1.25e-6, "cache_read": 0.1e-6 },
  "claude-fable-5":   { "input": 10e-6, "output": 50e-6, "cache_write": 12.5e-6, "cache_read": 1e-6 }
}'

: "${STATUSLINE_SUBAGENT_SCAN_TIMEOUT_SECS:=3}"

# subagent_transcript_dir - where one session's sub-agent
# transcripts live, derived from the main transcript path
# Claude Code puts in its statusline JSON.
#
# ccstatusline's own sub-agent reader also accepts a
# sibling <dir>/subagents, but that form is not scoped to a
# session.
#
# Pricing it would bill this session for every other
# session sharing the project directory, so only the
# session-scoped form is accepted here.
subagent_transcript_dir() {
  local transcript_path="$1" dir stem
  dir="$(dirname "$transcript_path")"
  stem="$(basename "$transcript_path" .jsonl)"
  printf '%s\n' "$dir/$stem/subagents"
}

# sum_subagent_cost - prints "<dollars> <unpriced-count>"
# for every sub-agent transcript in the given directory.
#
# Entries are keyed by message id and the last one wins,
# because a streamed reply is appended once per flush with
# a growing output_tokens count.
#
# Summing the raw lines instead would bill the same reply
# several times over.
#
# cache_creation_input_tokens is used rather than the
# nested cache_creation breakdown, since older entries
# carry the flat field alone and reading only the nested
# form silently drops their cache writes.
#
# Lines are parsed with fromjson? so a half-written line at
# the tail of a live transcript is skipped instead of
# aborting the whole sum.
#
# An entry spending no tokens is never counted as unpriced,
# whatever its model.
#
# Claude Code logs placeholders for turns that never reached
# the API - "<synthetic>" among them - and letting those
# raise the floor marker would report a complete figure as
# incomplete.
sum_subagent_cost() {
  local subagents_dir="$1"
  [ -d "$subagents_dir" ] || return 1

  local transcripts=("$subagents_dir"/agent-*.jsonl)
  [ -e "${transcripts[0]:-}" ] || return 1

  jq -Rnr --argjson rates "$MODEL_RATE_TABLE_JSON" '
    def base_model: sub("-20[0-9]{6}$"; "");

    def total_tokens:
      (.input_tokens // 0)
      + (.output_tokens // 0)
      + (.cache_creation_input_tokens // 0)
      + (.cache_read_input_tokens // 0);

    reduce (inputs | fromjson? // empty) as $entry ({};
      if $entry.type == "assistant"
        and ($entry.isApiErrorMessage | not)
        and ($entry.message.id != null)
        and ($entry.message.usage != null)
      then .[$entry.message.id] = $entry.message
      else . end
    )
    | [ .[] | { rate: $rates[(.model // "") | base_model], usage } ]
    | (
        map(select(.rate == null and (.usage | total_tokens) > 0))
        | length
      ) as $unpriced
    | (
        map(
          select(.rate != null)
          | (.usage.input_tokens // 0) * .rate.input
          + (.usage.output_tokens // 0) * .rate.output
          + (.usage.cache_creation_input_tokens // 0) * .rate.cache_write
          + (.usage.cache_read_input_tokens // 0) * .rate.cache_read
        )
        | add // 0
      ) as $cost
    | "\($cost) \($unpriced)"
  ' "${transcripts[@]}" 2>/dev/null
}

# render_subagent_cost - what this session's sub-agents
# have spent, as an addendum to ccstatusline's own Session
# Cost widget: "+ $19.01".
#
# The main half is left to that widget rather than
# reproduced here, since it already formats the same
# cost.total_cost_usd and omits itself when it is absent.
#
# A total carrying tokens from a model absent from
# MODEL_RATE_TABLE_JSON is prefixed "~", marking it a floor
# rather than the real number.
#
# ccusage is the cautionary case: its pinned rate table
# predates claude-sonnet-5, so it reports a confident
# $0.00 for an entire session on that model.
#
# Nothing prints when the main figure is missing, so this
# addendum can never render alone in front of an empty
# slot.
#
# Nothing prints either when the sub-agents cost too little
# to show and every one of them was priced, since "+ $0.00"
# widens the row to report no spend.
#
# Printing nothing and exiting 0 is ccstatusline's
# omit-this-widget contract - a non-zero exit renders a
# visible "[Exit: N]" token.
render_subagent_cost() {
  local payload main_cost transcript_path subagent_total
  payload="$(cat)"

  main_cost="$(printf '%s' "$payload" | jq -r '.cost.total_cost_usd // empty' 2>/dev/null)"
  [ -z "$main_cost" ] && return 0

  transcript_path="$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null)"
  [ -z "$transcript_path" ] && return 0

  subagent_total="$(
    run_with_timeout "$STATUSLINE_SUBAGENT_SCAN_TIMEOUT_SECS" \
      sum_subagent_cost "$(subagent_transcript_dir "$transcript_path")"
  )"
  [ -z "$subagent_total" ] && return 0

  awk -v subagent_total="$subagent_total" 'BEGIN {
    split(subagent_total, parts, " ")
    cost = sprintf("%.2f", parts[1])
    unpriced = parts[2] + 0
    if (cost == "0.00" && unpriced == 0)
      exit
    printf "+ %s$%s\n", (unpriced > 0 ? "~" : ""), cost
  }'
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
  statusline-tier.sh advisor    Print the advisor family that ran on this
                                 session's newest turn as "opus", or "none",
                                 reading transcript_path from the Claude
                                 Code statusline JSON on stdin. Falls back
                                 to the advisorModel setting before the
                                 session's first reply lands.
  statusline-tier.sh duration   Print whole-hour session duration, reading
                                 cost.total_duration_ms from the Claude
                                 Code statusline JSON on stdin.
  statusline-tier.sh spend-limit
                                Print the org's monthly extra-usage cap as
                                 "$1000", read from ccstatusline's usage
                                 cache.
  statusline-tier.sh subagent-cost
                                Print what every sub-agent this session
                                 spawned has spent as "+ $12.34", an
                                 addendum to ccstatusline's own Session
                                 Cost widget, reading transcript_path from
                                 the Claude Code statusline JSON on stdin.
                                 A "~" prefix means some model had no known
                                 rate, so the figure is a floor.
  statusline-tier.sh filter     Post-process ccstatusline's RENDERED output
                                 on stdin: round percents, trim edge
                                 padding, and keep only the second row this
                                 account's tier can populate.

Examples:
  statusline-tier.sh tier
  echo '{"cost":{"total_duration_ms":7500000}}' | statusline-tier.sh duration
  ccburn collect | ccstatusline | statusline-tier.sh filter
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
    spend-limit)
      read_monthly_spend_limit
      ;;
    subagent-cost)
      render_subagent_cost
      ;;
    filter)
      filter_rendered_lines
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
