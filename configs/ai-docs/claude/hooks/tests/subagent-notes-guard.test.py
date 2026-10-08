"""Prove subagent-notes-guard keeps subagents off the main session's notes file.

Each test drives the real hooks/subagent-notes-guard.py as a subprocess with a
PreToolUse JSON payload on stdin, the way Claude Code does. A subagent call is
one whose payload carries agent_id, the field the hooks docs mark as present
only inside a subagent (https://code.claude.com/docs/en/hooks).
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "subagent-notes-guard.py"

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


if __name__ == "__main__":
    unittest.main()
