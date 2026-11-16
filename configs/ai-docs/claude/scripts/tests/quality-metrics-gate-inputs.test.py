import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
HOOK = SCRIPTS_DIR.parent / "hooks" / "check-lint-suppressions.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quality_metrics_support import commit_all, head_of, make_repo, measure_report

FEEDBACK_EXIT = 2

DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  ts:
    extensions: [.ts]
    metrics: [size]
  js:
    extensions: [.js]
    metrics: [size]
"""

PARSE_SOURCE = "export function parse(text: string): number {\n  return text.length;\n}\n"
PARSE_SOURCE_WITH_ISTANBUL_IGNORE = (
    "/* istanbul ignore next */\n" + PARSE_SOURCE
)


def write_declaration(tmp_path):
    path = tmp_path / "quality-metrics.yaml"
    path.write_text(DECLARATION_TEXT)
    return path


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


class TestHappyPath:
    def test_should_list_an_added_istanbul_ignore_comment_as_a_violation(self, tmp_path):
        repo = make_repo(tmp_path, {"src/parse.ts": PARSE_SOURCE})
        base = head_of(repo)
        (repo / "src/parse.ts").write_text(PARSE_SOURCE_WITH_ISTANBUL_IGNORE)
        commit_all(repo, "ignore a branch")

        report = measure_report(repo, write_declaration(tmp_path), "--diff", f"{base}...HEAD")

        assert report["gate_input_violations"] == [
            {"kind": "suppression", "file": "src/parse.ts", "value": "istanbul ignore"}
        ]
