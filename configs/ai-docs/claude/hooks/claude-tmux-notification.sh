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

# Skip if the user is currently viewing this window (attached session + active window)
VIEWING=$(tmux display-message -t "$TMUX_PANE" -p '#{?#{&&:#{window_active},#{session_attached}},1,0}')
if [ "$VIEWING" = "1" ]; then
  exit 0
fi

tmux set-option -w -t "$TMUX_PANE" "@claude_state" "$STATE"
