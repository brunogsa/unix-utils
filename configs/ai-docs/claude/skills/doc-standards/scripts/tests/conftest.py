"""Shared fixtures for the fix-density-*.test.py suites.

`fixer` runs fix-density.py (and check-density.sh, to
re-verify a fix independently) over fixtures written
under pytest's tmp_path. `over_cap_pair` is the two-
sentence prose line most split tests are built from.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
FIX_SCRIPT = SCRIPTS_DIR / "fix-density.py"
DENSITY_SCRIPT = SCRIPTS_DIR / "check-density.sh"


class Fixer:
    """Runs fix-density.py over fixtures kept under one
    tmp_path."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def write(self, name, content, directory=None):
        path = (directory or self.tmp_path) / name
        path.write_text(content, encoding="utf-8")
        return path

    def run(self, target, *flags, cwd=None):
        """fix-density.py as a subprocess, stderr folded into
        stdout so a residue row or an error line is one
        string away."""
        return subprocess.run(
            [sys.executable, str(FIX_SCRIPT), *flags, str(target)],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def run_with_separate_streams(self, target):
        """fix-density.py with stdout and stderr kept apart,
        for tests that assert on one stream being empty."""
        return subprocess.run(
            [sys.executable, str(FIX_SCRIPT), str(target)],
            capture_output=True,
            text=True,
        )

    def density_exit_code(self, target, cwd=None):
        """check-density.sh run directly - the same tool a
        human would run - not fix-density.py's opinion of
        its own result."""
        return subprocess.run(
            [str(DENSITY_SCRIPT), str(target)],
            cwd=cwd,
            capture_output=True,
        ).returncode

    def new_repo(self, name):
        """An empty git repo with a local identity, so the
        fixture commit never depends on the machine's global
        git config."""
        repo = self.tmp_path / name
        repo.mkdir()
        for args in (
            ["init", "-q", "."],
            ["config", "user.email", "test@example.com"],
            ["config", "user.name", "test"],
        ):
            subprocess.run(["git", "-C", str(repo), *args], check=True)
        return repo

    def commit_all(self, repo):
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "base"],
            check=True,
        )


@pytest.fixture
def fixer(tmp_path):
    return Fixer(tmp_path)


@pytest.fixture
def over_cap_pair():
    """Two sentences that together pass the 512-char prose
    cap and each stay under it, as (first, second)."""
    first = (
        "This clause exists purely to push the line length well past the five hundred and twelve character density cap that check-density.sh now enforces on every prose line lacking a bullet marker across this repository's markdown documentation, using extra padding words solely to lengthen it convincingly without changing its meaning in any material way today."
    )
    second = (
        "This second clause continues the thought after the boundary so the split can balance both halves reasonably well, again padded with a few more harmless extra words so the whole line clears the new prose cap comfortably while each half still stays safely under it."
    )
    return first, second
