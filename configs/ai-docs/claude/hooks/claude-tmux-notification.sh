#!/bin/bash
# claude-tmux-notification - Flag the Claude Code tmux window as needing attention
#
# Usage (Claude Code Notification/Stop hooks):
#   claude-tmux-notification.sh <state>
#   state: notification | done
#
# Rationale:
#   Lets you run Claude Code in one tmux window while working in another,
#   and still notice when Claude is blocked on permission ("notification")
#   or has finished its turn ("done"). Sets the per-window user option
#   @claude_state, which tmux.conf reads in window-status-format to render
#   a colored icon prefix. tmux's session-window-changed hook clears the
#   flag once you focus the window. Skipped when you are already viewing
#   the window (attached session + window active) -- no point flagging a
#   window you can already see.
#
#   Also tints the pane background (orange for "notification", green for
#   "done") via the per-pane option @claude_pane_state, for when Claude
#   shares a window with a sibling pane you're actively working in -- the
#   tab icon alone can't be seen from another pane in the same window. This
#   gate is independent and stricter: it only skips when you're looking at
#   this exact pane (active pane, in an active window, in an attached
#   session), so a non-active split still gets tinted even while its window
#   is the one on screen. A pane-focus-in hook in the tmux config clears the
#   tint once you focus the pane.
#
#   For state=notification, reads the event JSON from stdin and skips
#   idle alerts (notification_type=idle_prompt), which Claude Code fires
#   ~60s after every turn and are not actionable. Permission prompts
#   (notification_type=permission_prompt) and any future notification
#   type pass through -- denylist bias avoids silently dropping new
#   actionable events.
#
# Debug:
#   Set CLAUDE_TMUX_HOOK_DEBUG=1 in the hook's environment to append each
#   event's raw JSON payload to /tmp/claude-tmux-hook.log -- useful for
#   tuning the idle-message filter.
#
# Examples:
#   bash claude-tmux-notification.sh notification  # Claude needs input
#   bash claude-tmux-notification.sh done          # Claude finished its turn

set -e

STATE="${1:-}"

case "$STATE" in
  notification|done) ;;
  *)
    echo "claude-tmux-notification: invalid state '$STATE' (expected: notification|done)" >&2
    exit 1
    ;;
esac

# Sound cues -- tweak to taste. A discrete "go look" tone, distinct per state:
# a calm one when a turn finishes, a more urgent one when Claude is blocked on
# a permission prompt. Played only after the "skip if viewing/not-tmux/idle"
# gates below, so they stay silent while you're already watching the window.
#   macOS: built-in .aiff under /System/Library/Sounds (afplay, no install).
#   Linux: freedesktop .oga theme (canberra-gtk-play/paplay + sound-theme-freedesktop).
DONE_SOUND_MACOS="Purr"
NOTIFICATION_SOUND_MACOS="Tink"
DONE_SOUND_LINUX="complete"
NOTIFICATION_SOUND_LINUX="message"

# Pane tint colors -- muted so the theme's light text stays readable over a
# full-pane background (the bright tab-bar hues would wash it out). Set via
# `set-option -p window-style`, never `select-pane -P`: the latter activates
# the target pane and steals focus, which was spiked and confirmed to yank
# the cursor into the Claude pane and self-clear the tint it had just set.
TINT_COLOR_NOTIFICATION="#653f1c"
TINT_COLOR_DONE="#345c3a"

