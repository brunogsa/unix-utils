#!/bin/bash
# tmux-window-title - Set the current tmux window's title to a
# given string.
#
# Claude Code calls this to label the window with a brief title
# of the current work, so the user can find the right window at
# a glance.
#
# It overwrites the title outright -- no prefixes, no stacking
# (that policy lives with the caller, not here) -- except that
# before the first main compaction only ONE title is allowed
# (see First-title gate below).
#
# Usage:
#   tmux-window-title.sh <title>       # set the base title
#   tmux-window-title.sh --help
#
#   Counter bumps, one per kind of compaction:
#     --bump-subagent-counter   # +1 subagent compaction
#     --bump-counter            # +1 main-session compaction
#     --reset-counter           # reset title state
#
#   Window ownership (see Ownership below):
#     --claim-owner             # claim if free; 0 = we own it
#     --is-owner                # 0 = this pane owns the window
#     --release-owner           # SessionEnd: free it on exit
#
# Compaction counter:
#   The title carries an optional trailing counter -- how many
#   context compactions this Claude session has survived.
#
#   It gives the user at-a-glance visibility into how churned a
#   session's context is.
#
#   It has two halves, because the two kinds of compaction do
#   not mean the same thing. "auth-fix[3]" is three MAIN-session
#   compactions, the ones that erase this window's own
#   conversation.
#
#   "auth-fix[3+9]" adds nine subagent compactions -- churn the
#   session delegated away rather than absorbed, which says its
#   subagents are running hot while its own context is not.
#
#   A zero subagent half renders as nothing at all: a session
#   whose subagents never compacted reads "[3]", never "[3+0]".
#   The "+" costs two of the 16-char tail room (see Root anchor
#   below), so it appears only once it carries information.
#
#   The reference for the count is the pane option
#   @claude_last_title, the name this script itself wrote last.
#
#   The live window name is read only when that option is unset
#   (a window opened before rollout) or differs from it, which
#   means the user renamed the window by hand.
#
#   A hand rename is taken whole as the new label, and becomes
#   the root (folded and capped like any root) at the next main
#   compaction.
#
#   The counter is managed by SessionStart hooks: a bump on
#   `compact`, --reset-counter on every other source.
#
#   --reset-counter takes the same path for every SessionStart
#   source, /clear included, and reads nothing from stdin.
#
#   It drops the root and the first-title flag, so the next
#   session titles itself afresh.
#
#   A live counter is shed with the root, keeping the compact
#   focus.
#
#   Nothing restores the pre-Claude window name on /clear or on
#   exit: the title stays until the user renames the window.
#
#   A first "/" segment starting with "." is the user's own
#   root and is kept instead: a tmux-resurrect window has no
#   pane options, so its name is that root's only record.
#
#   Setting a base title PRESERVES an existing counter.
#
#   Leading dots in a title Claude passes are stripped: a dotted
#   label is always the user's own deliberate name, so Claude
#   never writes one.
#
#   When a main compaction freezes no root (the window still
#   shows its pre-Claude name), --bump-counter prints a note on
#   stdout telling Claude to pass the session goal first; that
#   title then becomes the root.
#
# First-title gate:
#   Before the first main compaction a session gets ONE title.
#   The pane option @claude_first_title_used records that it was
#   spent.
#
#   A second title is refused: the window stays as it is, the
#   script exits 0, and a note on stderr says the refusal is
#   expected and not to retry. Exit 0 keeps the caller from
#   reading it as a failure.
#
#   A live window name starting with "." is the user's
#   protection marker: a title before the first main compaction
#   is refused the same way (exit 0, stderr note).
#
#   The flag stays unspent, so the first title still sets once
#   the user drops the dot.
#
#   A window titled before this gate existed carries no flag;
#   a dated shim in the code seeds it as spent when the live
#   name differs from the captured pre-Claude name.
#
# Root anchor:
#   The title the user learned to recognize is the one the
#   window carried BEFORE its first compaction.
#
#   Left alone, Claude's later re-titles replace it outright and
#   the window stops being identifiable mid-session.
#
#   So the first --bump-counter freezes the then-current base
#   as the session's ROOT, in the pane option
#   @claude_root_title.
#
#   Every later title renders as "<root>/<compact-focus>[N]"
#   -- the anchor the user scans for, plus where the work has
#   actually moved.
#
#   The compact-focus half always renders the label as-is, even
#   when it repeats a word the root already carries -- there is
#   no dedup/aggregation.
#
#   A rooted title renders bare (root only, no "/") only when
#   the label is IDENTICAL to the root, or when nothing has been
#   set post-root yet.
#
#   Root and tail each get their OWN fixed 16-char room, 32
#   total: MAX_LEN_PLAIN for the root (deliberately equal to the
#   pre-compaction cap) and TAIL_ROOM for the tail segment.
#
#   The tail room is shared by the leading "/", the label, and
#   the "[N]" counter. The counter is always rendered whole --
#   only the label gives up width as the counter widens (see
#   render_title).
#
#   A counter wider than 16 chars steals from the ROOT side too,
#   one char for one char past that point (head_room = 16 -
#   max(0, W-16), where W is the counter's own width including
#   its brackets).
#
#   Clamped at 0, so a counter wider than 32 chars leaves the
#   root empty and renders alone.
#
#   The tail's own room never grows to reclaim a short root's
#   unused space: it stays fixed at max(0, TAIL_ROOM - W)
#   regardless of how little of the root's 16 chars a short root
#   actually uses.
#
#   If the tail's label room ever drops below 2 chars (not even
#   room for the "/" plus one label char), the field is dropped
#   entirely rather than rendering a dangling "/[N]".
#
#   The root is stored in tmux, not left to Claude's memory,
#   precisely because compaction is what erases the first turn:
#   after it, Claude no longer knows what the original title was
#   and cannot preserve it by judgment alone.
#
#   It is immutable for the life of the session -- only
#   --reset-counter (every non-`compact` source) drops it,
#   letting the next session set its own.
#
#   A pane that Claude never titled grows no root, so the window
#   keeps the plain behavior instead of anchoring to the user's
#   shell name.
#
# Ownership:
#   The window name belongs to the WINDOW, but all this
#   script's state (counter, root, last title) belongs to a
#   PANE.
#
#   Two Claudes in two panes of one window would both rename
#   it, and the second one's start would shed the first one's
#   root and counter.
#
#   So the window option @claude_title_owner holds the pane id
#   of the one Claude allowed to title the window: the first
#   to start. `tmux set-option -o` makes the claim atomic.
#
#   A pane that does not own the window is refused.
#
#   Refusal: a title exits 0 with a stderr note, and
#   --reset-counter and both bumps exit 0 with no output and
#   no tmux write.
#
#   A window nobody owns refuses the same way.
#
#   Only a SessionStart claim creates an owner, so a Claude
#   started before ownership existed gets no title until its
#   next start.
#
#   The claim happens only at session start: --reset-counter
#   and --claim-owner (the SessionStart reminder hook) claim a
#   free window. Every other mode only checks.
#
#   A mid-session takeover would read the previous owner's
#   live "[M+S]" counter as its own, because a pane that never
#   ran its reset has no @claude_last_title.
#
#   An owner is stale, and replaced at a claim, when its pane
#   no longer exists or moved to another window.
#
#   An owner equal to the claiming pane counts as ours, so a
#   Claude that crashed and relaunched in the same pane keeps
#   its window.
#
#   --release-owner reads {"reason": ...} from the SessionEnd
#   JSON on stdin. It frees the window only when the process
#   exits (`other`, `logout`, `prompt_input_exit`) and this
#   pane is the owner.
#
#   `clear` and `resume` keep it, because the same process
#   continues, and an empty or unknown reason keeps it too.
#   It always exits 0.
#
#   Known gap: a Claude killed with no SessionEnd, whose pane
#   lives on, keeps ownership until that pane closes or runs
#   Claude again.
#
#   Recover by hand with
#   `tmux set-option -w -u @claude_title_owner`.
#
# Behavior:
# - Outside tmux ($TMUX unset): no-op, exit 0.
#   Lets the caller invoke it
#     unconditionally without guarding on the terminal.
#
# - Empty/missing title (default mode): error to stderr, exit 1.
#
# - Sets `automatic-rename off` first, because with it on
#   (the user's default) tmux re-derives the name from the
#   running command and the title would not stick.
#
# - Renames the window that Claude runs in ($TMUX_PANE), not
#   whatever window
#     is currently focused.
#
# - On the first title or bump for a pane, captures the
#   pre-Claude window name into the pane option
#   @claude_prev_window_name.
#
#   First-set-wins, so later calls in the same session don't
#   clobber the captured original.
#
#   It only tells a pane Claude never titled from one it did,
#   when a root is frozen. --reset-counter unsets it.
#
#   The whole title is capped, counter included: 16 chars
#   before any compaction, 32 once a counter exists (16 root +
#   16 tail, see Root anchor above).
#
#   The counter suffix stays intact and the label is truncated
#   to fit, so the count stays readable as the title shrinks.
#
# Examples:
#   tmux-window-title.sh "fix-auth-bug"
#     spaces are converted to hyphens too
#   tmux-window-title.sh "tmux-titles"
#
#   tmux-window-title.sh --bump-counter
#     "tmux-titles" -> "tmux-titles[1]", freezing the root
#
#   tmux-window-title.sh "hook-tests-cleanup"
#     the label is truncated to fit the tail's 16-char room
#     (incl. "/" and the counter): "tmux-titles/hook-tests-c[1]"
#
#   tmux-window-title.sh --bump-subagent-counter
#     a wider counter eats further into the label's room:
#     "tmux-titles/hook-tests[1+1]"
#
#   tmux-window-title.sh --reset-counter
#     drops the counter and the root, keeping the rendered
#     label: "hook-tests"
#
#   tmux-window-title.sh --reset-counter
#     on ".cityCode/is-cleanup[7+2]" keeps the user's dotted
#     root: ".cityCode"

