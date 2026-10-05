"""Prove dash-guard denies net-new em/en dashes and lets everything else through.

Each test drives the real hooks/dash-guard.py as a subprocess with a
PreToolUse JSON payload on stdin, the way Claude Code does. The dash
characters are written as escapes so this file never trips the guard itself.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "dash-guard.py"
EM = "\u2014"
EN = "\u2013"
SLACK_SEND = "mcp__claude_ai_Slack__slack_send_message"
LINEAR_SAVE = "mcp__plugin_linear_linear__save_issue"


def run_hook(payload=None, raw=None):
    stdin_text = raw if raw is not None else json.dumps(payload)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


def decision(result):
    """Return the parsed deny object, or None when the hook stayed silent."""
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]


class DashGuardTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def assert_allowed(self, payload=None, raw=None):
        result = run_hook(payload, raw)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def assert_denied(self, payload):
        out = decision(run_hook(payload))
        self.assertIsNotNone(out, "expected a deny decision")
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        return out["permissionDecisionReason"]

    def write_file(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return str(path)


class WriteToolTestCase(DashGuardTestCase):
    def test_should_deny_a_write_that_adds_an_em_dash_to_a_new_file(self):
        reason = self.assert_denied({
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.tmp / "new.md"), "content": f"Ready {EM} done"},
        })
        self.assertIn("1", reason)

    def test_should_deny_a_write_that_adds_an_en_dash_to_a_new_file(self):
        self.assert_denied({
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.tmp / "new.md"), "content": f"pages 3{EN}5"},
        })

    def test_should_allow_a_write_with_only_ascii_hyphens(self):
        self.assert_allowed({
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.tmp / "new.md"), "content": "Ready - done"},
        })

    def test_should_allow_a_rewrite_that_keeps_the_dashes_the_file_already_has(self):
        path = self.write_file("old.md", f"one {EM} two {EM} three")
        self.assert_allowed({
            "tool_name": "Write",
            "tool_input": {"file_path": path, "content": f"uno {EM} dos {EM} tres, plus a line"},
        })

    def test_should_deny_a_rewrite_that_adds_a_dash_beyond_the_existing_count(self):
        path = self.write_file("old.md", f"one {EM} two")
        self.assert_denied({
            "tool_name": "Write",
            "tool_input": {"file_path": path, "content": f"one {EM} two {EM} three"},
        })

    def test_should_report_how_many_new_dashes_and_quote_a_snippet_around_them(self):
        reason = self.assert_denied({
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(self.tmp / "new.md"),
                "content": f"alpha {EM} beta and gamma {EN} delta",
            },
        })
        self.assertIn("2 new", reason)
        self.assertIn("alpha", reason)
        self.assertIn("gamma", reason)

    def test_should_tell_the_model_which_replacements_to_use_and_not_to_fuse_words(self):
        reason = self.assert_denied({
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.tmp / "new.md"), "content": f"a {EM} b"},
        })
        for expected in ('" - "', "comma", "colon", "parentheses", "word-word"):
            self.assertIn(expected, reason)

    def test_should_treat_a_non_utf8_existing_file_as_unreadable_and_allow(self):
        path = self.tmp / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00\x81")
        self.assert_allowed({
            "tool_name": "Write",
            "tool_input": {"file_path": str(path), "content": f"x {EM} y"},
        })


class EditToolTestCase(DashGuardTestCase):
    def test_should_deny_an_edit_whose_new_text_adds_a_dash(self):
        self.assert_denied({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/x.md", "old_string": "Ready", "new_string": f"Ready {EM}"},
        })

    def test_should_allow_an_edit_that_keeps_an_existing_dash_on_the_line_it_touches(self):
        self.assert_allowed({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/x.md",
                "old_string": f"Ready {EM} old",
                "new_string": f"Ready {EM} new",
            },
        })

    def test_should_allow_an_edit_that_removes_a_dash(self):
        self.assert_allowed({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/x.md", "old_string": f"a {EM} b", "new_string": "a - b"},
        })

    def test_should_deny_an_edit_that_swaps_an_en_dash_in_for_nothing(self):
        self.assert_denied({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/x.md", "old_string": "1-2", "new_string": f"1{EN}2"},
        })


class MultiEditToolTestCase(DashGuardTestCase):
    def test_should_deny_when_the_summed_new_dashes_exceed_the_summed_old_dashes(self):
        self.assert_denied({
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": "/x.md", "edits": [
                {"old_string": "a", "new_string": f"a {EM}"},
                {"old_string": "b", "new_string": "b"},
            ]},
        })

    def test_should_allow_when_one_edit_removes_a_dash_another_adds(self):
        self.assert_allowed({
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": "/x.md", "edits": [
                {"old_string": f"a {EM}", "new_string": "a"},
                {"old_string": "b", "new_string": f"b {EM}"},
            ]},
        })


class NotebookEditToolTestCase(DashGuardTestCase):
    def notebook(self, cells):
        nb = {"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        return self.write_file("nb.ipynb", json.dumps(nb))

    def test_should_allow_a_replace_that_keeps_the_dash_already_in_the_targeted_cell(self):
        path = self.notebook([{"id": "c1", "cell_type": "markdown", "metadata": {},
                               "source": [f"old {EM} text"]}])
        self.assert_allowed({
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": path, "cell_id": "c1", "edit_mode": "replace",
                           "new_source": f"new {EM} text"},
        })

    def test_should_deny_a_replace_that_adds_a_dash_beyond_the_targeted_cell(self):
        path = self.notebook([
            {"id": "c1", "cell_type": "markdown", "metadata": {}, "source": "plain"},
            {"id": "c2", "cell_type": "markdown", "metadata": {}, "source": f"has {EM}"},
        ])
        self.assert_denied({
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": path, "cell_id": "c1",
                           "new_source": f"now {EM}"},
        })

    def test_should_deny_an_insert_with_a_dash_since_an_insert_has_no_baseline(self):
        path = self.notebook([{"id": "c1", "cell_type": "markdown", "metadata": {},
                               "source": f"has {EM}"}])
        self.assert_denied({
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": path, "cell_id": "c1", "edit_mode": "insert",
                           "new_source": f"new {EM}"},
        })

    def test_should_allow_when_the_notebook_cannot_be_read(self):
        self.assert_allowed({
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": str(self.tmp / "missing.ipynb"), "cell_id": "c1",
                           "new_source": f"new {EM}"},
        })


class OutgoingMessageToolTestCase(DashGuardTestCase):
    def test_should_deny_a_slack_message_containing_a_dash(self):
        self.assert_denied({
            "tool_name": SLACK_SEND,
            "tool_input": {"channel_id": "C0123ABCD", "message": f"Deploy done {EM} all green"},
        })

    def test_should_allow_a_slack_message_without_a_dash(self):
        self.assert_allowed({
            "tool_name": SLACK_SEND,
            "tool_input": {"channel_id": "C0123ABCD", "message": "Deploy done - all green"},
        })

    def test_should_deny_a_dash_nested_inside_a_linear_payload(self):
        reason = self.assert_denied({
            "tool_name": LINEAR_SAVE,
            "tool_input": {"title": "Fix login", "labels": ["bug"],
                           "extra": {"steps": ["open page", f"click {EN} submit"]}},
        })
        self.assertIn("resent", reason)

    def test_should_ignore_dashes_in_non_string_values_and_dict_keys(self):
        self.assert_allowed({
            "tool_name": LINEAR_SAVE,
            "tool_input": {"priority": 2, "title": "Fix login", "archived": False},
        })


class FailOpenTestCase(DashGuardTestCase):
    def test_should_allow_unparseable_json(self):
        self.assert_allowed(raw="{not json")

    def test_should_allow_empty_stdin(self):
        self.assert_allowed(raw="")

    def test_should_allow_a_payload_that_is_not_an_object(self):
        self.assert_allowed(raw="[1, 2]")

    def test_should_allow_an_unknown_tool_even_when_it_carries_a_dash(self):
        self.assert_allowed({"tool_name": "Bash", "tool_input": {"command": f"echo {EM}"}})

    def test_should_allow_a_write_with_missing_fields(self):
        self.assert_allowed({"tool_name": "Write", "tool_input": {}})

    def test_should_allow_a_write_whose_tool_input_is_not_an_object(self):
        self.assert_allowed({"tool_name": "Write", "tool_input": "oops"})

    def test_should_allow_an_edit_with_non_string_text_fields(self):
        self.assert_allowed({"tool_name": "Edit",
                             "tool_input": {"old_string": 3, "new_string": ["x"]}})


if __name__ == "__main__":
    unittest.main()
