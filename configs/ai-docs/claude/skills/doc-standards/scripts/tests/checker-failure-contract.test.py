"""Failure contract shared by every doc-standards checker.

A checker that cannot do its job must say so: exit 2, print nothing on
stdout, name itself and the input on stderr, and leave the file alone.
Callers run the checkers with stderr discarded and read any exit code
other than 0 or 1 as "no signal", so an exit 1 on unreadable input
reads as a false finding and an exit 0 reads as a clean file.

Checkers are discovered by glob rather than listed by hand, so a new
checker is held to the contract the moment it lands.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

INTERPRETERS = {".py": sys.executable, ".sh": "bash", ".js": "node"}


def discover_checkers():
    checkers = sorted(SCRIPTS_DIR.glob("check-*")) + sorted(SCRIPTS_DIR.glob("fix-*"))
    unknown = [c.name for c in checkers if c.suffix not in INTERPRETERS]
    if unknown:
        raise RuntimeError(f"no interpreter known for checker(s): {', '.join(unknown)}")
    return [pytest.param(c, id=c.name) for c in checkers]


CHECKERS = discover_checkers()

C_LOCALE_ENV = {**os.environ, "LC_ALL": "C"}


# Shaped so each fixer's rewrite branch fires on the UTF-8
# twin (0xE9 as C3 A9), or "bytes unchanged" proves nothing.
def write_non_utf8_fixture(tmp_path):
    path = tmp_path / "latin1.py"
    path.write_bytes(
        b"# caf\xe9 note that runs well past the sixty-four character comment cap here\n"
        + (
            'NOTES = """\n'
            "- The release checklist asks every reviewer to confirm the migration ran "
            "on staging, that the rollback script was rehearsed once, and that the "
            "on-call engineer for the week has read the runbook entry before merging\n"
            "- Rollback steps live beside the migration.\n"
            "- Each nightly export writes one compressed archive per region to the "
            "shared bucket, keeping thirty days of history for the finance team to "
            "audit — the cleanup job deletes anything older and logs every removed "
            "archive name so a missing file can be traced back to its deletion\n"
            '"""\n'
        ).encode("utf-8")
    )
    return path


def missing_path(tmp_path):
    return tmp_path / "missing.py"


def directory_path(tmp_path):
    path = tmp_path / "dir.py"
    path.mkdir()
    return path


UNREADABLE_INPUTS = [
    pytest.param(missing_path, id="missing-path"),
    pytest.param(directory_path, id="directory"),
    pytest.param(write_non_utf8_fixture, id="non-utf8-file"),
]


def write_plain_fixture(tmp_path):
    path = tmp_path / "plain.py"
    path.write_text("TIMEOUT_SECONDS = 30\n", encoding="utf-8")
    return path


def run(checker, *args, env=C_LOCALE_ENV):
    return subprocess.run(
        [INTERPRETERS[checker.suffix], str(checker), *args],
        capture_output=True,
        env=env,
    )


def prefixed_stderr_lines(result, checker):
    stderr_lines = result.stderr.decode("utf-8", errors="replace").splitlines()
    return [line for line in stderr_lines if line.startswith(f"{checker.name}: ")]


@pytest.mark.parametrize("make_input", UNREADABLE_INPUTS)
@pytest.mark.parametrize("checker", CHECKERS)
def test_exits_2_naming_itself_and_the_file_when_the_file_cannot_be_read(
    tmp_path, checker, make_input
):
    path = make_input(tmp_path)

    result = run(checker, str(path))

    stderr_lines = result.stderr.decode("utf-8", errors="replace").splitlines()
    assert result.returncode == 2
    assert result.stdout == b""
    assert any(
        line.startswith(f"{checker.name}: ") and str(path) in line
        for line in stderr_lines
    ), stderr_lines


@pytest.mark.parametrize(
    "mode_args",
    [pytest.param([], id="default-mode"), pytest.param(["--fix"], id="fix-mode")],
)
@pytest.mark.parametrize("checker", CHECKERS)
def test_leaves_a_non_utf8_file_byte_for_byte_unchanged(tmp_path, checker, mode_args):
    path = write_non_utf8_fixture(tmp_path)
    before = path.read_bytes()

    run(checker, *mode_args, str(path))

    assert path.read_bytes() == before


# A checker with no --fix mode refuses the flag through its
# unknown-option path, so naming the flag satisfies the contract
# as well as naming the file.
@pytest.mark.parametrize("checker", CHECKERS)
def test_exits_2_naming_itself_and_the_file_or_flag_when_asked_to_fix_a_non_utf8_file(
    tmp_path, checker
):
    path = write_non_utf8_fixture(tmp_path)

    result = run(checker, "--fix", str(path))

    named_lines = prefixed_stderr_lines(result, checker)
    assert result.returncode == 2
    assert result.stdout == b""
    assert any(str(path) in line or "--fix" in line for line in named_lines), named_lines


@pytest.mark.parametrize("checker", CHECKERS)
def test_exits_2_naming_itself_and_the_option_when_given_an_unknown_option(
    tmp_path, checker
):
    path = write_plain_fixture(tmp_path)

    result = run(checker, "--no-such-option", str(path))

    named_lines = prefixed_stderr_lines(result, checker)
    assert result.returncode == 2
    assert result.stdout == b""
    assert any("--no-such-option" in line for line in named_lines), named_lines


# Stopping git's repository search at the fixture directory's
# parent keeps the file outside any work tree, wherever the
# temporary directory happens to live.
@pytest.mark.parametrize("checker", CHECKERS)
def test_exits_2_naming_itself_and_the_file_when_changed_only_runs_outside_a_git_work_tree(
    tmp_path, checker
):
    path = write_plain_fixture(tmp_path)
    outside_git_env = {**C_LOCALE_ENV, "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}

    result = run(checker, "--changed-only", str(path), env=outside_git_env)

    named_lines = prefixed_stderr_lines(result, checker)
    assert result.returncode == 2
    assert result.stdout == b""
    assert any(str(path) in line for line in named_lines), named_lines