set -euo pipefail

# Print the comment header (lines 2..first non-comment line) as
# help text, stripping the leading "# ".
# Stops at the first non-# line so it never leaks code below the
# header, regardless of where the header ends.
print_help() {
  awk 'NR==1 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
}

# Two fixed 16-char segments, 32 total.
# A pre-compaction title is a bare base and stays at the tight
# 16 the caller is told to aim for.
#
# Once a counter exists, the head segment (root, or base when
# unrooted) keeps its own 16, and the tail segment ("/" + label
# + "[M+S]") gets a second 16.
MAX_LEN_PLAIN=16

# Separates the frozen root from the compact-focus label in a
# rooted title.
ROOT_SEPARATOR="/"

# Fixed room the tail segment gets inside a rooted (or
# unrooted-with-counter) title: the leading ROOT_SEPARATOR, the
# label, and the "[M+S]" counter all share this one 16-char
# room.
#
# The counter is always rendered whole, so only the label gives
# up width as the counter widens.
TAIL_ROOM=16

# Parse a trailing compaction counter from a title. Echoes the
# counter BODY without its brackets -- "3" or "3+2" -- and
# nothing when there is none.
#
# Strict: only digits (with at most one "+" between them) inside
# brackets at the very end count, so a base title never picks up
# a stray "[x]" as a counter.
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
# as "+0": the "+" costs two of the tail segment's fixed 16-char
# room (see render_title), so it earns those two characters only
# once a subagent has actually compacted.
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
# idempotent -- feeding "<root>/<compact-focus>" back in would
# compose a second root onto it and squeeze both halves again.
# On a pre-root title there is no separator and this is a no-op.
compact_focus_base() {
  local base
  base=$(strip_counter "$1")
  printf '%s' "${base##*"$ROOT_SEPARATOR"}"
}

