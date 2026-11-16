"""Tests for how check-commit-subject-length.py screens a git
command run through a wrapper such as sudo, xargs or timeout.

A wrapper runs the word after its own options, so the screen
must read that word as the command word: a git alias such as
git ci, run through sudo, may still record a commit.

Usage:
  ./run-tests.py <this file>
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parent.parent / "check-commit-subject-length.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_commit_subject_length", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

# The empty verdict denies: the guard screens the command as
# a commit it could not read.
WITHHELD_VERDICT = ""


def _attribution_verdict(command):
    result = subprocess.run(
        [sys.executable, str(CHECKER), checker.ATTRIBUTED_FLAG, command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize(
    "command",
    [
        "xargs git ci -m x",
        "sudo git ci -m x",
        "nohup git ci -m x",
        "time git ci -m x",
        "nice git ci -m x",
        "exec git ci -m x",
    ],
)
def test_should_screen_a_git_alias_run_through_a_bare_wrapper_like_the_unwrapped_alias(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT
