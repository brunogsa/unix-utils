#!/usr/bin/env python3
# check-comment-format-regressions.py - fail when a source file
# outside the grandfathered baseline violates comment format.
#
# Usage:
#   check-comment-format-regressions.py [--repo-root <dir>]
#                                       [--baseline <file>]
#
# stdin: none.
#
# stdout: check-comment-format.js's own report, verbatim,
#   for every scanned file that violates
#
# exit: 0 nothing outside the baseline violates, 1 at least
#   one scanned file violates, 2 usage error (baseline
#   unreadable)
import argparse
import subprocess
import sys
from pathlib import Path

SOURCE_GLOBS = ("*.py", "*.sh", "*.js", "*.ts")

CLAUDE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_BASELINE = Path(__file__).resolve().parent / "comment-format-baseline.txt"

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


def load_baseline(baseline_path):
    """Return the grandfathered paths as a set. Blank and #-comment
    lines are skipped so the file can carry its own prune-only
    instructions where the next maintainer will actually read them.

    Raises OSError, which main turns into a usage error: a typo'd or
    deleted baseline must never read as 'nothing is grandfathered'
    and quietly pass a repo full of violations."""
    lines = baseline_path.read_text(encoding="utf-8").splitlines()
    entries = (line.strip() for line in lines)
    return {e for e in entries if e and not e.startswith("#")}


def main():
    parser = argparse.ArgumentParser(
        description="Fail when a source file outside the grandfathered "
        "baseline violates comment format."
    )
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()

    try:
        baseline = load_baseline(Path(args.baseline).expanduser())
    except OSError as exc:
        print(f"--baseline {args.baseline}: {exc}", file=sys.stderr)
        return 2

    # is_file() drops a listed-but-absent path: a tracked file
    # deleted from the worktree, or a stale baseline entry.
    # Either would make the checker exit 2 on a missing file -
    # an environment error reported as a violation.
    scan = [
        repo_root / rel
        for rel in enumerate_sources(repo_root)
        if rel not in baseline and (repo_root / rel).is_file()
    ]

    if not scan:
        return 0

    return subprocess.run(
        ["node", str(CHECKER), *[str(p) for p in scan]]
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
