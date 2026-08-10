#!/usr/bin/env python3
"""claude-tmux-compact-bump - SessionStart:compact router that picks
which half of the tmux title's compaction counter to bump.

Usage (Claude Code SessionStart hook, matcher "compact"):
  stdin:  hook event JSON ({ agent_id, agent_type, session_id, ... })
  stdout: nothing
  exit:   always 0 -- a hook bug must never fail a compaction; losing
          a counter bump is strictly better than breaking one.

A non-empty agent_id (falling back to agent_type) means this
SessionStart fired inside a subagent's own compaction, not the main
session's -- the same agent_id/agent_type precedent used by
claude-explore-mandate-hook.sh and claude-stopfailure-resume.sh.
That case bumps the SUBAGENT half via --bump-subagent-counter.

Every other case bumps the MAIN half via --bump-counter, stdin this
hook could not parse included. The hook is wired only to
SessionStart's "compact" matcher, so a compaction definitely
happened and the only open question is whose. Filing it under main
misattributes at worst, where skipping the bump would make the
counter silently under-report a compaction that really occurred.

The title script is resolved relative to this hook's own file
location (../scripts/tmux-window-title.sh), never a hardcoded
~/.claude/ path, so it works identically from the source tree and
from the ~/.claude symlink tree install.sh sets up.

Examples:
  echo '{"agent_id":"abc123"}' | claude-tmux-compact-bump.py
    # subagent compaction -> bumps the subagent half
  echo '{"session_id":"main-1"}' | claude-tmux-compact-bump.py
    # main-session compaction -> bumps the main half
"""

import json
import subprocess
import sys
from pathlib import Path

TITLE_SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "tmux-window-title.sh"
)


def main():
    # A terminal on stdin means a human ran this by hand rather
    # than a compaction firing it, and json.load would block
    # there until EOF -- so there is nothing to bump.
    if sys.stdin.isatty():
        return

    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = None

    # Unparseable stdin, or non-object JSON, leaves no routing
    # signal -- fall through to the main bump below.
    if not isinstance(payload, dict):
        payload = {}

    agent = payload.get("agent_id") or payload.get("agent_type")
    flag = "--bump-subagent-counter" if agent else "--bump-counter"

    try:
        subprocess.run(["bash", str(TITLE_SCRIPT), flag], check=False)
    except Exception:
        pass  # a broken title script can't break the session


if __name__ == "__main__":
    main()
