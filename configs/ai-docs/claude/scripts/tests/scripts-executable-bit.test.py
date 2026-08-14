"""Prove every runnable script this repo ships under
`configs/ai-docs/claude/scripts/` arrives executable on a fresh clone.

The mode git records is the contract, not the mode this working copy
happens to have: `~/.claude/scripts` is a directory symlink into that
source directory, so agents invoke each script by path. One recorded as
100644 is a permission-denied every caller silently routes around.

Usage:
  pytest configs/ai-docs/claude/scripts/tests/scripts-executable-bit.test.py
"""
import subprocess
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

REPO_ROOT = Path(__file__).resolve().parents[5]

GIT_EXECUTABLE_MODE = "100755"

SHEBANG = "#!"


def _shebang_carrying_script_names():
    """Return the names of the files git tracks directly in the scripts
    directory whose first line is a shebang.

    The shebang is what marks a file as meant to be run, which keeps the
    data files that live beside the scripts (the two baseline .txt) out
    of a rule that has nothing to say about them."""
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", str(SCRIPTS_DIR.relative_to(REPO_ROOT))],
        capture_output=True,
        text=True,
        check=True,
    )

    names = []
    for relative_path in listed.stdout.split():
        path = REPO_ROOT / relative_path
        if path.parent != SCRIPTS_DIR:
            continue

        with path.open(encoding="utf-8", errors="replace") as handle:
            if handle.read(len(SHEBANG)) == SHEBANG:
                names.append(path.name)

    return sorted(names)


def _git_recorded_mode(name):
    staged = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s", "--", str((SCRIPTS_DIR / name).relative_to(REPO_ROOT))],
        capture_output=True,
        text=True,
        check=True,
    )
    return staged.stdout.split()[0]


class TestClaudeScriptsExecutableBit(unittest.TestCase):
    def test_should_record_every_shebang_carrying_claude_script_as_executable_in_git(self):
        names = _shebang_carrying_script_names()

        # Anti-vacuity: an empty discovery would pass
        # the loop below while proving nothing at all
        # about the directory.
        self.assertGreater(len(names), 1, "no runnable scripts discovered")

        non_executable = [
            name for name in names if _git_recorded_mode(name) != GIT_EXECUTABLE_MODE
        ]
        self.assertEqual(non_executable, [])
