#!/usr/bin/env bash
# Launches claude-hud. Kept in a wrapper so settings.json holds only a stable
# 1-line command — preventing Claude Code's /config write-back from stripping flags.
# Pick the newest installed HUD version dir by mtime via a portable glob loop.
# `-nt` works on macOS and Linux; avoids parsing `ls` (SC2012) and the GNU-only
# `find -printf` mtime trick that BSD find lacks.
HUD_DIR=""
for d in ~/.claude/plugins/cache/claude-hud/claude-hud/*/; do
  [ -d "$d" ] || continue
  if [ -z "$HUD_DIR" ] || [ "$d" -nt "$HUD_DIR" ]; then HUD_DIR="$d"; fi
done
# Render nothing if claude-hud is not installed (empty HUD_DIR), rather than
# exec'ing node on a relative dist/index.js that would error the statusline.
[ -n "$HUD_DIR" ] || exit 0
# Resolve node from PATH so the statusline renders on macOS (/usr/local/bin) and
# Linux (/usr/bin or nvm) alike; render nothing if node is absent rather than erroring.
NODE_BIN=$(command -v node) || exit 0
exec "$NODE_BIN" "${HUD_DIR}dist/index.js"
