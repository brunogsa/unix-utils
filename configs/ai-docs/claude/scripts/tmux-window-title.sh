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
#   tmux-window-title.sh --bump-counter  # +1 to the compaction counter
#   tmux-window-title.sh --reset-counter # drop the compaction counter
#   tmux-window-title.sh --help
#
# Compaction counter:
#   The title carries an optional trailing "[N]" -- the number of context
#   compactions this Claude session has survived, e.g. "auth-fix[3]". It gives
#   the user at-a-glance visibility into how churned a session's context is.
#   The count lives in the title itself (single source of truth), managed by
#   SessionStart hooks: --bump-counter on `compact`, --reset-counter on
#   `startup`/`clear`. Setting a base title PRESERVES an existing counter, so
#   Claude re-titling on a topic shift does not reset the count.
#
# Root anchor:
#   The title the user learned to recognize is the one the window carried
#   BEFORE its first compaction. Left alone, Claude's later re-titles replace
#   it outright and the window stops being identifiable mid-session.
#
#   So the first --bump-counter freezes the then-current base as the session's
#   ROOT, in the pane option @claude_root_title. Every later title renders as
#   "<root>/<current>[N]" -- the anchor the user scans for, plus where the work
#   has actually moved.
#
#   The current half AGGREGATES over the root rather than repeating it: any
#   hyphen-separated word the root already carries is dropped from it, so
#   "tmux-titles" plus "tmux-titles-cap" reads "tmux-titles/cap[1]". Repeating
#   a word already on screen would spend the cap truncating the work that is
#   actually new. A base the root fully covers leaves nothing to add and
#   renders bare, so an undrifted session never reads "auth-fix/auth-fix[2]".
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
#     "<root>/<current>[N]" form needs it. The counter suffix is always kept
#     intact and the text is truncated to fit, so the count stays readable
#     even as the title shrinks. The caller should still keep titles short.
#   - On the first rename for a pane (any mode), captures the pre-Claude window
#     name and automatic-rename flag into pane options ($TMUX_PANE-scoped
#     @claude_prev_window_name / @claude_prev_auto_rename) before overwriting
#     either -- first-set-wins, so later calls in the same session don't
#     clobber the captured original. A separate SessionEnd hook restores it.
#
# Examples:
#   tmux-window-title.sh "fix-auth-bug"   # spaces are converted to hyphens too
#   tmux-window-title.sh "tmux-titles"
#   tmux-window-title.sh --bump-counter   # "tmux-titles" -> "tmux-titles[1]"
#   tmux-window-title.sh --reset-counter  # "tmux-titles[1]" -> "tmux-titles"
#   tmux-window-title.sh "hook-tests"     # after that bump, roots the title:
#                                         #   "tmux-title/hook-tests[1]"
#   tmux-window-title.sh "tmux-titles-cap" # the root's own words drop out:
#                                          #   "tmux-titles/cap[1]"

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

# Separates the frozen root from the current work in a rooted title.
ROOT_SEPARATOR="/"

# Parse a trailing compaction counter "[N]" from a title. Echoes N when
# present, nothing otherwise. Strict -- only digits inside brackets at the very
# end count, so a base title never picks up a stray "[x]" as a counter.
parse_counter() {
  if [[ "$1" =~ \[([0-9]+)\]$ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  fi
}

# Echo the base title with a trailing numeric "[N]" removed (unchanged if none).
strip_counter() {
  if [[ "$1" =~ ^(.*)\[[0-9]+\]$ ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  else
    printf '%s' "$1"
  fi
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

# Split `available` chars between the root and the current base. Each side is
# entitled to half, but a side shorter than its half hands the slack to the
# other -- so a short root never wastes room a long current base could use.
# Echoes the two fitted segments separated by ROOT_SEPARATOR.
fit_rooted_pair() {
  local root=$1 base=$2 available=$3

  if [ $(( ${#root} + ${#base} )) -le "$available" ]; then
    printf '%s%s%s' "$root" "$ROOT_SEPARATOR" "$base"
    return
  fi

  local half=$(( available / 2 ))
  local root_room=$half base_room=$(( available - half ))

  if [ "${#root}" -lt "$half" ]; then
    root_room=${#root}
    base_room=$(( available - root_room ))
  elif [ "${#base}" -lt "$(( available - half ))" ]; then
    base_room=${#base}
    root_room=$(( available - base_room ))
  fi

  printf '%s%s%s' \
    "$(truncate_segment "$root" "$root_room")" \
    "$ROOT_SEPARATOR" \
    "$(truncate_segment "$base" "$base_room")"
}

# Echo `base` with every hyphen-separated word the root already carries
# dropped, in the order the survivors appeared. Echoes nothing when the root
# covers every word.
#
# This is what makes a rooted title aggregate instead of repeat: the root is
# already on screen, so re-printing one of its words buys the reader nothing
# while the cap truncates away the work that IS new.
drop_words_already_in_root() {
  local root=$1 remaining=$2 kept="" word

  while [ -n "$remaining" ]; do
    word="${remaining%%-*}"
    remaining="${remaining#"$word"}"
    remaining="${remaining#-}"

    # Both sides wrapped in hyphens so only whole words match -- an "auth"
    # in the root must not swallow "authz" from the current work.
    case "-$root-" in
      *"-$word-"*) continue ;;
    esac

    kept="${kept:+$kept-}$word"
  done

  printf '%s' "$kept"
}

# Render the window title, capped per MAX_LEN_PLAIN / MAX_LEN_COMPACTED. The
# counter is kept whole and the text truncated to make room, so the count stays
# visible even as the title shrinks.
#
# The root is prepended only when there is one AND the base still says
# something the root does not.
render_title() {
  local base=$1 count=$2 root=${3:-} suffix=""
  [ -n "$count" ] && suffix="[$count]"

  local max_len=$MAX_LEN_PLAIN
  [ -n "$count" ] && max_len=$MAX_LEN_COMPACTED

  local budget=$(( max_len - ${#suffix} ))

  if [ -n "$root" ]; then
    local new_work
    new_work=$(drop_words_already_in_root "$root" "$base")

    if [ -n "$new_work" ]; then
      local available=$(( budget - ${#ROOT_SEPARATOR} ))
      printf '%s%s' "$(fit_rooted_pair "$root" "$new_work" "$available")" "$suffix"
      return
    fi

    # Nothing survived: the root already spells the current work out, so it
    # renders alone rather than as "auth-fix/auth-fix" or "auth-fix/auth".
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
    # A compaction happened: increment the counter (absent -> starts at 1).
    current=$(current_title)
    count=$(parse_counter "$current")
    next=$(( ${count:-0} + 1 ))
    capture_prev_state

    # The window name is a RENDERED title, and rendering is not idempotent --
    # feeding "<root>/<current>" back in would compose a second root onto it
    # and squeeze both halves again. Recover the current-work half first; on a
    # pre-root title there is no separator and this is a no-op.
    base=$(strip_counter "$current")
    base="${base##*"$ROOT_SEPARATOR"}"

    # Freeze the root on the FIRST compaction only: `base` is still the
    # pre-compaction title, which is the anchor the user already recognizes.
    if [ -z "$count" ]; then
      freeze_root_title "$base"
    fi

    apply_title "$(render_title "$base" "$next" "$(root_title)")"
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
    base=$(strip_counter "$current")
    base="${base##*"$ROOT_SEPARATOR"}"
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
