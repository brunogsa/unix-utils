#!/usr/bin/env bash
# SessionStart guard: typing /model or /advisor in any session writes
# straight into the global ~/.claude/settings.json — and with that file
# symlinked into unix-utils, a session-local choice silently becomes
# the committed steady state (documented: code.claude.com/docs/en/
# model-config.md, .../advisor.md).
#
# Steady state is defined as the git-committed version of the file, so
# this guard hardcodes no model names: it warns whenever the live
# model/advisorModel keys differ from HEAD, and whenever the symlink
# itself got detached by a settings write.
#
# Fail-quiet contract: a guard bug must never break session startup,
# so every unexpected condition exits 0 with no output.

set -u
LIVE="$HOME/.claude/settings.json"

if [ ! -L "$LIVE" ]; then
  echo "WARNING: ~/.claude/settings.json is not a symlink — a settings write detached it from unix-utils. Diff it against the repo file, port any wanted change, then re-run install.sh."
  exit 0
fi

REPO_FILE="$(readlink "$LIVE")"
REPO_DIR="${REPO_FILE%/configs/*}"
[ -n "$REPO_FILE" ] && [ -d "$REPO_DIR/.git" ] || exit 0

drift=$(python3 - "$REPO_FILE" "$REPO_DIR" <<'PY'
import json, subprocess, sys

live_path, repo = sys.argv[1], sys.argv[2]
rel = live_path[len(repo) + 1:]
try:
    committed = json.loads(subprocess.run(
        ["git", "-C", repo, "show", f"HEAD:{rel}"],
        capture_output=True, text=True, check=True).stdout)
    with open(live_path) as f:
        live = json.load(f)
except Exception:
    sys.exit(0)

for key in ("model", "advisorModel"):
    if committed.get(key) != live.get(key):
        print(f"  {key}: committed={committed.get(key)!r} live={live.get(key)!r}")
PY
) || exit 0

if [ -n "$drift" ]; then
  echo "WARNING: settings.json model keys drifted from the committed steady state (a typed /model or /advisor leaks globally):"
  echo "$drift"
  echo "If unwanted, restore with: git -C $REPO_DIR checkout -- configs/ai-docs/claude/settings.json"
  echo "Session-only alternatives that never touch the file: the 's' key inside the /model picker, or launching with 'claude --model <m>' / 'claude --advisor <m>'."
fi
exit 0
