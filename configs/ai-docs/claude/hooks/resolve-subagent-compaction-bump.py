#!/usr/bin/env python3
# resolve-subagent-compaction-bump.py - bump the tmux window
# title's subagent compaction counter when a subagent stops.
#
# Usage:
#   resolve-subagent-compaction-bump.py   # SubagentStop hook
#
# stdin: the SubagentStop hook payload, as JSON
# stdout: nothing, so the hook adds no context to the session
# exit: 0 always, so a broken counter cannot break a session

# A subagent's own compaction fires no hook event of its own:
# SessionStart never runs inside a subagent, so the only trace
# left behind is a compact_boundary entry Claude Code appends
# to that subagent's transcript.
#
# SubagentStop is therefore the one moment the count can be
# read, and it fires again every time a resumed agent stops -
# hence the per-agent store below, which turns a re-read total
# into just the boundaries not reported yet.

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TITLE_SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "tmux-window-title.sh"
)
BUMP_FLAG = "--bump-subagent-counter"

COUNT_STORE = Path.home() / ".claude" / "state" / "subagent-compaction-counts"

# Both ids become path segments of that store, so they are held
# to what a session UUID and an agent hex id actually contain.
# Anything else is refused rather than sanitized, because a
# sanitized id would silently merge two agents' counts.
SAFE_ID = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")


def read_payload():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return None

    return payload if isinstance(payload, dict) else None


def get_safe_id(payload, field):
    value = payload.get(field)
    if not isinstance(value, str) or not SAFE_ID.match(value):
        return None

    return value


def count_compactions(transcript_path):
    """Count the compact_boundary entries a transcript records.

    Every line is parsed as JSON rather than matched as text:
    ordinary conversation text mentions compact_boundary, and a
    text match counts those too."""
    total = 0

    with open(transcript_path, encoding="utf-8", errors="replace") as transcript:
        for line in transcript:
            try:
                entry = json.loads(line)
            except Exception:
                # a partially-flushed line is no boundary
                continue

            if not isinstance(entry, dict):
                continue

            is_boundary = (
                entry.get("type") == "system"
                and entry.get("subtype") == "compact_boundary"
            )
            if is_boundary:
                total += 1

    return total


def get_reported_count(count_file):
    try:
        return int(count_file.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def write_reported_count(count_file, total):
    """Record the total through a temp file and a rename.

    Several Claude sessions run at once on this machine, so a
    plain write would let one of them read a half-written count;
    a rename is atomic and leaves no partial state to read."""
    count_file.parent.mkdir(parents=True, exist_ok=True)

    temp_file = count_file.with_name(f"{count_file.name}.{os.getpid()}.tmp")
    temp_file.write_text(f"{total}\n", encoding="utf-8")
    temp_file.replace(count_file)


def main():
    payload = read_payload()
    if payload is None:
        return

    session_id = get_safe_id(payload, "session_id")
    agent_id = get_safe_id(payload, "agent_id")
    transcript_path = payload.get("agent_transcript_path")

    if not session_id or not agent_id:
        return

    if not isinstance(transcript_path, str) or not transcript_path:
        return

    try:
        total = count_compactions(transcript_path)
    except OSError:
        # no readable transcript means no countable compaction
        return

    count_file = COUNT_STORE / session_id / agent_id
    unreported = total - get_reported_count(count_file)
    if unreported <= 0:
        return

    # Recorded before reporting, so a title script that fails
    # under-counts once instead of re-adding this agent's whole
    # history on its next stop.
    write_reported_count(count_file, total)

    for _ in range(unreported):
        subprocess.run(
            ["bash", str(TITLE_SCRIPT), BUMP_FLAG],
            check=False,
            capture_output=True,
        )


try:
    main()
except Exception:
    pass  # a broken counter must never break a session

sys.exit(0)