# Play the cue for $1 (done|notification): best-effort and non-blocking.
# Never fails the hook -- no player found means it's skipped, and the player
# runs detached (&) so the short sound outlives this script's exit.
play_attention_sound() {
  local state="$1"
  local name

  if command -v afplay >/dev/null 2>&1; then
    case "$state" in
      done)         name="$DONE_SOUND_MACOS" ;;
      notification) name="$NOTIFICATION_SOUND_MACOS" ;;
    esac
    afplay "/System/Library/Sounds/${name}.aiff" >/dev/null 2>&1 &
    return 0
  fi

  case "$state" in
    done)         name="$DONE_SOUND_LINUX" ;;
    notification) name="$NOTIFICATION_SOUND_LINUX" ;;
  esac

  if command -v canberra-gtk-play >/dev/null 2>&1; then
    canberra-gtk-play -i "$name" >/dev/null 2>&1 &
  elif command -v paplay >/dev/null 2>&1; then
    paplay "/usr/share/sounds/freedesktop/stereo/${name}.oga" >/dev/null 2>&1 &
  fi

  return 0
}

# Buffer stdin once (may be empty for manual invocations)
PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD=$(cat)
fi

# Optional debug: append the raw event payload to a log file
if [ -n "${CLAUDE_TMUX_HOOK_DEBUG:-}" ] && [ -n "$PAYLOAD" ]; then
  printf '[%s] state=%s payload=%s\n' "$(date -Is)" "$STATE" "$PAYLOAD" >> /tmp/claude-tmux-hook.log
fi

# Skip idle Notification events -- they fire ~60s after every turn and
# are not actionable. Everything else (permission prompts, unknown types)
# passes through.
if [ "$STATE" = "notification" ] && [ -n "$PAYLOAD" ]; then
  NTYPE=$(echo "$PAYLOAD" | jq -r '.notification_type // empty' 2>/dev/null || true)
  if [ "$NTYPE" = "idle_prompt" ]; then
    exit 0
  fi
fi

# Silently skip if not running under tmux
if [ -z "$TMUX" ] || [ -z "$TMUX_PANE" ]; then
  exit 0
fi

# Read pane/window/session state once for both skip gates below -- the icon
# gate and the tint gate are independent (a non-active pane in the active,
# viewed window needs the tint but not the icon), so neither can early-exit
# the whole script the way the old single-gate version did.
read -r PANE_ACTIVE WINDOW_ACTIVE SESSION_ATTACHED <<< "$(
  tmux display-message -t "$TMUX_PANE" -p '#{pane_active} #{window_active} #{session_attached}'
)"

# Icon gate: skip @claude_state (and the sound cue) if the user is already
# viewing this window (attached session + active window) -- no point
# flagging or sounding an alert for a window you can already see.
IS_WINDOW_VIEWED=0
if [ "$WINDOW_ACTIVE" = "1" ] && [ "$SESSION_ATTACHED" = "1" ]; then
  IS_WINDOW_VIEWED=1
fi

if [ "$IS_WINDOW_VIEWED" = "0" ]; then
  tmux set-option -w -t "$TMUX_PANE" "@claude_state" "$STATE"
fi

# Tint gate: stricter superset of the icon gate above -- skip the tint only
# when the pane is also the active one in that viewed window. A non-active
# pane in the active window (a split you're not focused on) still gets
# tinted, and so does any pane in a non-active window.
IS_PANE_VIEWED=0
if [ "$PANE_ACTIVE" = "1" ] && [ "$IS_WINDOW_VIEWED" = "1" ]; then
  IS_PANE_VIEWED=1
fi

if [ "$IS_PANE_VIEWED" = "0" ]; then
  case "$STATE" in
    done)         TINT_COLOR="$TINT_COLOR_DONE" ;;
    notification) TINT_COLOR="$TINT_COLOR_NOTIFICATION" ;;
  esac
  tmux set-option -p -t "$TMUX_PANE" window-style "bg=$TINT_COLOR"
  tmux set-option -p -t "$TMUX_PANE" "@claude_pane_state" "$STATE"
fi

# Audible "go look" cue -- skip it under the same condition the icon uses
# (unchanged from before the tint gate existed): no point sounding an alert
# for a window you're already viewing.
if [ "$IS_WINDOW_VIEWED" = "0" ]; then
  play_attention_sound "$STATE"
fi
