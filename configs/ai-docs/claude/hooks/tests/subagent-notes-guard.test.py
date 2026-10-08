"""Prove subagent-notes-guard keeps subagents off the main session's notes file.

Each test drives the real hooks/subagent-notes-guard.py as a subprocess with a
PreToolUse JSON payload on stdin, the way Claude Code does. A subagent call is
one whose payload carries agent_id, the field the hooks docs mark as present
only inside a subagent (https://code.claude.com/docs/en/hooks).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "subagent-notes-guard.py"
SETTINGS = Path(__file__).resolve().parent.parent.parent / "settings.json"
GUARD_COMMAND = "python3 ~/.claude/hooks/subagent-notes-guard.py"

# Every built-in tool that can create or modify a file by
# path: Write and Edit per the hooks reference, NotebookEdit
# per https://code.claude.com/docs/en/tools-reference;
# MultiEdit, as the sibling dash-guard matcher covers it.
WRITE_CAPABLE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

MAIN_SESSION_NOTES = (
    "/private/tmp/claude-503/-Users-brunoagostini-workspace-code-integrator/"
    "81abc238-9589-4508-b367-c031afb21e3d/scratchpad/notes.md"
)
SUBAGENT_ID = "a3f9c2e17b04d5e6"
SUBAGENT_TYPE = "code-reviewer"


def run_hook(payload=None, raw=None):
    stdin_text = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )


def write_call(file_path, agent_id=None, agent_type=None):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": "# Findings\n"},
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return payload


def edit_call(file_path, agent_id=None, agent_type=None):
    payload = write_call(file_path, agent_id, agent_type)
    payload["tool_name"] = "Edit"
    payload["tool_input"] = {
        "file_path": file_path,
        "old_string": "## Findings",
        "new_string": "## Findings\n- verdict persisted",
    }
    return payload


class SubagentNotesGuardTestCase(unittest.TestCase):
    def assert_left_to_normal_flow(self, payload=None, raw=None):
        result = run_hook(payload, raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def assert_denied(self, payload):
        result = run_hook(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        assert result.stdout.strip(), "expected a deny decision"
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        return decision["permissionDecisionReason"]


class SubagentWriteToMainSessionNotesTest(SubagentNotesGuardTestCase):
    def test_should_deny_a_subagent_writing_the_main_session_notes_file(self):
        self.assert_denied(
            write_call(MAIN_SESSION_NOTES, SUBAGENT_ID, SUBAGENT_TYPE)
        )

    def test_should_point_the_denied_subagent_at_a_notes_file_named_after_its_type(self):
        reason = self.assert_denied(
            write_call(MAIN_SESSION_NOTES, SUBAGENT_ID, SUBAGENT_TYPE)
        )
        self.assertIn("code-reviewer-notes.md", reason)
        self.assertIn("own work dir", reason)

    def test_should_deny_a_subagent_reaching_the_notes_file_through_a_parent_dir_segment(self):
        sneaky_path = MAIN_SESSION_NOTES.replace(
            "scratchpad/notes.md", "scratchpad/wave1/../notes.md"
        )
        self.assert_denied(write_call(sneaky_path, SUBAGENT_ID, SUBAGENT_TYPE))


class SubagentEditToMainSessionNotesTest(SubagentNotesGuardTestCase):
    def test_should_deny_a_subagent_editing_the_main_session_notes_file(self):
        reason = self.assert_denied(
            edit_call(MAIN_SESSION_NOTES, SUBAGENT_ID, SUBAGENT_TYPE)
        )
        self.assertIn("code-reviewer-notes.md", reason)


class WritesLeftToNormalPermissionFlowTest(SubagentNotesGuardTestCase):
    def test_should_leave_the_main_session_writing_its_own_notes_file_alone(self):
        self.assert_left_to_normal_flow(write_call(MAIN_SESSION_NOTES))

    def test_should_leave_the_main_session_editing_its_own_notes_file_alone(self):
        self.assert_left_to_normal_flow(edit_call(MAIN_SESSION_NOTES))

    def test_should_leave_a_main_session_started_with_an_agent_flag_writing_its_notes_alone(self):
        # An --agent session carries agent_type without
        # agent_id; it is still the main thread, the notes
        # file's owner.
        self.assert_left_to_normal_flow(
            write_call(MAIN_SESSION_NOTES, agent_type="tdd-coder")
        )

    def test_should_leave_a_subagent_writing_a_review_wave_file_under_tmp_alone(self):
        self.assert_left_to_normal_flow(
            write_call("/tmp/auto-review.Xk3p9Q/wave1.md", SUBAGENT_ID, SUBAGENT_TYPE)
        )

    def test_should_leave_a_subagent_writing_its_own_typed_notes_file_in_the_scratchpad_alone(self):
        own_notes = MAIN_SESSION_NOTES.replace("notes.md", "code-reviewer-notes.md")
        self.assert_left_to_normal_flow(
            write_call(own_notes, SUBAGENT_ID, SUBAGENT_TYPE)
        )

    def test_should_leave_a_subagent_writing_a_notes_file_outside_any_scratchpad_alone(self):
        self.assert_left_to_normal_flow(
            write_call(
                "/Users/brunoagostini/workspace/code/integrator/notes.md",
                SUBAGENT_ID,
                SUBAGENT_TYPE,
            )
        )

    def test_should_fail_open_on_unparseable_input(self):
        self.assert_left_to_normal_flow(raw="{not json")


class EveryWriteCapableToolTest(SubagentNotesGuardTestCase):
    def test_should_run_the_guard_for_every_write_capable_tool(self):
        pre_tool_use = json.loads(SETTINGS.read_text())["hooks"]["PreToolUse"]
        for tool in WRITE_CAPABLE_TOOLS:
            with self.subTest(tool=tool):
                guarding_entries = [
                    entry
                    for entry in pre_tool_use
                    if re.fullmatch(entry.get("matcher", ""), tool)
                    and any(h.get("command") == GUARD_COMMAND for h in entry["hooks"])
                ]
                self.assertTrue(guarding_entries, f"{tool} never reaches the guard")

    def test_should_deny_a_subagent_editing_the_notes_file_as_a_notebook(self):
        self.assert_denied(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "NotebookEdit",
                "tool_input": {
                    "notebook_path": MAIN_SESSION_NOTES,
                    "new_source": "# Findings",
                },
                "agent_id": SUBAGENT_ID,
                "agent_type": SUBAGENT_TYPE,
            }
        )

    def test_should_deny_a_subagent_multi_editing_the_main_session_notes_file(self):
        payload = edit_call(MAIN_SESSION_NOTES, SUBAGENT_ID, SUBAGENT_TYPE)
        payload["tool_name"] = "MultiEdit"
        payload["tool_input"] = {
            "file_path": MAIN_SESSION_NOTES,
            "edits": [{"old_string": "## Findings", "new_string": "## Done"}],
        }
        self.assert_denied(payload)


class DisguisedPathToMainSessionNotesTest(SubagentNotesGuardTestCase):
    def test_should_deny_a_subagent_writing_the_notes_file_in_another_letter_case(self):
        # macOS APFS is case-insensitive by default, so each
        # variant opens the very same notes file.
        for variant in ("Scratchpad/NOTES.md", "scratchpad/Notes.md"):
            with self.subTest(variant=variant):
                disguised = MAIN_SESSION_NOTES.replace("scratchpad/notes.md", variant)
                self.assert_denied(write_call(disguised, SUBAGENT_ID, SUBAGENT_TYPE))

    def test_should_deny_a_subagent_writing_the_notes_file_through_a_symlinked_dir(self):
        with tempfile.TemporaryDirectory() as session_dir:
            scratchpad = Path(session_dir) / "scratchpad"
            scratchpad.mkdir()
            (scratchpad / "notes.md").write_text("## Findings\n")
            alias = Path(session_dir) / "review-scratch"
            os.symlink(scratchpad, alias)
            self.assert_denied(
                write_call(str(alias / "notes.md"), SUBAGENT_ID, SUBAGENT_TYPE)
            )


if __name__ == "__main__":
    unittest.main()
