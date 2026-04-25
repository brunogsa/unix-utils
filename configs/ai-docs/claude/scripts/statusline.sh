#!/usr/bin/env bash
# Launches claude-hud. Kept in a wrapper so settings.json holds only a stable
# 1-line command — preventing Claude Code's /config write-back from stripping flags.
HUD_DIR=$(ls -td ~/.claude/plugins/cache/claude-hud/claude-hud/*/ 2>/dev/null | head -1)
exec /usr/local/bin/node "${HUD_DIR}dist/index.js"
