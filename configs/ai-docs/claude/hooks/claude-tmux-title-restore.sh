#!/bin/bash
# claude-tmux-title-restore - Restore the tmux window title after a Claude Code
#                              session ends.
#
# Usage (Claude Code SessionEnd hook):
#   stdin: hook event JSON ({ session_id, reason, ... })
#
# Rationale:
#   tmux-window-title.sh captures the pre-Claude window name and
#   automatic-rename flag into pane options (@claude_prev_window_name /
#   @claude_prev_auto_rename) the first time it titles a window. This hook
#   reads those back and restores the window once the session that set them
#   is over, so a shell that outlives Claude isn't left with Claude's title.
#
#   Gated on the SessionEnd `reason` field to an allowlist -- other, logout,
#   prompt_input_exit -- the reasons that mean the session itself is ending.
#   `clear` and `resume` continue the same conceptual session (the title
#   should stay), and `bypass_permissions_disabled` is deliberately left off
#   the allowlist even though it also ends the session, because an allowlist
#   is safe by construction: an unknown or new reason can never trigger a
#   mid-session restore, unlike a `clear`-only denylist. The gate lives here,
#   in the script, rather than as a settings.json hook matcher, so the single
#   allowlist can't drift out of sync between two places and doesn't depend
#   on getting tmux's matcher pipe-syntax exactly right.
#
#   SessionEnd hooks cannot block the session or influence its behavior --
#   exit code and stdout are ignored by the harness. This is a pure
#   side-effect script: read stdin, act on tmux state, exit.
#
#   Skipped entirely outside tmux (same guard as tmux-window-title.sh), and
#   skipped if this pane never captured a pre-Claude state -- i.e. this
#   session never called tmux-window-title.sh.
#
# Examples:
#   echo '{"reason":"other"}' | claude-tmux-title-restore.sh
#   echo '{"reason":"clear"}' | claude-tmux-title-restore.sh   # no-op

set -euo pipefail

PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD=$(cat)
fi

REASON=$(printf '%s' "$PAYLOAD" | jq -r '.reason // empty' 2>/dev/null || true)

case "$REASON" in
  other|logout|prompt_input_exit) ;;
  *) exit 0 ;;
esac

# Outside tmux there is no window to restore -- succeed silently.
if [ -z "${TMUX:-}" ] || [ -z "${TMUX_PANE:-}" ]; then
  exit 0
fi

# No captured state means this session never titled the window (or a prior
# restore already ran and cleaned up) -- nothing to restore.
if ! tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name" >/dev/null 2>&1; then
  exit 0
fi

PREV_WINDOW_NAME=$(tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_window_name")
PREV_AUTO_RENAME=$(tmux show-options -p -t "$TMUX_PANE" -v "@claude_prev_auto_rename")

if [ "$PREV_AUTO_RENAME" = "on" ]; then
  # Re-enabling automatic-rename makes tmux immediately re-derive the name
  # from the pane's running command, so an explicit rename-window here would
  # just be overwritten by that re-derivation -- confirmed live (see
  # manual-verification_pane-notify.md).
  tmux set-window-option -t "$TMUX_PANE" automatic-rename on
else
  tmux rename-window -t "$TMUX_PANE" -- "$PREV_WINDOW_NAME"
  # Already off since Task 4's capture-time flip -- set explicitly anyway so
  # this branch is correct even if that invariant ever changes.
  tmux set-window-option -t "$TMUX_PANE" automatic-rename off
fi

# Clean up so a stale captured value can't leak into some future unrelated
# session that reuses this same pane.
tmux set-option -p -t "$TMUX_PANE" -u "@claude_prev_window_name"
tmux set-option -p -t "$TMUX_PANE" -u "@claude_prev_auto_rename"
