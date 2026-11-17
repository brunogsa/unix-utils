"""Tests for claude-git-guard.py, the allowlist that lets a Bash
command run a risky git subcommand only in a few fixed forms.

Each test drives the real hook as a subprocess with a PreToolUse
JSON payload on stdin, the way Claude Code does, and reads its
verdict from the exit code: 0 allows, 2 blocks.

Every block assertion also requires the closing pointer line, so
a hook that crashes or is missing (python exits 2 for a missing
file) never reads as a block.

Usage:
  ./run-tests.py <this file>
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "claude-git-guard.py"
BLOCK_FOOTER = "See the commit-standards skill."

# The command the old bash guard denied as a commit missing its
# attribution, although it runs no git at all: its `$?` sent it
# to the attribution lib, which denies when unsure.
MEASURE_METRICS_COMMAND = (
    "cd <dir> && timeout 300 python3 measure-quality-metrics.py ... > out.json 2> out.err; rc=$?"
)


@pytest.fixture
def repo(tmp_path):
    """A scratch git repository holding one tracked file, so the
    commit-content libs that read the index have one to read."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, value in (("user.name", "Ada Lovelace"), ("user.email", "ada@example.com")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    (tmp_path / "notes.txt").write_text("first draft\n", encoding="utf-8")
    return tmp_path


def run_hook(command, cwd):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd),
    )


def assert_allowed(result):
    assert result.returncode == 0, result.stderr


def assert_blocked(result):
    assert result.returncode == 2, result.stderr
    assert BLOCK_FOOTER in result.stderr, result.stderr


# Fast path and parsing


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(MEASURE_METRICS_COMMAND, id="metrics run with redirects and $? but no git"),
        pytest.param("ls $HOME && echo $PWD", id="dollar expansions but no git"),
        pytest.param(
            'gh pr create --title "Guard" --body "never git push --force origin main"',
            id="force push named inside a quoted PR body",
        ),
        pytest.param('echo "git push --force origin main"', id="force push named inside a quoted echo"),
        pytest.param(
            "cat > notes.md <<'EOF'\ndon't git push --force origin main\nEOF",
            id="force push named inside a heredoc body",
        ),
        pytest.param("echo it's done", id="unbalanced quote without git"),
        pytest.param("git status && echo it's done", id="unbalanced quote beside an unguarded git"),
        pytest.param("git log --oneline | head -5", id="unguarded git subcommand in a pipe"),
    ],
)
def test_allows_commands_that_run_no_guarded_git(repo, command):
    assert_allowed(run_hook(command, repo))


def test_blocks_unbalanced_quote_beside_a_git_push(repo):
    assert_blocked(run_hook("git push origin feature-x && echo it's done", repo))


@pytest.mark.parametrize(
    "stdin_text",
    [pytest.param("not json", id="malformed JSON"), pytest.param("{}", id="no command")],
)
def test_allows_payload_without_a_readable_command(repo, stdin_text):
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True, timeout=60
    )
    assert_allowed(result)
