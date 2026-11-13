"""Finds the code a change touched, as line numbers per file.

A whitespace-only edit and a detected rename carry no touched lines,
so the code they move is never bound by a limit.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# A file with no recorded hunks (a new file, or one named by
# --files) is touched on every line.
WHOLE_FILE = None

HUNK_HEADER = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
NEW_FILE_HEADER = "+++ b/"
DELETED_FILE_HEADER = "+++ /dev/null"

DIFF_ARGUMENTS = (
    "diff", "--relative", "--no-ext-diff", "--no-color",
    "-M", "-w", "--ignore-blank-lines", "-U0",
)


class GitError(RuntimeError):
    """A git command the touched-line lookup depends on failed."""


@dataclass(frozen=True)
class Target:
    """One file to measure, with the lines the change touched."""

    path: Path
    language: str
    touched_lines: object

    def touches(self, first_line, last_line):
        if self.touched_lines is WHOLE_FILE:
            return True
        return any(first_line <= line <= last_line for line in self.touched_lines)


def touched_files_since(base_ref):
    """Map each changed or new file to its touched lines.

    The diff covers the working tree against `base_ref`, so staged and
    unstaged edits both count. New files git does not track yet are
    touched on every line.
    """
    touched = _touched_lines_in_diff(_git("-c", "core.quotepath=false", *DIFF_ARGUMENTS, base_ref))
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    for path in untracked:
        touched[path] = WHOLE_FILE
    return touched


def _touched_lines_in_diff(diff_text):
    touched = {}
    current_path = None
    for line in diff_text.splitlines():
        if line.startswith(DELETED_FILE_HEADER):
            current_path = None
        elif line.startswith(NEW_FILE_HEADER):
            current_path = line[len(NEW_FILE_HEADER):]
            touched.setdefault(current_path, set())
        elif current_path and (hunk := HUNK_HEADER.match(line)):
            touched[current_path].update(_hunk_lines(hunk))
    return touched


def _hunk_lines(hunk):
    first_line = int(hunk.group(1))
    added_count = 1 if hunk.group(2) is None else int(hunk.group(2))
    if added_count == 0:
        # A deletion-only hunk adds no line, so it marks the
        # lines on both sides of the gap: a function holding
        # either one changed.
        return {first_line, first_line + 1}
    return set(range(first_line, first_line + added_count))


def _git(*arguments):
    result = subprocess.run(["git", *arguments], capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout
