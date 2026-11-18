"""Tests for claude-git-guard.sh, the shim that hands every Bash
PreToolUse payload to claude-git-guard.py.

The shim exists only so a session started before the cut-over,
whose settings still name the .sh hook, keeps being guarded.
Each test drives it the way Claude Code does: `bash <shim>` with
the JSON payload on stdin, verdict read from the exit code.

Usage:
  ./run-tests.py <this file>
"""

import json
import subprocess
from pathlib import Path

import pytest

SHIM = Path(__file__).resolve().parent.parent / "claude-git-guard.sh"
BLOCK_FOOTER = "See the commit-standards skill."


def run_shim(command, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    return subprocess.run(
        ["bash", str(SHIM)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd),
    )


# The old bash guard allowed a push option; only the python
# guard's push allowlist blocks it, so the second case proves
# the shim runs the python guard rather than its own old body.
@pytest.mark.parametrize("command", [
    "git push --force origin feat-checkout-retry",
    "git push -o ci.skip origin feat-checkout-retry",
])
def test_blocks_a_push_the_python_guard_blocks(tmp_path, command):
    result = run_shim(command, tmp_path)

    assert result.returncode == 2, result.stderr
    assert BLOCK_FOOTER in result.stderr


def test_allows_a_read_only_git_command(tmp_path):
    result = run_shim("git status", tmp_path)

    assert result.returncode == 0, result.stderr
