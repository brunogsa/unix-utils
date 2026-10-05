#!/usr/bin/env python3
# dash-guard - Deny net-new em and en dashes in a tool call.
#
# Usage (PreToolUse hook, matcher set in settings.json):
#   dash-guard.py < tool-call.json
#   echo '{"tool_name":"Edit",...}' | dash-guard.py
#
# stdin: the PreToolUse JSON payload.
#
# stdout: a deny decision as JSON when a net-new U+2014 or
#   U+2013 is found, nothing otherwise
#
# exit: 0 always; the deny lives in the JSON, and malformed
#   input fails open

import json
import re
import sys
from pathlib import Path

EM_DASH = "\u2014"
EN_DASH = "\u2013"
DASH_PATTERN = re.compile(f"[{EM_DASH}{EN_DASH}]")

# Same names as the settings.json matcher, so a broader
# registration stays inert.
OUTGOING_TOOL_PATTERN = re.compile(
    r"^(mcp__claude_ai_Slack__slack_(send_message|send_message_draft|schedule_message"
    r"|create_canvas|update_canvas)|mcp__plugin_linear_linear__save_.*)$"
)
SNIPPET_RADIUS = 20
MAX_SNIPPETS = 3


def count_dashes(text):
    return len(DASH_PATTERN.findall(text))


def snippets_around_dashes(text):
    snippets = []
    for match in DASH_PATTERN.finditer(text):
        start = max(0, match.start() - SNIPPET_RADIUS)
        end = match.end() + SNIPPET_RADIUS
        snippets.append(text[start:end].replace("\n", " "))
        if len(snippets) == MAX_SNIPPETS:
            break
    return snippets


def collect_strings(value):
    """Yield every string value nested anywhere in dicts and lists (keys excluded)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from collect_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from collect_strings(item)


def read_baseline_file(file_path):
    """Return the file's text, "" if it does not exist, or None if it cannot be read as text."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError):
        return None


def read_notebook_cell_source(notebook_path, cell_id):
    """Return the targeted cell's source text, or None when it cannot be determined."""
    try:
        notebook = json.loads(Path(notebook_path).read_text(encoding="utf-8"))
        for cell in notebook["cells"]:
            if cell.get("id") == cell_id:
                source = cell.get("source", "")
                return "".join(source) if isinstance(source, list) else source
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return None


def is_text(*values):
    return all(isinstance(value, str) for value in values)


def check_write(tool_input):
    content, file_path = tool_input.get("content"), tool_input.get("file_path")
    if not is_text(content, file_path):
        return None
    baseline = read_baseline_file(file_path)
    if baseline is None:
        return None
    return net_new_dashes(content, count_dashes(baseline))


def check_edit(tool_input):
    old, new = tool_input.get("old_string"), tool_input.get("new_string")
    if not is_text(old, new):
        return None
    return net_new_dashes(new, count_dashes(old))


def check_multi_edit(tool_input):
    edits = tool_input.get("edits")
    if not isinstance(edits, list):
        return None
    old_total, new_texts = 0, []
    for edit in edits:
        if not isinstance(edit, dict) or not is_text(edit.get("old_string"), edit.get("new_string")):
            return None
        old_total += count_dashes(edit["old_string"])
        new_texts.append(edit["new_string"])
    return net_new_dashes("\n".join(new_texts), old_total)


def check_notebook_edit(tool_input):
    new_source = tool_input.get("new_source")
    if not is_text(new_source):
        return None
    if tool_input.get("edit_mode") == "insert":
        return net_new_dashes(new_source, 0)
    baseline = read_notebook_cell_source(tool_input.get("notebook_path"), tool_input.get("cell_id"))
    if baseline is None:
        return None
    return net_new_dashes(new_source, count_dashes(baseline))


def net_new_dashes(new_text, baseline_count):
    """Return (extra_count, snippets) when new_text holds more dashes than the baseline."""
    extra = count_dashes(new_text) - baseline_count
    if extra <= 0:
        return None
    return extra, snippets_around_dashes(new_text)


def check_outgoing_message(tool_input):
    text = "\n".join(collect_strings(tool_input))
    total = count_dashes(text)
    if total == 0:
        return None
    return total, snippets_around_dashes(text)


def check_tool_call(tool_name, tool_input):
    """Return (new_dash_count, snippets, is_outgoing) to deny, or None to allow."""
    if OUTGOING_TOOL_PATTERN.match(tool_name):
        found = check_outgoing_message(tool_input)
        return found + (True,) if found else None
    checks = {
        "Write": check_write,
        "Edit": check_edit,
        "MultiEdit": check_multi_edit,
        "NotebookEdit": check_notebook_edit,
    }
    check = checks.get(tool_name)
    found = check(tool_input) if check else None
    return found + (False,) if found else None


def build_reason(count, snippets, is_outgoing):
    noun = "dash" if count == 1 else "dashes"
    quoted = "; ".join(f'"...{snippet}..."' for snippet in snippets)
    resend_note = (
        " This text goes out as a message, so dashes already present in text you are "
        "resending (for example an issue description being updated) must be replaced too."
        if is_outgoing
        else ""
    )
    return (
        f"Found {count} new em/en {noun} (U+2014 / U+2013) in what you are about to write. "
        f"Near: {quoted}. "
        'Humans type the plain hyphen-minus "-", so rewrite each one with " - " '
        "(spaced hyphen), a comma, a colon, or parentheses. "
        'Never fuse the words as "word-word" where you meant a dash; that changes the meaning.'
        f"{resend_note}"
    )


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main():
    try:
        payload = json.load(sys.stdin)
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input")
        if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
            return
        verdict = check_tool_call(tool_name, tool_input)
    except Exception:
        # fail open: a hook bug must never block every write
        return
    if verdict:
        deny(build_reason(*verdict))


if __name__ == "__main__":
    main()
