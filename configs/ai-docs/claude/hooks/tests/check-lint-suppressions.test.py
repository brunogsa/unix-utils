"""Prove check-lint-suppressions flags net-new lint/type-checker suppressions.

Each test drives the real hooks/check-lint-suppressions.py as a subprocess
with a PostToolUse JSON payload on stdin, the way Claude Code does, and
reads the exit code and stderr - exit 2 is the channel PostToolUse feeds
back to the model.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "check-lint-suppressions.py"
FEEDBACK_EXIT = 2

ESLINT_IMPORT_ORDER = "// eslint-disable-next-line import/order\n"
IMPORT_LINE = "import { AgreementService } from '../agreement.service';\n"


def run_hook(payload=None, raw=None):
    stdin_text = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=30,
    )


def edit_payload(file_path, old_string, new_string):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": old_string,
            "new_string": new_string,
        },
        "tool_response": {"filePath": file_path},
    }


def multi_edit_payload(file_path, edits):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": file_path, "edits": edits},
        "tool_response": {"filePath": file_path},
    }


def write_payload(file_path, content, write_type):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
        "tool_response": {"filePath": file_path, "type": write_type},
    }


class LintSuppressionGuardTestCase(unittest.TestCase):
    def assert_flagged(self, payload):
        result = run_hook(payload)
        self.assertEqual(result.returncode, FEEDBACK_EXIT, result.stderr)
        return result.stderr

    def assert_silent(self, payload=None, raw=None):
        result = run_hook(payload, raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.strip(), "")


class EditAddingSuppression(LintSuppressionGuardTestCase):
    def test_should_flag_an_eslint_disable_next_line_added_above_an_import_in_a_typescript_spec(self):
        stderr = self.assert_flagged(
            edit_payload(
                "/repo/src/agreement/agreement.service.spec.ts",
                IMPORT_LINE,
                ESLINT_IMPORT_ORDER + IMPORT_LINE,
            )
        )

        self.assertIn("eslint-disable-next-line", stderr)
        self.assertIn("/repo/src/agreement/agreement.service.spec.ts", stderr)

    def test_should_tell_the_model_to_remove_the_suppression_and_run_the_checker_before_keeping_it(self):
        stderr = self.assert_flagged(
            edit_payload("/repo/src/a.spec.ts", IMPORT_LINE, ESLINT_IMPORT_ORDER + IMPORT_LINE)
        )

        self.assertIn("Remove", stderr)
        self.assertIn("linter", stderr)
        self.assertIn("failing output", stderr)

    def test_should_flag_a_python_type_ignore_comment_added_to_a_line(self):
        stderr = self.assert_flagged(
            edit_payload(
                "/repo/app/sync.py",
                "total = compute_total(order)\n",
                "total = compute_total(order)  # type: ignore[arg-type]\n",
            )
        )

        self.assertIn("type: ignore", stderr)

    def test_should_flag_every_supported_suppression_syntax_when_newly_added(self):
        cases = [
            ("/repo/a.ts", "/* eslint-disable */\n", "eslint-disable"),
            ("/repo/a.ts", "foo(); // eslint-disable-line no-console\n", "eslint-disable-line"),
            ("/repo/a.ts", "// @ts-ignore\n", "@ts-ignore"),
            ("/repo/a.ts", "// @ts-expect-error\n", "@ts-expect-error"),
            ("/repo/a.ts", "// @ts-nocheck\n", "@ts-nocheck"),
            ("/repo/a.py", "import os  # noqa: F401\n", "noqa"),
            ("/repo/a.py", "# pylint: disable=too-many-locals\n", "pylint: disable"),
            ("/repo/main.go", "x := y //nolint:errcheck\n", "nolint"),
            ("/repo/run.sh", "# shellcheck disable=SC2086\n", "shellcheck disable"),
            ("/repo/a.ts", "// biome-ignore lint/style: legacy\n", "biome-ignore"),
        ]
        for file_path, added_line, token in cases:
            with self.subTest(token=token):
                stderr = self.assert_flagged(
                    edit_payload(file_path, "value = 1\n", added_line + "value = 1\n")
                )

                self.assertIn(token, stderr)


class EditKeepingSuppressionCount(LintSuppressionGuardTestCase):
    def test_should_stay_silent_when_an_existing_suppression_is_kept_while_the_line_around_it_changes(self):
        self.assert_silent(
            edit_payload(
                "/repo/src/a.spec.ts",
                ESLINT_IMPORT_ORDER + "import { A } from './a';\n",
                ESLINT_IMPORT_ORDER + "import { A, B } from './a';\n",
            )
        )

    def test_should_stay_silent_when_an_edit_removes_a_suppression(self):
        self.assert_silent(
            edit_payload("/repo/src/a.spec.ts", ESLINT_IMPORT_ORDER + IMPORT_LINE, IMPORT_LINE)
        )


class ProseFilesExempt(LintSuppressionGuardTestCase):
    def test_should_stay_silent_when_a_markdown_rule_quotes_a_suppression_token(self):
        self.assert_silent(
            edit_payload(
                "/repo/CLAUDE.md",
                "- Never silence a check.\n",
                "- Never silence a check (no `// eslint-disable`).\n",
            )
        )

    def test_should_stay_silent_when_a_plain_text_note_quotes_a_suppression_token(self):
        self.assert_silent(
            edit_payload("/repo/NOTES.TXT", "", "avoid # type: ignore here\n")
        )


class MultiEditSuppressions(LintSuppressionGuardTestCase):
    def test_should_flag_a_multi_edit_whose_edits_add_a_suppression_in_total(self):
        stderr = self.assert_flagged(
            multi_edit_payload(
                "/repo/src/a.ts",
                [
                    {"old_string": "const a = 1;", "new_string": "const a = 2;"},
                    {"old_string": "run();", "new_string": "// @ts-ignore\nrun();"},
                ],
            )
        )

        self.assertIn("@ts-ignore", stderr)

    def test_should_stay_silent_when_a_multi_edit_moves_a_suppression_from_one_spot_to_another(self):
        self.assert_silent(
            multi_edit_payload(
                "/repo/src/a.ts",
                [
                    {"old_string": "// @ts-ignore\nfirst();", "new_string": "first();"},
                    {"old_string": "second();", "new_string": "// @ts-ignore\nsecond();"},
                ],
            )
        )


class WriteSuppressions(LintSuppressionGuardTestCase):
    def test_should_flag_a_suppression_in_a_newly_created_file(self):
        stderr = self.assert_flagged(
            write_payload("/repo/src/new.spec.ts", ESLINT_IMPORT_ORDER + IMPORT_LINE, "create")
        )

        self.assertIn("eslint-disable-next-line", stderr)

    def test_should_stay_silent_when_overwriting_an_existing_file_because_its_prior_content_is_unknown(self):
        self.assert_silent(
            write_payload("/repo/src/old.spec.ts", ESLINT_IMPORT_ORDER + IMPORT_LINE, "update")
        )


class FailOpen(LintSuppressionGuardTestCase):
    def test_should_stay_silent_for_a_tool_that_does_not_edit_files(self):
        self.assert_silent(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "/repo/a.ts"},
                "tool_response": {"content": ESLINT_IMPORT_ORDER},
            }
        )

    def test_should_stay_silent_when_stdin_is_not_valid_json(self):
        self.assert_silent(raw="{not json")

    def test_should_stay_silent_when_the_edit_payload_is_missing_its_strings(self):
        self.assert_silent({"tool_name": "Edit", "tool_input": {"file_path": "/repo/a.ts"}})


if __name__ == "__main__":
    unittest.main()
