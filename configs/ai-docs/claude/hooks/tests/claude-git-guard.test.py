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
ATTRIBUTION = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TRAILER = f'-m "{ATTRIBUTION}"'
SUBJECT = "fix(hooks): tidy the git guard"
COMMIT = f'git commit -m "{SUBJECT}" {TRAILER}'
DIFF_CHECK = "git diff --cached --quiet"
ADD_CHAIN = f"{DIFF_CHECK} && git add notes.txt && {COMMIT}"
HUNK_CHAIN = f"{DIFF_CHECK} && git-hunk stage a1b2c3 d4e5f6 && {COMMIT}"

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


# Shape: one bare git segment, or the fixed commit chain


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(ADD_CHAIN, id="index check, git add of named paths, then commit"),
        pytest.param(HUNK_CHAIN, id="index check, git-hunk stage, then commit"),
        pytest.param(f"git -C /some/dir commit -m \"{SUBJECT}\" {TRAILER}", id="commit with -C"),
        pytest.param(
            f"git -C /some/dir diff --cached --quiet && git -C /some/dir add notes.txt"
            f" && git -C /some/dir commit -m \"{SUBJECT}\" {TRAILER}",
            id="chain with the same -C on every git segment",
        ),
    ],
)
def test_allows_the_sanctioned_shapes(repo, command):
    assert_allowed(run_hook(command, repo))


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(f"cd /tmp/work && {COMMIT}", id="cd before commit"),
        pytest.param(f"git add notes.txt && {COMMIT}", id="add then commit without the index check"),
        pytest.param(f"{DIFF_CHECK} && git add . && {COMMIT}", id="chain adding every path with ."),
        pytest.param(f"{DIFF_CHECK} && git add -A && {COMMIT}", id="chain adding every path with -A"),
        pytest.param(f"{DIFF_CHECK} || git add notes.txt && {COMMIT}", id="chain joined by ||"),
        pytest.param(
            f"git -C /a diff --cached --quiet && git -C /b add notes.txt && git -C /b commit -m x {TRAILER}",
            id="chain whose index check runs in another repository",
        ),
        pytest.param(f'git commit -m "costs $5" {TRAILER}', id="dollar sign in a commit message"),
        pytest.param("git push origin `git branch --show-current`", id="backtick substitution"),
        pytest.param("git push origin feature-x | tee push.log", id="pipe"),
        pytest.param("git status; git push origin feature-x", id="semicolon"),
        pytest.param("git push origin feature-x > push.log", id="redirect"),
        pytest.param("git push origin feature-x &", id="background"),
        pytest.param("(git push origin feature-x)", id="subshell"),
        pytest.param("git push origin feature-x\necho pushed", id="newline separator"),
        pytest.param("env git push -f", id="env wrapper"),
        pytest.param("echo notes.txt | xargs git commit", id="xargs wrapper"),
        pytest.param('bash -c "git push --force"', id="bash -c string"),
        pytest.param('eval "git reset --hard"', id="eval string"),
        pytest.param("git --no-pager push -f origin feature-x", id="force push after --no-pager"),
        pytest.param("git -c core.hooksPath=/dev/null push origin feature-x", id="global option other than -C"),
        pytest.param("/usr/bin/git push --force origin feature-x", id="git called by absolute path"),
    ],
)
def test_blocks_any_other_shape(repo, command):
    assert_blocked(run_hook(command, repo))
