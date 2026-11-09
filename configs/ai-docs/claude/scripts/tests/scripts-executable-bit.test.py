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

SKILLS_DIR = SCRIPTS_DIR.parent / "skills"

# synced/ holds vendored third-party skills and .trash/
# holds discarded ones - neither is a skill this repo
# ships, so their modes are not ours to enforce.
EXCLUDED_SKILL_DIRS = {"synced", ".trash"}


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
    for relative_path in listed.stdout.splitlines():
        path = REPO_ROOT / relative_path
        if path.parent != SCRIPTS_DIR:
            continue

        if _starts_with_shebang(path):
            names.append(path.name)

    return sorted(names)


def _shebang_carrying_skill_script_paths():
    """Return the repo-relative paths of the files git tracks directly in
    a skill's `scripts/` directory (`skills/<skill>/scripts/<file>`)
    whose first line is a shebang.

    Only direct children count: `scripts/tests/` and deeper helper
    directories hold test files and sourced libraries that are never
    invoked by path. `synced/` is vendored and `.trash/` is discarded,
    so neither is a skill this repo ships."""
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", str(SKILLS_DIR.relative_to(REPO_ROOT))],
        capture_output=True,
        text=True,
        check=True,
    )

    paths = []
    for relative_path in listed.stdout.splitlines():
        path = REPO_ROOT / relative_path
        skill_dir = path.parent.parent
        if path.parent.name != "scripts" or skill_dir.parent != SKILLS_DIR:
            continue

        if skill_dir.name in EXCLUDED_SKILL_DIRS:
            continue

        if _starts_with_shebang(path):
            paths.append(relative_path)

    return sorted(paths)


def _starts_with_shebang(path):
    """The shebang is what marks a file as meant to be run, which keeps
    data files and imported modules out of a rule that has nothing to
    say about them."""
    with path.open(encoding="utf-8", errors="replace") as handle:
        return handle.read(len(SHEBANG)) == SHEBANG


def _git_recorded_mode(relative_path):
    staged = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s", "--", relative_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return staged.stdout.split()[0]


class TestClaudeScriptsExecutableBit(unittest.TestCase):
    # Print every offending path, not a truncated diff - the
    # list is the fix's to-do.
    maxDiff = None

    def test_should_record_every_shebang_carrying_claude_script_as_executable_in_git(self):
        names = _shebang_carrying_script_names()

        # Anti-vacuity: an empty discovery would pass
        # the loop below while proving nothing at all
        # about the directory.
        self.assertGreater(len(names), 1, "no runnable scripts discovered")

        non_executable = [
            name
            for name in names
            if _git_recorded_mode(str((SCRIPTS_DIR / name).relative_to(REPO_ROOT))) != GIT_EXECUTABLE_MODE
        ]
        self.assertEqual(non_executable, [])

    def test_should_record_every_shebang_carrying_script_directly_under_a_skill_scripts_directory_as_executable_in_git(self):
        paths = _shebang_carrying_skill_script_paths()

        # Anti-vacuity: an empty discovery would pass
        # the loop below while proving nothing at all
        # about the skills' scripts directories.
        self.assertGreater(len(paths), 1, "no runnable skill scripts discovered")

        non_executable = [
            path for path in paths if _git_recorded_mode(path) != GIT_EXECUTABLE_MODE
        ]
        self.assertEqual(non_executable, [])
