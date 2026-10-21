#!/usr/bin/env python3
# check-lint-suppressions - Flag lint/type-checker suppression
# comments that an Edit, MultiEdit or Write just added.
#
# Usage (PostToolUse hook, matcher Edit|MultiEdit|Write):
#   check-lint-suppressions.py < tool-call.json
#
# stdin: the PostToolUse JSON payload.
#
# stderr: on a net-new suppression, the tokens added and the
#   steps to take before keeping any of them.
#
# exit: 2 when the edit added a suppression (the channel
#   PostToolUse feeds back to the model), 0 otherwise;
#   malformed input fails open.
#
# "Added" means more suppression matches in the new text than
# in the text it replaced, so moving or keeping one is silent.
#
# Write payloads carry no prior file content: the documented
# tool_response is {filePath, type}, per
# https://code.claude.com/docs/en/hooks.
#
# So a Write counts every match as added only when type is
# "create"; an overwrite ("update") is never flagged.

import json
import re
import sys
from collections import Counter

FEEDBACK_EXIT = 2

SUPPRESSION_PATTERN = re.compile(
    r"eslint-disable(?:-next-line|-line)?"
    r"|@ts-(?:ignore|expect-error|nocheck)"
    r"|#\s*type:\s*ignore"
    r"|#\s*noqa"
    r"|#\s*pylint:\s*disable"
    r"|//\s*nolint"
    r"|#\s*shellcheck\s+disable"
    r"|biome-ignore"
)

# Rules and docs quote these tokens on purpose.
PROSE_SUFFIXES = (".md", ".txt")

WRITE_CREATE_TYPE = "create"


def count_suppressions(text):
    return Counter(SUPPRESSION_PATTERN.findall(text))


def get_replaced_and_new_text(tool_name, tool_input, tool_response):
    """Return (replaced, new) text for the edit, or None when unknown."""
    if tool_name == "Edit":
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        if isinstance(old, str) and isinstance(new, str):
            return old, new
        return None

    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return None
        string_edits = [
            edit
            for edit in edits
            if isinstance(edit, dict)
            and isinstance(edit.get("old_string"), str)
            and isinstance(edit.get("new_string"), str)
        ]
        old = "\n".join(edit["old_string"] for edit in string_edits)
        new = "\n".join(edit["new_string"] for edit in string_edits)
        return old, new

    if tool_name == "Write":
        content = tool_input.get("content")
        is_created = (
            isinstance(tool_response, dict)
            and tool_response.get("type") == WRITE_CREATE_TYPE
        )
        if isinstance(content, str) and is_created:
            return "", content
        return None

    return None


def build_feedback(file_path, added_tokens):
    token_list = ", ".join(f"`{token}`" for token in sorted(added_tokens))
    return (
        f"This edit added a lint/type-checker suppression to "
        f"{file_path}: {token_list}.\n"
        "1. Remove the suppression - do not copy it from sibling "
        "files that carry it.\n"
        "2. Run the project's linter or type-checker on the file.\n"
        "3. Keep it only if the check genuinely fails and the "
        "underlying issue cannot be fixed - then say so in chat, "
        "with the failing output.\n"
    )


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str):
        return 0
    if file_path.lower().endswith(PROSE_SUFFIXES):
        return 0

    texts = get_replaced_and_new_text(
        payload.get("tool_name"), tool_input, payload.get("tool_response")
    )
    if texts is None:
        return 0

    replaced_counts = count_suppressions(texts[0])
    new_counts = count_suppressions(texts[1])
    if sum(new_counts.values()) <= sum(replaced_counts.values()):
        return 0

    added_tokens = new_counts - replaced_counts
    sys.stderr.write(build_feedback(file_path, added_tokens))
    return FEEDBACK_EXIT


if __name__ == "__main__":
    sys.exit(main())
