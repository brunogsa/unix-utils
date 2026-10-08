#!/usr/bin/env python3
# subagent-notes-guard - Deny a subagent's Write/Edit to the
# main session's scratchpad notes.md.
#
# Usage (PreToolUse hook, every write-capable tool's matcher
# in settings.json):
#   subagent-notes-guard.py < tool-call.json
#
# stdin: the PreToolUse JSON payload.
#
# stdout: a deny decision as JSON when a subagent targets
#   <any>/scratchpad/notes.md, nothing otherwise
#
# exit: 0 always; the deny lives in the JSON, and malformed
#   input fails open

import json
import os
import sys

NOTES_FILENAME = "notes.md"
SCRATCHPAD_DIRNAME = "scratchpad"


def is_main_session_notes(file_path):
    # realpath folds `..` segments and symlinked dirs, and
    # casefold covers APFS's default case-insensitivity, so
    # no spelling that opens the same file slips past.
    resolved = os.path.realpath(file_path)
    filename = os.path.basename(resolved).casefold()
    parent_dir = os.path.basename(os.path.dirname(resolved)).casefold()
    return filename == NOTES_FILENAME and parent_dir == SCRATCHPAD_DIRNAME


def build_deny(file_path, agent_type):
    own_notes = f"{agent_type or 'subagent'}-notes.md"
    reason = (
        f"Subagents must not write {file_path}: that notes.md is the main "
        f"session's working notes. Keep yours in your own work dir, or in "
        f"{own_notes} beside it."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    if not isinstance(payload, dict):
        return

    # Only agent_id marks a subagent call; agent_type is
    # also set on a main session started with --agent,
    # which owns the file.
    is_subagent_call = bool(payload.get("agent_id"))
    tool_input = payload.get("tool_input")
    if not is_subagent_call or not isinstance(tool_input, dict):
        return

    # NotebookEdit names its target notebook_path; every other
    # write-capable tool names it file_path.
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(file_path, str):
        return

    if is_main_session_notes(file_path):
        print(json.dumps(build_deny(file_path, payload.get("agent_type"))))


if __name__ == "__main__":
    main()
