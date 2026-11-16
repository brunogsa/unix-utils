"""Finds the code a change touched, as line numbers per file.

A whitespace-only edit and a detected rename carry no touched
lines, so the code they move is never bound by a limit.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set

# A file with no recorded hunks (a new file, or one named by
# --files) is touched on every line.
WHOLE_FILE = None

HUNK_HEADER = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
NEW_FILE_HEADER = "+++ b/"
DELETED_FILE_HEADER = "+++ /dev/null"

# The git diff every lookup here starts from;
# core.quotepath=false keeps non-ASCII paths unquoted.
DIFF_COMMAND = (
    "-c", "core.quotepath=false", "diff", "--relative", "--no-ext-diff",
)

# NUL-separated (-z) output skips git's path quoting.
UNTRACKED_LISTING = ("ls-files", "-z", "--others", "--exclude-standard")

DIFF_ARGUMENTS = (
    *DIFF_COMMAND, "--no-color",
    "--src-prefix=a/", "--dst-prefix=b/",
    "-M", "-w", "--ignore-blank-lines", "-U0",
)


class GitError(RuntimeError):
    """A git command the touched-line lookup depends on
    failed."""


@dataclass(frozen=True)
class Target:
    """One file to measure, with the lines the change touched.

    `path` can be a temporary copy; `repo_path` names the
    real file, relative to the repo, and is None when `path`
    is already it.
    """

    path: Path
    language: Optional[str]
    touched_lines: Optional[Set[int]]
    repo_path: Optional[str] = None

    # The lizard nesting column the language declares.
    nesting_reader: str = "nd"

    # Times each global function tool; None runs it bare.
    tool_policy: Optional[object] = field(default=None, compare=False)

    def touches(self, first_line, last_line):
        if self.touched_lines is None:
            return True
        return any(first_line <= line <= last_line for line in self.touched_lines)


def repo_root():
    """The repo's top-level directory, whatever the working
    directory."""
    return Path(_git("rev-parse", "--show-toplevel").strip())


def touched_files_since(base_ref):
    """Map each changed or new file to its touched lines.

    The diff covers the working tree against `base_ref`,
    so staged and unstaged edits both count.
    New files git does not track yet are touched on every line.
    Paths are relative to the repo root whatever the working
    directory, so a run from a subdirectory still sees every
    change.
    """
    root = _git("rev-parse", "--show-toplevel").strip()
    touched = _touched_lines_in_diff(_git(*DIFF_ARGUMENTS, base_ref, cwd=root))

    # NUL-separated output skips git's path quoting, which would
    # otherwise turn a name like café.go into "caf\303\251.go".
    untracked = _git(*UNTRACKED_LISTING, cwd=root).split("\0")
    for path in filter(None, untracked):
        touched[path] = WHOLE_FILE
    return touched


def touched_files_between(base_ref, head_ref):
    """Map each file the range `base_ref...head_ref` changed to
    its touched lines."""
    return _touched_lines_in_diff(_git(*DIFF_ARGUMENTS, f"{base_ref}...{head_ref}"))


@dataclass(frozen=True)
class Change:
    """A file the range changed: its path at the base (None
    when added), and at the head (None when deleted)."""

    old_path: Optional[str]
    new_path: Optional[str]


def changes_between(base_ref, head_ref):
    """List the files the range modified, renamed or deleted,
    as base-side paths."""
    output = _git(*DIFF_COMMAND, "--name-status", "-M", f"{base_ref}...{head_ref}")
    changes = []
    for line in output.splitlines():
        status, *paths = line.split("\t")
        if status.startswith("A"):
            continue
        if status.startswith("D"):
            changes.append(Change(paths[0], None))
        else:
            changes.append(Change(paths[0], paths[-1]))
    return changes


def all_changes_between(base_ref, head_ref):
    """List every file `head_ref` changed against `base_ref`,
    an added one with no base-side path and a deleted one with
    no head-side path; git pairs renames."""
    output = _git(*DIFF_COMMAND, "--name-status", "-M", base_ref, head_ref)
    changes = []
    for line in output.splitlines():
        status, *paths = line.split("\t")
        if status.startswith("A"):
            changes.append(Change(None, paths[0]))
        elif status.startswith("D"):
            changes.append(Change(paths[0], None))
        else:
            changes.append(Change(paths[0], paths[-1]))
    return changes


def ref_exists(ref):
    """True when `ref` names a commit in this repo."""
    try:
        _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except GitError:
        return False
    return True


def merge_base(base_ref, head_ref):
    """The commit a three-dot range `base_ref...head_ref`
    diffs from."""
    return _git("merge-base", base_ref, head_ref).strip()


def file_text_at(ref, path):
    """The text of `path` (relative to the working directory)
    as of `ref`."""
    return _git("show", f"{ref}:./{path}")


def _touched_lines_in_diff(diff_text):
    touched = {}
    current_path = None
    for line in diff_text.splitlines():
        if line.startswith(DELETED_FILE_HEADER):
            current_path = None
        elif line.startswith(NEW_FILE_HEADER):
            # A name holding a space gets a trailing tab.
            current_path = line[len(NEW_FILE_HEADER):].rstrip("\t")
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


def _git(*arguments, cwd=None):
    # A binary or Latin-1 file must not crash the run, so bytes
    # that are not UTF-8 decode to a replacement character.
    result = subprocess.run(
        ["git", *arguments], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=cwd,
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout
