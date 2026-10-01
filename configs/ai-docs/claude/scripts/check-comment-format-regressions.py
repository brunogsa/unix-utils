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
#   violates, 2 the checker could not list its extensions
import argparse
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]

CHECKER = CLAUDE_DIR / "skills/doc-standards/scripts/check-comment-format.js"


def list_source_globs():
    """Return a `*<ext>` glob for every extension the checker gates,
    read from its --list-extensions so the set has one source.

    A failed or empty listing aborts with exit 2. Carrying on would
    hand git ls-files no globs, so the gate would scan nothing and
    pass, which is the silent pass this gate exists to prevent."""
    completed = subprocess.run(
        ["node", str(CHECKER), "--list-extensions"],
        capture_output=True,
        text=True,
    )
    extensions = completed.stdout.split()
    if completed.returncode != 0 or not extensions:
        print(
            f"`node {CHECKER} --list-extensions` gave no extensions "
            f"(exit {completed.returncode}): {completed.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    return tuple(f"*{ext}" for ext in extensions)


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
            *list_source_globs(),
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
