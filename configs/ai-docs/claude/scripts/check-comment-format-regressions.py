#!/usr/bin/env python3
# check-comment-format-regressions.py - fail when a source file
# violates comment format.
#
# Usage:
#   check-comment-format-regressions.py [--repo-root <dir>]
#
# stdin: none.
#
# stdout: check-comment-format.js's own report, verbatim,
#   for every scanned file that violates
#
# exit: 0 nothing violates, 1 at least one scanned file
#   violates
import argparse
import subprocess
import sys
from pathlib import Path

SOURCE_GLOBS = ("*.py", "*.sh", "*.js", "*.ts")

CLAUDE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]

CHECKER = CLAUDE_DIR / "skills/doc-standards/scripts/check-comment-format.js"


def enumerate_sources(repo_root):
    """Return every tracked and untracked-but-not-ignored source file,
    repo-root-relative. Untracked files count because a brand-new file
    is untracked right up to the commit that ships it, which is
    precisely when the gate has to see it.

    -z keeps paths with spaces or unicode intact, which git's default
    output would quote and corrupt."""
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *SOURCE_GLOBS,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(p for p in completed.stdout.split("\0") if p)


def main():
    parser = argparse.ArgumentParser(
        description="Fail when a source file violates comment format."
    )
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()

    # is_file() drops a listed-but-absent path: a tracked file
    # deleted from the worktree. Handing it to the checker would
    # make it exit 2 on a missing file - an environment error
    # reported as a violation.
    scan = [
        repo_root / rel
        for rel in enumerate_sources(repo_root)
        if (repo_root / rel).is_file()
    ]

    if not scan:
        return 0

    return subprocess.run(
        ["node", str(CHECKER), *[str(p) for p in scan]]
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
