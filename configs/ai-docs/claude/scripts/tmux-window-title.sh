#!/bin/bash
# tmux-window-title - Set the current tmux window's title to a given string.
#
# Claude Code calls this to label the window with a brief title of the current
# work, so the user can find the right window at a glance. It overwrites the
# title outright -- no prefixes, no stacking (that policy lives with the caller,
# not here).
#
# Usage:
#   tmux-window-title.sh <title>       # set the base title
#   tmux-window-title.sh --help
#
#   Counter bumps, one per kind of compaction:
#     --bump-subagent-counter   # +1 subagent compaction
#     --bump-counter            # +1 main-session compaction
#     --reset-counter           # drop the counter entirely
#
# Compaction counter:
#   The title carries an optional trailing counter -- how many
#   context compactions this Claude session has survived. It
#   gives the user at-a-glance visibility into how churned a
#   session's context is.
#
#   It has two halves, because the two kinds of compaction do
#   not mean the same thing. "auth-fix[3]" is three MAIN-session
#   compactions, the ones that erase this window's own
#   conversation. "auth-fix[3+9]" adds nine subagent
#   compactions -- churn the session delegated away rather than
#   absorbed, which says its subagents are running hot while
#   its own context is not.
#
#   A zero subagent half renders as nothing at all: a session
#   whose subagents never compacted reads "[3]", never "[3+0]".
#   The "+" costs two of a 24-char budget, so it appears only
#   once it carries information.
#
#   The count lives in the title itself (single source of
#   truth), managed by SessionStart hooks: a bump on `compact`,
#   --reset-counter on `startup`/`clear`. Setting a base title
#   PRESERVES an existing counter, so Claude re-titling on a
#   topic shift does not reset the count.
#
# Root anchor:
#   The title the user learned to recognize is the one the window carried
#   BEFORE its first compaction. Left alone, Claude's later re-titles replace
#   it outright and the window stops being identifiable mid-session.
#
#   So the first --bump-counter freezes the then-current base as the session's
#   ROOT, in the pane option @claude_root_title. Every later title renders as
#   "<root>/<compact-focus>[N]" -- the anchor the user scans for, plus where
#   the work has actually moved.
#
#   The compact-focus half always renders the label as-is, even when it
#   repeats a word the root already carries -- there is no dedup/aggregation.
#   A rooted title renders bare (root only, no "/") only when the label is
#   IDENTICAL to the root, or when nothing has been set post-root yet.
#
#   Root and compact-focus each get a FIXED room inside the 24-char cap: 16
#   for the root (MAX_LEN_PLAIN, deliberately equal to the pre-compaction cap)
#   and 8 for the compact-focus half (FOCUS_ROOM_BASELINE, the leading "/"
#   included -- so "/" plus up to 7 label chars). 16 + 8 = 24 = MAX_LEN_COMPACTED.
#
#   A counter wider than the narrowest possible "[N]" steals width from BOTH
#   sides, proportionally 3:2 (root:compact-focus) -- see split_rooted_rooms.
#   There is no reallocation between the two: once a side's room clamps to 0
#   it stays 0, it is never handed back to the other side.
#
#   If the compact-focus room ever drops below 2 chars (not even room for the
#   "/" plus one label char), the field is dropped entirely rather than
#   rendering a dangling "/[N]".
#
#   The root is stored in tmux, not left to Claude's memory, precisely because
#   compaction is what erases the first turn: after it, Claude no longer knows
#   what the original title was and cannot preserve it by judgment alone.
#
#   It is immutable for the life of the session -- only --reset-counter
#   (SessionStart `startup`/`clear`) drops it, letting the next session set its
#   own. A pane that Claude never titled grows no root, so the window keeps the
#   plain behavior instead of anchoring to the user's shell name.
#
# Behavior:
#   - Outside tmux ($TMUX unset): no-op, exit 0. Lets the caller invoke it
#     unconditionally without guarding on the terminal.
#   - Empty/missing title (default mode): error to stderr, exit 1.
#   - Sets `automatic-rename off` first, because with it on (the user's default)
#     tmux re-derives the name from the running command and the title would not
#     stick.
#   - Renames the window that Claude runs in ($TMUX_PANE), not whatever window
#     is currently focused.
#   - Caps the whole title, counter included: 16 chars before any compaction,
#     24 once a counter exists. The wider cap is spent only where the rooted
#     "<root>/<compact-focus>[N]" form needs it. The counter suffix is always
#     kept intact and the text is truncated to fit, so the count stays
#     readable even as the title shrinks. The caller should still keep titles
#     short.
#   - On the first rename for a pane (any mode), captures the pre-Claude window
#     name and automatic-rename flag into pane options ($TMUX_PANE-scoped
#     @claude_prev_window_name / @claude_prev_auto_rename) before overwriting
#     either -- first-set-wins, so later calls in the same session don't
#     clobber the captured original. A separate SessionEnd hook restores it.
#
# Examples:
#   tmux-window-title.sh "fix-auth-bug"
#     spaces are converted to hyphens too
#   tmux-window-title.sh "tmux-titles"
#   tmux-window-title.sh --bump-counter
#     "tmux-titles" -> "tmux-titles[1]"
#   tmux-window-title.sh --bump-subagent-counter
#     "tmux-titles[1]" -> "tmux-titles[1+1]"
#   tmux-window-title.sh --reset-counter
#     "tmux-titles[1+1]" -> "tmux-titles"
#   tmux-window-title.sh "hook-tests"
#     after that bump, roots the title, compact-focus capped to its 8-char
#     (incl. "/") room: "tmux-titles/hook-t[1]"
#   tmux-window-title.sh "tmux-titles-cap"
#     the label renders as-is, even repeating a root word, truncated to its
#     8-char (incl. "/") room: "tmux-titles/tmux-t[1]"

set -euo pipefail

# Print the comment header (lines 2..first non-comment line) as help text,
# stripping the leading "# ". Stops at the first non-# line so it never leaks
# code below the header, regardless of where the header ends.
print_help() {
  awk 'NR==1 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
}

# Two caps, both counting the "[N]" suffix. A pre-compaction title is a bare
# base and stays at the tight 16 the caller is told to aim for; once a counter
# exists the title may also carry the root, so it gets room for both.
MAX_LEN_PLAIN=16
MAX_LEN_COMPACTED=24

# Separates the frozen root from the compact-focus label in a rooted title.
ROOT_SEPARATOR="/"

# Fixed room the compact-focus half gets inside a rooted title, before any
# counter-width steal -- the leading ROOT_SEPARATOR included, so "/" plus up
# to 7 label chars. Paired with MAX_LEN_PLAIN (the root's own fixed room):
# 16 + 8 = 24 = MAX_LEN_COMPACTED.
FOCUS_ROOM_BASELINE=8

# A counter wider than the narrowest possible "[N]" steals width from BOTH
# the root and the compact-focus room, proportionally ROOT_STEAL_RATIO :
# FOCUS_STEAL_RATIO -- see split_rooted_rooms for the exact formula.
ROOT_STEAL_RATIO=3
FOCUS_STEAL_RATIO=2
STEAL_RATIO_TOTAL=$(( ROOT_STEAL_RATIO + FOCUS_STEAL_RATIO ))

