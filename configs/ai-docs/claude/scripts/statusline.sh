#!/usr/bin/env bash
# Launches claude-hud. Kept in a wrapper so settings.json holds only a stable
# 1-line command — preventing Claude Code's /config write-back from stripping flags.
HUD_DIR=$(ls -td ~/.claude/plugins/cache/claude-hud/claude-hud/*/ 2>/dev/null | head -1)
# Resolve node from PATH so the statusline renders on macOS (/usr/local/bin) and
# Linux (/usr/bin or nvm) alike; render nothing if node is absent rather than erroring.
NODE_BIN=$(command -v node) || exit 0
exec "$NODE_BIN" "${HUD_DIR}dist/index.js"