# Cut a title segment down to `max` chars, dropping a
# trailing hyphen the cut may leave so the result never reads as
# a dangling word break.
truncate_segment() {
  local text=$1 max=$2
  if [ "${#text}" -gt "$max" ]; then
    text="${text:0:max}"
    text="${text%-}"
  fi
  printf '%s' "$text"
}

# Render the window title, capped per MAX_LEN_PLAIN
# (pre-counter) or the 16+16 head/tail split (once a counter
# exists).
#
# The counter is kept whole and the text truncated to make room,
# so the count stays visible even as the title shrinks.
#
# The root is prepended only when there is one AND the base
# still differs from it -- an identical base renders bare rather
# than doubled.
render_title() {
  local base=$1 counter=$2 root=${3:-} suffix=""
  [ -n "$counter" ] && suffix="[$counter]"

  if [ -z "$suffix" ]; then
    # Pre-compaction: a bare base, no head/tail split to apply.
    printf '%s' "$(truncate_segment "$base" "$MAX_LEN_PLAIN")"
    return
  fi

  local suffix_len=${#suffix}

  # The head segment (root, or base when unrooted) keeps its own
  # MAX_LEN_PLAIN room, and gives up width only once the counter
  # itself grows past that same MAX_LEN_PLAIN -- one char stolen
  # per char the counter widens past it.
  #
  # An absurdly wide counter can outgrow this room entirely.
  #
  # A negative room fed into truncate_segment's "${text:0:max}"
  # is a bash version trap: bash < 4.2 errors, bash >= 4.2 reads
  # a negative length as "N chars off the end" and returns MORE
  # text, not less -- clamp it away.
  local head_steal=0
  [ "$suffix_len" -gt "$MAX_LEN_PLAIN" ] && head_steal=$(( suffix_len - MAX_LEN_PLAIN ))
  local head_room=$(( MAX_LEN_PLAIN - head_steal ))
  [ "$head_room" -lt 0 ] && head_room=0

  if [ -n "$root" ]; then
    local focus_label=$base
    [ "$focus_label" = "$root" ] && focus_label=""

    if [ -n "$focus_label" ]; then
      # The tail's own room never grows to reclaim a short
      # root's unused space: it stays fixed at TAIL_ROOM minus
      # the counter's width, regardless of head_room.
      local label_room=$(( TAIL_ROOM - suffix_len ))
      [ "$label_room" -lt 0 ] && label_room=0

      # Below a 2-char room there's not even space for the "/"
      # plus one label char -- drop the field entirely rather
      # than render a dangling "/[N]".
      local focus_out=""
      [ "$label_room" -ge 2 ] && focus_out=$(truncate_segment "${ROOT_SEPARATOR}${focus_label}" "$label_room")

      printf '%s%s%s' "$(truncate_segment "$root" "$head_room")" "$focus_out" "$suffix"
      return
    fi

    # Nothing to add: the label is identical to the root, so it
    # renders alone rather than as "auth-fix/auth-fix".
    base=$root
  fi

  printf '%s%s' "$(truncate_segment "$base" "$head_room")" "$suffix"
}

# Read the name of the window Claude runs in ($TMUX_PANE), not
# whatever window is currently focused.
current_title() {
  tmux display-message -t "$TMUX_PANE" -p '#{window_name}'
}

# First-set-wins capture of the window's pre-Claude name, into
# a pane option (not a window option) so the "original" ties to
# this specific Claude pane/session -- relevant if the window
# ever holds more than one pane.
#
# freeze_root_title reads it back, to tell a pane Claude never
# titled from one it did.
#
# `show-options -v` on an option that was never set exits
# non-zero with nothing on stdout, and exits 0 with the
# value once it has been -- that's the "already captured?"
# check below.
capture_prev_state() {
  if tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" >/dev/null 2>&1; then
    return 0  # already captured earlier in this session
  fi

  tmux set-option -p -t "$TMUX_PANE" -- "@claude_prev_window_name" "$(current_title)"
}

# Echo this pane's frozen root title, or nothing when none was
# ever frozen.
#
# `show-options -v` exits non-zero on an option that was
# never set, so the guard doubles as the "is there a root?"
# check.
root_title() {
  tmux show-options -p -t "$TMUX_PANE" -v "@claude_root_title" 2>/dev/null || true
}

# Echo the last name this script wrote to the window, or nothing
# when it never wrote one (a window opened before this option
# existed).
#
# The window name is the user's to rename; this option is the
# script's own record, so a live name that differs from it is a
# hand rename.
last_title() {
  tmux show-options -p -t "$TMUX_PANE" -v "@claude_last_title" 2>/dev/null || true
}

# Echo "yes" when this session already spent its one title
# before the first main compaction, else "no".
#
# The pane option is the record: `show-options -v` exits
# non-zero on an option that was never set.
first_title_spent() {
  if tmux show-options -p -t "$TMUX_PANE" -v "@claude_first_title_used" >/dev/null 2>&1; then
    printf 'yes'
  else
    printf 'no'
  fi
}

# Echo a hand-set window name as a root: "/" folded to "-" so it
# cannot split into root and label, then cut to MAX_LEN_PLAIN
# (a leading dot counts).
#
# The counter is not stripped: the count lives in last_title, so
# a bracket in a hand-set name is plain text.
adopt_root_name() {
  local name=$1
  truncate_segment "${name//"$ROOT_SEPARATOR"/-}" "$MAX_LEN_PLAIN"
}

# Echo "yes" when the main-compaction half of a counter body is
# zero or absent, else "no".
#
# A string test, never a numeric one: bash 3.2 overflows on the
# 20-30 digit counts the cap tests inject.
has_no_main_compaction() {
  local main
  main=$(main_count "$1")
  if [[ $main =~ ^0+$ ]]; then
    printf 'yes'
  else
    printf 'no'
  fi
}

# Freeze `base` as this session's root, unless one is
# already frozen.
#
# Called only from --bump-counter, so the root is the title the
# window carried going INTO its first compaction -- the last one
# the user saw before the summarizing started, which is the one
# they recognize.
freeze_root_title() {
  local base=$1

  if [ -n "$(root_title)" ]; then
    return 0  # already frozen earlier in this session
  fi

  # A pane Claude never titled still carries the user's own
  # window name, which capture_prev_state has just recorded.
  # Anchoring to that would prefix every later title with
  # something like "zsh/", so skip: no root, plain behavior.
  #
  # A dotted label is exempt: Claude never writes a leading dot,
  # so it is always the user's deliberate name, and it freezes
  # even when it equals the pre-Claude name.
  local prev_name
  prev_name=$(tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" 2>/dev/null || true)
  if [ "$base" = "$prev_name" ] && [[ $base != .* ]]; then
    return 0
  fi

  tmux set-option -p -t "$TMUX_PANE" -- "@claude_root_title" "$base"
}

# Drop the frozen root so the next session anchors to its own
# first title.
# Unsetting an option that was never set is not an error, so
# this is safe to call unconditionally.
clear_root_title() {
  tmux set-option -p -u -t "$TMUX_PANE" "@claude_root_title" 2>/dev/null || true
}

# Window option naming the pane whose Claude owns this window's
# title (see Ownership in the header).
OWNER_OPTION="@claude_title_owner"

# Echo the pane id recorded as this window's title owner, or
# nothing when none is.
title_owner() {
  tmux show-options -w -t "$TMUX_PANE" -v "$OWNER_OPTION" 2>/dev/null || true
}

# Succeed when `owner` (a pane id) no longer holds a Claude in
# this window: the pane is gone, or break-pane moved it to
# another window.
#
# tmux exits 0 with empty output for a pane id that does not
# exist, so an empty window id is the dead-pane signal.
owner_is_stale() {
  local owner=$1 own_window owner_window
  own_window=$(tmux display-message -t "$TMUX_PANE" -p '#{window_id}')
  owner_window=$(tmux display-message -t "$owner" -p '#{window_id}' 2>/dev/null || true)
  [ -z "$owner_window" ] || [ "$owner_window" != "$own_window" ]
}

# Succeed when this pane owns the window's title.
is_title_owner() {
  [ "$(title_owner)" = "$TMUX_PANE" ]
}

# Make this pane the window's title owner when the window is
# free or its owner is stale, and succeed when this pane owns
# the window afterwards.
#
# `set-option -o` fails when the option is already set, so the
# claim is atomic inside the tmux server: of two panes racing
# for a free window, exactly one wins.
#
# An owner equal to this pane counts as ours, so a Claude that
# crashed and relaunched in the same pane keeps its window.
claim_title_ownership() {
  local owner
  owner=$(title_owner)
  if [ -n "$owner" ] && [ "$owner" != "$TMUX_PANE" ] && owner_is_stale "$owner"; then
    tmux set-option -w -u -t "$TMUX_PANE" "$OWNER_OPTION" 2>/dev/null || true
  fi

  if tmux set-option -w -o -t "$TMUX_PANE" "$OWNER_OPTION" "$TMUX_PANE" 2>/dev/null; then
    return 0
  fi
  is_title_owner
}

# Disable auto-rename for this window so the manual name
# persists, then set it.
# `--` ends option parsing so a title starting with
# `-` is not read as a flag.
apply_title() {
  tmux set-window-option -t "$TMUX_PANE" automatic-rename off

  # tmux reads an argument ending in `;` as a command separator,
  # which would drop it from the title; a backslash makes it a
  # literal semicolon again.
  local title="$1"
  [[ "$title" == *\; ]] && title="${title%;}\\;"

  # One command list, so a rename never lands without the record
  # of what the script wrote.
  tmux rename-window -t "$TMUX_PANE" -- "$title" \; \
    set-option -p -t "$TMUX_PANE" -- "@claude_last_title" "$title"
}

# Shared preamble + render for --bump-counter and
# --bump-subagent-counter: read the live title's counter body,
# capture pre-Claude state, resolve the base, increment the half
# named by `half` ("main" or "subagent"), and re-render.
#
# The two callers differ only in which half increments and
# whether the root freezes (main-only -- see freeze_root_title's
# header).
#
# capture_prev_state only writes the @claude_prev_window_name
# pane option (first-set-wins, see its own header).
#
# It never calls apply_title and never touches the counter body,
# so reading main_count/subagent_count before or after it is
# provably equivalent.
#
# This helper reads both together, after.
bump_counter() {
  local half=$1
  local current last body base main sub counter
  local is_hand_rename=no

  current=$(current_title)
  last=$(last_title)
  capture_prev_state

  # Counter and label come from the name the script itself wrote
  # last.
  #
  # With none recorded (a window opened before rollout) they
  # come from the live name, as they always did.
  if [ -z "$last" ]; then
    body=$(parse_counter "$current")
    base=$(compact_focus_base "$current")
  else
    body=$(parse_counter "$last")
    if [ "$current" = "$last" ]; then
      base=$(compact_focus_base "$last")
    else
      # The user renamed the window since: take the whole new
      # name as the label, with no split at its own "/".
      is_hand_rename=yes
      base=$(adopt_root_name "$current")
    fi
  fi

  main=$(main_count "$body")
  sub=$(subagent_count "$body")

  if [ "$(has_no_main_compaction "$body")" = yes ]; then
    # Freeze the root on the FIRST MAIN compaction only: `base`
    # is still the pre-compaction title, which is the anchor the
    # user already recognizes.
    #
    # Subagent bumps never reach here, so a session whose
    # subagents compacted first still anchors to the title it
    # carried into its OWN first compaction.
    if [ "$half" = main ]; then
      freeze_root_title "$base"

      # No root froze, so the next title Claude passes becomes
      # the root (title mode). Claude Code adds a SessionStart
      # `compact` hook's plain stdout to Claude's context, so
      # this note reaches it right when it must pick that title.
      if [ -z "$(root_title)" ]; then
        echo "tmux-window-title: this window has no root title yet. Pass the session goal as your next title, not the current sub-goal: that title becomes the window's root."
      fi
    fi
  elif [ "$is_hand_rename" = yes ]; then
    # After a main compaction the hand-set name replaces the
    # root, so the label equals it and renders bare.
    tmux set-option -p -t "$TMUX_PANE" -- "@claude_root_title" "$base"
  fi

  if [ "$half" = main ]; then
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

# A missing arg is caller misuse in every mode (the subcommands
# are non-empty strings and a real title is non-empty too) --
# flag it even outside tmux.
if [ -z "$MODE" ]; then
  echo "tmux-window-title: missing <title> (try --help)" >&2
  exit 1
fi

# Outside tmux there is no window to title -- succeed silently
# so the caller never has to check.
# Covers every mode below.
if [ -z "${TMUX:-}" ] || [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

case "$MODE" in
  --claim-owner)
    # Silent: the exit code is the answer, for the SessionStart
    # reminder hook.
    if claim_title_ownership; then
      exit 0
    fi
    exit 1
    ;;

  --is-owner)
    if is_title_owner; then
      exit 0
    fi
    exit 1
    ;;

  --release-owner)
    # SessionEnd passes {"reason": ...} on stdin. Only a reason
    # that ends the process frees the window; an empty or
    # unknown one keeps it, because freeing a window whose
    # Claude lives on would let a second Claude take it.
    reason=$(jq -r '.reason // empty' 2>/dev/null || true)
    case "$reason" in
      other|logout|prompt_input_exit)
        if is_title_owner; then
          tmux set-option -w -u -t "$TMUX_PANE" "$OWNER_OPTION" 2>/dev/null || true
        fi
        ;;
    esac
    exit 0
    ;;

  --bump-counter)
    # A MAIN-session compaction: increment the left half
    # (absent -> starts at 1). Freezes the root on the FIRST
    # main compaction only -- see bump_counter's header and
    # freeze_root_title's for the full reasoning.
    #
    # A pane that does not own the window never ran its reset,
    # so it would read the owner's live counter as its own.
    if ! is_title_owner; then
      exit 0
    fi
    bump_counter main
    ;;

  --bump-subagent-counter)
    # A subagent compacted its own context: increment the right
    # half, and freeze no root.
    #
    # A subagent's compaction erases nothing this session
    # remembers, so there is no anchor at risk -- the root
    # exists to survive an erasure that did not happen here.
    #
    # Same ownership gate as --bump-counter.
    if ! is_title_owner; then
      exit 0
    fi
    bump_counter subagent
    ;;

  --reset-counter)
    # Only the Claude that owns the window may reset it: the
    # root and counter on the window are that Claude's, and a
    # second Claude's start must not shed them. A fresh start
    # claims a free or stale window here.
    if ! claim_title_ownership; then
      exit 0
    fi

    # /clear or a fresh start: drop the counter and the root, so
    # the next session anchors to its own first title rather
    # than inheriting this one's.
    #
    # The root is cleared before the early return below, which
    # fires when there is no counter to reset -- a /clear after
    # zero compactions must still release the root.
    clear_root_title

    # A spent first-title flag would block the next session's
    # first title, so every source releases it.
    tmux set-option -p -u -t "$TMUX_PANE" "@claude_first_title_used" 2>/dev/null || true

    # Forget the pre-Claude name a bump or title captured: this
    # session is over, and the next one captures its own.
    #
    # The automatic-rename flag an older script captured is
    # unset too, since nothing reads it any more.
    tmux set-option -p -u -t "$TMUX_PANE" "@claude_prev_window_name" 2>/dev/null || true
    tmux set-option -p -u -t "$TMUX_PANE" "@claude_prev_auto_rename" 2>/dev/null || true

    current=$(current_title)

    # With no counter present, leave the window name alone --
    # it's the user's shell title, not one of ours.
    #
    # The last title still gets set, so a later hand rename
    # reads as one.
    if [ -z "$(parse_counter "$current")" ]; then
      tmux set-option -p -t "$TMUX_PANE" -- "@claude_last_title" "$current"
      exit 0
    fi

    # Shed the now-released root too, keeping only the current
    # work -- carrying "<root>/" into a counter-less title would
    # anchor the new session to the old one's identity, which is
    # what the reset just revoked.
    base=$(compact_focus_base "$current")

    # A dotted first segment is the user's own name -- Claude
    # never writes a leading dot -- so keep it as the base
    # instead of the compact focus.
    #
    # A window tmux-resurrect restores carries no pane options,
    # so the live name is the only record of that root; shedding
    # it would let the next Claude title overwrite it.
    uncounted=$(strip_counter "$current")
    first_segment=${uncounted%%"$ROOT_SEPARATOR"*}
    if [[ "$first_segment" == .* ]]; then
      base=$first_segment
    fi

    apply_title "$(render_title "$base" "")"
    ;;

  *)
    # Default mode: set the base title, preserving any counter
    # already on the window so a mid-session re-title (topic
    # shift) keeps the count.
    #
    # Drop control chars (a raw newline corrupts the tmux status
    # line), turn any whitespace run into a single "-" (hyphens
    # read cleaner than spaces in a tab bar), collapse repeated
    # hyphens, and trim leading/trailing.
    #
    # The root separator is folded into a hyphen too: the script
    # owns the "<root>/<current>" composition, so a caller
    # passing an already-rooted string would otherwise nest one
    # root inside another.
    #
    # Leading dots are stripped after that cleanup, then hyphens
    # they uncovered: a leading "." protects a window from this
    # script, and only the user may set one.
    clean=$(printf '%s' "$MODE" | tr -d '\000-\037' | tr "$ROOT_SEPARATOR" '-' | sed -E 's/[[:space:]]+/-/g; s/-+/-/g; s/^[-.]+//; s/-+$//')

    if [ -z "$clean" ]; then
      echo "tmux-window-title: <title> is empty after sanitizing" >&2
      exit 1
    fi

    if ! is_title_owner; then
      echo "tmux-window-title: title refused (expected, not an error): another Claude in this tmux window owns its title. Do not retry." >&2
      exit 0
    fi

    current=$(current_title)
    last=$(last_title)
    if [ -z "$last" ]; then
      existing=$(parse_counter "$current")
    else
      existing=$(parse_counter "$last")

      # A live name that differs from the last one written is
      # a hand rename; after a main compaction it becomes the
      # root.
      if [ "$current" != "$last" ] && [ "$(has_no_main_compaction "$existing")" = no ]; then
        tmux set-option -p -t "$TMUX_PANE" -- "@claude_root_title" "$(adopt_root_name "$current")"
      fi
    fi

    # A window past its first main compaction with no root yet
    # (the bump found only the pre-Claude name) roots this
    # title.
    if [ -z "$(root_title)" ] && [ "$(has_no_main_compaction "$existing")" = no ]; then
      tmux set-option -p -t "$TMUX_PANE" -- "@claude_root_title" "$clean"
    fi

    # Before the first main compaction a session gets ONE title.
    # A second one is refused with exit 0: the caller must not
    # read it as a failure, so the note says to stop retrying.
    if [ "$(has_no_main_compaction "$existing")" = yes ]; then
      if [ "$(first_title_spent)" = yes ]; then
        echo "tmux-window-title: title refused (expected, not an error): this session already set its first title and may not re-title before its first compaction. Do not retry." >&2
        exit 0
      fi

      # A dotted window is the user's protection from this
      # script. The refusal leaves the first-title flag
      # unspent, so the first title still sets once the user
      # drops the dot.
      if [ "${current#.}" != "$current" ]; then
        echo "tmux-window-title: title refused (expected, not an error): the window name starts with a dot, which protects it from re-titling. Do not retry." >&2
        exit 0
      fi
    fi

    capture_prev_state
    apply_title "$(render_title "$clean" "$existing" "$(root_title)")"
    if [ "$(has_no_main_compaction "$existing")" = yes ]; then
      tmux set-option -p -t "$TMUX_PANE" -- "@claude_first_title_used" 1
    fi
    ;;
esac