# Parse a trailing compaction counter from a title. Echoes the
# counter BODY without its brackets -- "3" or "3+2" -- and
# nothing when there is none. Strict: only digits (with at most
# one "+" between them) inside brackets at the very end count,
# so a base title never picks up a stray "[x]" as a counter.
parse_counter() {
  if [[ "$1" =~ \[([0-9]+(\+[0-9]+)?)\]$ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  fi
}

# Echo the base title with a trailing counter removed
# (unchanged if none).
strip_counter() {
  if [[ "$1" =~ ^(.*)\[[0-9]+(\+[0-9]+)?\]$ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  else
    printf '%s' "$1"
  fi
}

# Echo the main-session half of a counter body.
#
# A body with no "+" is a main count alone, which is also how
# every title written before the split reads -- so an existing
# "[3]" on a live window keeps meaning three main compactions
# instead of being reinterpreted when this script updates.
main_count() {
  local body=${1:-}

  if [ -z "$body" ]; then
    printf '0'
    return
  fi

  printf '%s' "${body%%+*}"
}

# Echo the subagent half of a counter body, or 0 when the body
# carries no "+" half at all.
subagent_count() {
  local body=${1:-}

  case "$body" in
    *+*) printf '%s' "${body#*+}" ;;
    *)   printf '0' ;;
  esac
}

# Compose a counter body from its two halves.
#
# A zero subagent half is dropped entirely rather than rendered
# as "+0": the suffix competes with the title text for a 24-char
# budget, so it earns its two characters only once a subagent
# has actually compacted.
compose_counter() {
  local main=$1 sub=$2

  if [ "$sub" -gt 0 ]; then
    printf '%s+%s' "$main" "$sub"
    return
  fi

  printf '%s' "$main"
}

# Recover the compact-focus half of an already-rendered title.
#
# The window name is a RENDERED title, and rendering is not
# idempotent -- feeding "<root>/<compact-focus>" back in would compose
# a second root onto it and squeeze both halves again. On a
# pre-root title there is no separator and this is a no-op.
compact_focus_base() {
  local base
  base=$(strip_counter "$1")
  printf '%s' "${base##*"$ROOT_SEPARATOR"}"
}

# Cut a title segment down to `max` chars, dropping a trailing hyphen the cut
# may leave so the result never reads as a dangling word break.
truncate_segment() {
  local text=$1 max=$2
  if [ "${#text}" -gt "$max" ]; then
    text="${text:0:max}"
    text="${text%-}"
  fi
  printf '%s' "$text"
}

# Split the rooted pair's two fixed rooms (MAX_LEN_PLAIN for the root,
# FOCUS_ROOM_BASELINE for the compact-focus half) given a counter-suffix
# length. A counter wider than the narrowest possible "[N]" steals from BOTH
# sides proportionally 3:2 (root:compact-focus), round-half-up, and each
# room clamps at 0 rather than go negative -- there is no reallocation
# between sides. Echoes "<root_room> <focus_room>".
split_rooted_rooms() {
  local suffix_len=$1
  local root_steal=$(( (suffix_len * ROOT_STEAL_RATIO + STEAL_RATIO_TOTAL / 2) / STEAL_RATIO_TOTAL ))
  local focus_steal=$(( suffix_len - root_steal ))

  local root_room=$(( MAX_LEN_PLAIN - root_steal ))
  [ "$root_room" -lt 0 ] && root_room=0
  local focus_room=$(( FOCUS_ROOM_BASELINE - focus_steal ))
  [ "$focus_room" -lt 0 ] && focus_room=0

  printf '%s %s' "$root_room" "$focus_room"
}

# Render the window title, capped per MAX_LEN_PLAIN / MAX_LEN_COMPACTED. The
# counter is kept whole and the text truncated to make room, so the count stays
# visible even as the title shrinks.
#
# The root is prepended only when there is one AND the base still differs
# from it -- an identical base renders bare rather than doubled.
render_title() {
  local base=$1 counter=$2 root=${3:-} suffix=""
  [ -n "$counter" ] && suffix="[$counter]"

  local max_len=$MAX_LEN_PLAIN
  [ -n "$counter" ] && max_len=$MAX_LEN_COMPACTED

  local budget=$(( max_len - ${#suffix} ))
  # An absurdly wide counter can outgrow the whole cap by
  # itself. A negative budget fed into truncate_segment's
  # "${text:0:max}" is a bash version trap: bash < 4.2 errors,
  # bash >= 4.2 reads a negative length as "N chars off the
  # end" and returns MORE text, not less -- clamp it away.
  [ "$budget" -lt 0 ] && budget=0

  if [ -n "$root" ]; then
    local focus_label=$base
    [ "$focus_label" = "$root" ] && focus_label=""

    if [ -n "$focus_label" ]; then
      local rooms root_room focus_room
      rooms=$(split_rooted_rooms "${#suffix}")
      root_room=${rooms%% *}
      focus_room=${rooms#* }

      # Below a 2-char room there's not even space for the "/" plus one
      # label char -- drop the field entirely rather than render a
      # dangling "/[N]".
      local focus_out=""
      [ "$focus_room" -ge 2 ] && focus_out=$(truncate_segment "${ROOT_SEPARATOR}${focus_label}" "$focus_room")

      printf '%s%s%s' "$(truncate_segment "$root" "$root_room")" "$focus_out" "$suffix"
      return
    fi

    # Nothing to add: the label is identical to the root, so it renders
    # alone rather than as "auth-fix/auth-fix".
    base=$root
  fi

  printf '%s%s' "$(truncate_segment "$base" "$budget")" "$suffix"
}

# Read the name of the window Claude runs in ($TMUX_PANE), not whatever window
# is currently focused.
current_title() {
  tmux display-message -t "$TMUX_PANE" -p '#{window_name}'
}

# First-set-wins capture of the window's pre-Claude name and automatic-rename
# flag, into pane options (not window options) so the "original" ties to this
# specific Claude pane/session -- relevant if the window ever holds more than
# one pane. A SessionEnd hook (separate script) reads these back to restore
# the window once Claude's session ends. `show-options -v` on an option that
# was never set exits non-zero with nothing on stdout, and exits 0 with the
# value once it has been -- that's the "already captured?" check below.
capture_prev_state() {
  if tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" >/dev/null 2>&1; then
    return 0  # already captured earlier in this session
  fi

  local prev_name prev_auto
  prev_name=$(current_title)

  # automatic-rename is a window option; an unset local value means the
  # window inherits the global default, so fall back to that -- the restore
  # hook needs a literal "on"/"off" captured here, never an empty string.
  prev_auto=$(tmux show-options -w -t "$TMUX_PANE" -v automatic-rename)
  if [ -z "$prev_auto" ]; then
    prev_auto=$(tmux show-options -g -v automatic-rename)
  fi

  tmux set-option -p -t "$TMUX_PANE" -- "@claude_prev_window_name" "$prev_name"
  tmux set-option -p -t "$TMUX_PANE" "@claude_prev_auto_rename" "$prev_auto"
}

# Echo this pane's frozen root title, or nothing when none was ever frozen.
# `show-options -v` exits non-zero on an option that was never set, so the
# guard doubles as the "is there a root?" check.
root_title() {
  tmux show-options -p -t "$TMUX_PANE" -v "@claude_root_title" 2>/dev/null || true
}

# Freeze `base` as this session's root, unless one is already frozen. Called
# only from --bump-counter, so the root is the title the window carried going
# INTO its first compaction -- the last one the user saw before the summarizing
# started, which is the one they recognize.
freeze_root_title() {
  local base=$1

  if [ -n "$(root_title)" ]; then
    return 0  # already frozen earlier in this session
  fi

  # A pane Claude never titled still carries the user's own window name, which
  # capture_prev_state has just recorded. Anchoring to that would prefix every
  # later title with something like "zsh/", so skip: no root, plain behavior.
  local prev_name
  prev_name=$(tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" 2>/dev/null || true)
  if [ "$base" = "$prev_name" ]; then
    return 0
  fi

  tmux set-option -p -t "$TMUX_PANE" -- "@claude_root_title" "$base"
}

# Drop the frozen root so the next session anchors to its own first title.
# Unsetting an option that was never set is not an error, so this is safe to
# call unconditionally.
clear_root_title() {
  tmux set-option -p -u -t "$TMUX_PANE" "@claude_root_title" 2>/dev/null || true
}

# Disable auto-rename for this window so the manual name persists, then set it.
# `--` ends option parsing so a title starting with `-` is not read as a flag.
apply_title() {
  tmux set-window-option -t "$TMUX_PANE" automatic-rename off
  tmux rename-window -t "$TMUX_PANE" -- "$1"
}

# Shared preamble + render for --bump-counter and --bump-subagent-counter:
# read the live title's counter body, capture pre-Claude state, resolve the
# base, increment the half named by `half` ("main" or "subagent"), and
# re-render. The two callers differ only in which half increments and
# whether the root freezes (main-only -- see freeze_root_title's header).
#
# capture_prev_state only writes the @claude_prev_window_name /
# @claude_prev_auto_rename pane options (first-set-wins, see its own
# header) -- it never calls apply_title and never touches the counter
# body, so reading main_count/subagent_count before or after it is
# provably equivalent. This helper reads both together, after.
bump_counter() {
  local half=$1
  local current body base main sub counter

  current=$(current_title)
  body=$(parse_counter "$current")
  capture_prev_state
  base=$(compact_focus_base "$current")

  main=$(main_count "$body")
  sub=$(subagent_count "$body")

  if [ "$half" = main ]; then
    # Freeze the root on the FIRST MAIN compaction only: `base`
    # is still the pre-compaction title, which is the anchor the
    # user already recognizes. Subagent bumps never reach here,
    # so a session whose subagents compacted first still anchors
    # to the title it carried into its OWN first compaction.
    if [ "$main" -eq 0 ]; then
      freeze_root_title "$base"
    fi
    main=$(( main + 1 ))
  else
    sub=$(( sub + 1 ))
  fi

  counter=$(compose_counter "$main" "$sub")
  apply_title "$(render_title "$base" "$counter" "$(root_title)")"
}

MODE="${1:-}"

case "$MODE" in
  -h|--help)
    print_help
    exit 0
    ;;
esac

# A missing arg is caller misuse in every mode (the subcommands are non-empty
# strings and a real title is non-empty too) -- flag it even outside tmux.
if [ -z "$MODE" ]; then
  echo "tmux-window-title: missing <title> (try --help)" >&2
  exit 1
fi

# Outside tmux there is no window to title -- succeed silently so the caller
# never has to check. Covers every mode below.
if [ -z "${TMUX:-}" ] || [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

case "$MODE" in
  --bump-counter)
    # A MAIN-session compaction: increment the left half
    # (absent -> starts at 1). Freezes the root on the FIRST
    # main compaction only -- see bump_counter's header and
    # freeze_root_title's for the full reasoning.
    bump_counter main
    ;;

  --bump-subagent-counter)
    # A subagent compacted its own context: increment the right
    # half, and freeze no root. A subagent's compaction erases
    # nothing this session remembers, so there is no anchor at
    # risk -- the root exists to survive an erasure that did not
    # happen here.
    bump_counter subagent
    ;;

  --reset-counter)
    # /clear or a fresh start: drop the counter and the root, so the next
    # session anchors to its own first title rather than inheriting this one's.
    # The root is cleared before the early return below, which fires when there
    # is no counter to reset -- a /clear after zero compactions must still
    # release the root.
    clear_root_title

    current=$(current_title)
    # With no counter present, leave the window name alone -- it's the user's
    # shell title, not one of ours.
    if [ -z "$(parse_counter "$current")" ]; then
      exit 0
    fi
    # Shed the now-released root too, keeping only the current work -- carrying
    # "<root>/" into a counter-less title would anchor the new session to the
    # old one's identity, which is what the reset just revoked.
    base=$(compact_focus_base "$current")
    capture_prev_state
    apply_title "$(render_title "$base" "")"
    ;;

  *)
    # Default mode: set the base title, preserving any counter already on the
    # window so a mid-session re-title (topic shift) keeps the count.
    #
    # Drop control chars (a raw newline corrupts the tmux status line), turn
    # any whitespace run into a single "-" (hyphens read cleaner than spaces
    # in a tab bar), collapse repeated hyphens, and trim leading/trailing.
    #
    # The root separator is folded into a hyphen too: the script owns the
    # "<root>/<current>" composition, so a caller passing an already-rooted
    # string would otherwise nest one root inside another.
    clean=$(printf '%s' "$MODE" | tr -d '\000-\037' | tr "$ROOT_SEPARATOR" '-' | sed -E 's/[[:space:]]+/-/g; s/-+/-/g; s/^-+//; s/-+$//')

    if [ -z "$clean" ]; then
      echo "tmux-window-title: <title> is empty after sanitizing" >&2
      exit 1
    fi

    existing=$(parse_counter "$(current_title)")
    capture_prev_state
    apply_title "$(render_title "$clean" "$existing" "$(root_title)")"
    ;;
esac
