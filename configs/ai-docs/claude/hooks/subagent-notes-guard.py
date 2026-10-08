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
PATH_FIELDS = ("file_path", "notebook_path")


def names_scratchpad_notes(path):
    filename = os.path.basename(path).casefold()
    parent_dir = os.path.basename(os.path.dirname(path)).casefold()
    return filename == NOTES_FILENAME and parent_dir == SCRATCHPAD_DIRNAME


def is_main_session_notes(file_path):
    # The raw spelling is checked on its own, so a path
    # realpath cannot resolve still denies instead of
    # crashing the hook into an allow.
    if names_scratchpad_notes(os.path.normpath(file_path)):
        return True

    # realpath folds symlinked dirs, and casefold covers
    # APFS's default case-insensitivity, so no spelling
    # that opens the same file slips past.
    try:
        resolved = os.path.realpath(file_path)
    except (OSError, ValueError):
        return False

    return names_scratchpad_notes(resolved)


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
    # Unparseable hook input fails open on purpose: it names
    # no caller and no path, and denying it would block every
    # Write/Edit in every session, main included.
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
    # write-capable tool names it file_path. Each field is
    # checked, so one present field never hides another.
    for field in PATH_FIELDS:
        file_path = tool_input.get(field)
        if isinstance(file_path, str) and is_main_session_notes(file_path):
            print(json.dumps(build_deny(file_path, payload.get("agent_type"))))
            return


if __name__ == "__main__":
    main()
