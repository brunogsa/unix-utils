import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
HOOK = SCRIPTS_DIR.parent / "hooks" / "check-lint-suppressions.py"

FEEDBACK_EXIT = 2


def run_hook_on_added_line(file_path, added_line):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": "value = 1\n",
            "new_string": added_line + "value = 1\n",
        },
        "tool_response": {"filePath": file_path},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=30,
    )


class TestCornerCases:
    @pytest.mark.parametrize("added_line, token", [
        ("x = 1  # pragma: no cover", "pragma: no cover"),
        ("/* istanbul ignore next */", "istanbul ignore"),
        ("/* c8 ignore next */", "c8 ignore"),
        ("// jscpd:ignore-start", "jscpd:ignore"),
    ])
    def test_should_block_pragma_no_cover_istanbul_ignore_c8_ignore_and_jscpd_ignore_comments_at_edit_time(
        self, added_line, token
    ):
        result = run_hook_on_added_line("/repo/src/parse.ts", added_line)

        assert result.returncode == FEEDBACK_EXIT
        assert token in result.stderr
