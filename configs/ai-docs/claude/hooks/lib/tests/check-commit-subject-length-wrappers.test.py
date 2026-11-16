"""Tests for how check-commit-subject-length.py screens a git
command run through a wrapper such as sudo, xargs or timeout.

A wrapper runs the word after its own options, so the screen
must read that word as the command word: a git alias such as
git ci, run through sudo, may still record a commit.

Usage:
  ./run-tests.py <this file>
"""

import importlib.util
import os
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


# rg reads its config file from here, so each run starts
# without it and a test sets it only on purpose.
RIPGREP_CONFIG_ENV = "RIPGREP_CONFIG_PATH"


def _attribution_verdict(command, environment=None):
    run_environment = {key: value for key, value in os.environ.items() if key != RIPGREP_CONFIG_ENV}
    run_environment.update(environment or {})
    result = subprocess.run(
        [sys.executable, str(CHECKER), checker.ATTRIBUTED_FLAG, command],
        capture_output=True,
        text=True,
        check=False,
        env=run_environment,
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


@pytest.mark.parametrize(
    "command",
    [
        "sudo -u root git ci -m x",
        "sudo -E git ci -m x",
        "sudo -n git ci -m x",
        "timeout 5 git ci -m x",
        "timeout -s KILL 5 git ci -m x",
        "timeout -k 1 5 git ci -m x",
        "nice -n 5 git ci -m x",
        "xargs -0 git ci -m x",
        "xargs -r git ci -m x",
        "xargs -n 1 git ci -m x",
        "env -i git ci -m x",
        "env -u HOME git ci -m x",
        "command -p git ci -m x",
        "time -p git ci -m x",
        "sudo -u root nice -n 5 git ci -m x",
    ],
)
def test_should_screen_a_git_alias_run_through_a_wrapper_given_its_known_options(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


@pytest.mark.parametrize(
    "command",
    [
        "sudo -Z git status",
        "sudo --user=root git status",
        "nohup -x git status",
        "nice -5 git status",
        "timeout --foreground 5 git status",
        "xargs --null git status",
        "exec -a name git status",
        "xargs -I {} git ci -m {}",
    ],
)
def test_should_screen_as_a_possible_commit_a_wrapper_whose_options_it_cannot_read(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


@pytest.mark.parametrize(
    "command",
    [
        "stdbuf -oL git ci -m x",
        "doas git ci -m x",
        "setsid git ci -m x",
        "flock /tmp/lock git ci -m x",
        "ionice -c 3 git ci -m x",
    ],
)
def test_should_screen_a_git_alias_for_commit_run_by_a_command_not_known_as_a_wrapper(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


@pytest.mark.parametrize(
    "command",
    [
        "grep git file",
        "rg git configs",
    ],
)
def test_should_report_no_commit_for_a_later_git_word_read_as_data_by_a_command_that_runs_no_argument(command):
    assert _attribution_verdict(command) == checker.NO_COMMIT_VERDICT


# A function or alias of the same name runs its arguments, so
# the git word after grep may then run as git.
@pytest.mark.parametrize(
    "command",
    [
        'grep() { "$@"; }; grep git zz -m x',
        'function grep { "$@"; }; grep git zz -m x',
        "alias grep=sh; grep git zz",
    ],
)
def test_should_screen_a_later_git_word_after_grep_when_the_command_redefines_a_name(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


# A new PATH may find another grep, and an rg config file may
# set --pre, the program rg runs on each file.
@pytest.mark.parametrize(
    "command",
    [
        "RIPGREP_CONFIG_PATH=/tmp/c rg git zz",
        "export RIPGREP_CONFIG_PATH=/tmp/c; rg git zz",
        "PATH=/tmp/e:$PATH grep git zz -m x",
        "export PATH=/tmp/e; grep git zz -m x",
    ],
)
def test_should_screen_a_later_git_word_after_a_search_command_when_the_command_changes_its_lookup(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


# Only a lone grep or rg is surely the search program: any
# other statement, assignment or wrapper may change what that
# name runs.
@pytest.mark.parametrize(
    "command",
    [
        "hash -p /bin/sh grep; grep git zz -m x",
        "source f; grep git zz",
        ". f; grep git zz",
        "BASH_ENV=/tmp/x grep git zz",
        "eval x; grep git zz",
        "read PATH; grep git zz -m x",
        "printf -v PATH /tmp/e; grep git zz -m x",
        "command grep git zz -m x",
    ],
)
def test_should_screen_a_later_git_word_after_a_search_command_that_is_not_the_whole_command(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


def test_should_screen_a_later_git_word_after_rg_when_the_environment_names_an_rg_config():
    environment = {RIPGREP_CONFIG_ENV: "/tmp/c"}
    assert _attribution_verdict("rg git zz", environment) == WITHHELD_VERDICT


def test_should_report_no_commit_for_grep_when_the_environment_names_an_rg_config():
    environment = {RIPGREP_CONFIG_ENV: "/tmp/c"}
    assert _attribution_verdict("grep git configs/x.md", environment) == checker.NO_COMMIT_VERDICT


# The guard reads no git config: an earlier stage may write
# one, and sudo, find -exec or ssh may run git under another
# user, directory or host, so any name may be an alias there.
@pytest.mark.parametrize(
    "command",
    [
        "printf '[alias]\\n ci2 = commit\\n' >> ~/.gitconfig; stdbuf git ci2 -m x",
        "tee -a .git/config < f; stdbuf git zz -m x",
        "sudo -u other stdbuf git zz -m x",
        "find . -maxdepth 0 -exec git zz -m x ;",
        "ssh host git zz -m x",
        "stdbuf -oL git st",
        "rg --pre git zz file",
        "rg x --pre git zz",
        "rg $X git zz",
        "stdbuf git CI -m x",
        "stdbuf git commit-tree HEAD^{tree} -m x",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.zz GIT_CONFIG_VALUE_0=commit stdbuf git zz -m x",
        "export HOME=/elsewhere; stdbuf git zz -m x",
        "stdbuf git -C /elsewhere zz -m x",
        "cd /elsewhere && stdbuf git zz -m x",
    ],
)
def test_should_screen_a_later_git_word_naming_no_git_builtin_after_a_command_that_may_run_it(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


# An alias set in the environment, or a command word read
# only at run time, hides what git will run.
@pytest.mark.parametrize(
    "command",
    [
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.ci GIT_CONFIG_VALUE_0=commit git ci -m x",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.zz GIT_CONFIG_VALUE_0=commit git zz -m x",
        "$X git ci -m x",
        "$X git zz -m x",
    ],
)
def test_should_screen_a_git_alias_set_in_the_environment_or_run_by_an_expandable_word(command):
    assert _attribution_verdict(command) == WITHHELD_VERDICT


# xargs -I swaps each named word for a stdin line, so the
# status here may run as commit.
def test_should_screen_as_a_possible_commit_an_xargs_that_rewrites_its_git_words():
    assert _attribution_verdict("xargs -I status git status -m x") == WITHHELD_VERDICT


@pytest.mark.parametrize(
    "command",
    [
        "sudo ls",
        "time make",
        "xargs grep foo",
        "sudo git status",
        "time git log --oneline",
        "xargs git add",
        "sudo -u root git status",
        "timeout 5 git diff",
    ],
)
def test_should_report_no_commit_for_a_wrapper_running_no_git_alias(command):
    assert _attribution_verdict(command) == checker.NO_COMMIT_VERDICT
