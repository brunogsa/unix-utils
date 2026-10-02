"""Blackbox CLI tests for fetch-issue-context.py.

Every fixture is a fake `linear` executable and a fake Jira helper
script written under tmp_path, with HOME and PATH pointed at them, so
no case touches a real tracker or the user's real skills tree.

Usage:
  pytest configs/ai-docs/claude/skills/code-review-pipeline/scripts/tests/fetch-issue-context.test.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "fetch-issue-context.py"

LINEAR_KEY = "CMSBQ-2117"
LINEAR_BLOCK = "# CMSBQ-2117: Fix login redirect\n\nUsers land on a blank page."
JIRA_KEY = "PAY-482"
JIRA_BLOCK = "## Jira Card: PAY-482 - Retry failed charges\n\nCharges retry twice."
UNKNOWN_KEY = "NOPE-1"


def _make_linear(tmp_path, sleep_seconds=0):
    """Fake `linear` on a PATH dir: prints LINEAR_BLOCK for LINEAR_KEY,
    exits 1 otherwise, and appends its argv to argv.log."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "linear"
    script.write_text(
        "#!/bin/bash\n"
        f'echo "$@" >> "{tmp_path}/argv.log"\n'
        f"sleep {sleep_seconds}\n"
        f'if [ "$3" = "{LINEAR_KEY}" ]; then\n'
        f"  printf '%s\\n' '{LINEAR_BLOCK}'\n"
        "  exit 0\n"
        "fi\n"
        "echo 'Failed to view issue: Could not find referenced Issue.' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir


def _make_jira_helper(tmp_path):
    """Fake Jira helper under tmp_path/home, records each call in jira-called.log."""
    helper = tmp_path / "home/.claude/skills/jira-cli/scripts/fetch-jira-review-context.sh"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        "fetch-jira-review-context() {\n"
        f'  echo "$1" >> "{tmp_path}/jira-called.log"\n'
        f'  if [ "$1" = "{JIRA_KEY}" ]; then\n'
        f"    printf '%s\\n' '{JIRA_BLOCK}'\n"
        "    return 0\n"
        "  fi\n"
        "  return 1\n"
        "}\n",
        encoding="utf-8",
    )


def _env(
    tmp_path,
    jira_url: "str | None" = "https://acme.atlassian.net",
    with_linear=True,
    sleep_seconds=0,
):
    """Environment with HOME at the fixture tree and PATH holding the fake
    linear first (or, when absent, only the system dirs bash needs)."""
    env = dict(os.environ)
    env["HOME"] = str(tmp_path / "home")
    if with_linear:
        env["PATH"] = f"{_make_linear(tmp_path, sleep_seconds)}{os.pathsep}{os.environ['PATH']}"
    else:
        env["PATH"] = _path_without_linear()
    if jira_url is None:
        env.pop("JIRA_URL", None)
    else:
        env["JIRA_URL"] = jira_url
    return env


def _path_without_linear():
    dirs = [d for d in os.environ["PATH"].split(os.pathsep) if not (Path(d) / "linear").exists()]
    return os.pathsep.join(dirs)


def _run(stdin, env, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True, env=env,
    )


def test_linear_reference_is_fetched_through_the_cli_with_the_three_no_flags(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"linear {LINEAR_KEY}\n", _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert LINEAR_BLOCK in result.stdout
    argv = (tmp_path / "argv.log").read_text()
    for flag in ("--no-comments", "--no-pager", "--no-download"):
        assert flag in argv
    assert f"issue view {LINEAR_KEY}" in argv
    assert f"fetched linear {LINEAR_KEY}" in result.stderr


def test_jira_reference_is_fetched_through_the_helper_when_jira_url_is_set(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"jira {JIRA_KEY}\n", _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert JIRA_BLOCK in result.stdout
    assert f"fetched jira {JIRA_KEY}" in result.stderr


def test_jira_reference_is_skipped_with_exit_one_when_jira_url_is_unset(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"jira {JIRA_KEY}\n", _env(tmp_path, jira_url=None))
    assert result.returncode == 1
    assert result.stdout == ""
    assert "JIRA_URL unset" in result.stderr
    assert not (tmp_path / "jira-called.log").exists()


def test_unknown_reference_that_jira_misses_is_fetched_from_linear(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"unknown {LINEAR_KEY}\n", _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert LINEAR_BLOCK in result.stdout
    assert (tmp_path / "jira-called.log").read_text().strip() == LINEAR_KEY
    assert f"fetched linear {LINEAR_KEY}" in result.stderr


def test_unknown_reference_goes_straight_to_linear_when_jira_url_is_unset(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"unknown {LINEAR_KEY}\n", _env(tmp_path, jira_url=None))
    assert result.returncode == 0, result.stderr
    assert LINEAR_BLOCK in result.stdout
    assert not (tmp_path / "jira-called.log").exists()


def test_two_references_print_two_snippets_in_input_order_separated_by_one_blank_line(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"jira {JIRA_KEY}\nlinear {LINEAR_KEY}\n", _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{JIRA_BLOCK}\n\n{LINEAR_BLOCK}"


def test_reference_nobody_has_gives_empty_stdout_a_not_found_note_and_exit_one(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"unknown {UNKNOWN_KEY}\n", _env(tmp_path))
    assert result.returncode == 1
    assert result.stdout == ""
    assert f"{UNKNOWN_KEY} not found (tried jira, linear)" in result.stderr


def test_one_hit_and_one_miss_prints_the_hit_and_exits_one(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"linear {LINEAR_KEY}\nlinear {UNKNOWN_KEY}\n", _env(tmp_path))
    assert result.returncode == 1
    assert LINEAR_BLOCK in result.stdout
    assert f"{UNKNOWN_KEY} not found" in result.stderr


def test_empty_stdin_exits_zero_with_empty_stdout(tmp_path):
    result = _run("", _env(tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""


def test_linear_reference_with_no_linear_cli_on_path_exits_one_with_a_not_installed_note(tmp_path):
    _make_jira_helper(tmp_path)
    result = _run(f"linear {LINEAR_KEY}\n", _env(tmp_path, with_linear=False))
    assert result.returncode == 1
    assert f"linear skipped for {LINEAR_KEY} (linear CLI not installed)" in result.stderr


def test_linear_cli_slower_than_the_timeout_counts_as_a_miss_and_returns_promptly(tmp_path):
    _make_jira_helper(tmp_path)
    env = _env(tmp_path, sleep_seconds=5)
    started = time.monotonic()
    result = _run(f"linear {LINEAR_KEY}\n", env, "--timeout", "1")
    elapsed = time.monotonic() - started
    assert result.returncode == 1
    assert "timed out" in result.stderr
    assert elapsed < 4


def test_malformed_line_exits_two(tmp_path):
    result = _run("just-one-token\n", _env(tmp_path))
    assert result.returncode == 2
    assert result.stderr != ""


def test_help_exits_zero_with_usage_on_stdout(tmp_path):
    result = _run("", _env(tmp_path), "--help")
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
