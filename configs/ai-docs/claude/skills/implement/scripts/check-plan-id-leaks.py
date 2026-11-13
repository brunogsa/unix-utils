#!/usr/bin/env python3
"""check-plan-id-leaks.py - flag plan acceptance-criterion (`AC-<n>`) and
plan-task (`T<n>`) IDs that a branch adds to committed files.

A plan is never committed, so an ID copied out of it is undecodable in
code. The token rule mirrors the plan annotation grammar
`// AC-<n>... T<n>...` that check-ac-references.py in
spec-driven-development/scripts/ exempts inside plan code fences:
  - `AC-<n>` (word-bounded) is flagged anywhere on an added line, unless
    that line also cites a `.md` path committed at HEAD - the shape a
    repo uses to keep a design-doc ID decodable.
  - `T<n>` (word-bounded) is flagged only on a line that also holds an
    `AC-<n>`, or inside a code comment (`//`, `# `, `/*`, `*`), since a
    bare `T1` in code is a numbered type parameter, not a plan task.

Usage:
  check-plan-id-leaks.py [--base <ref>] [--exclude <glob>]...

  --base     ref to diff from as `<ref>...HEAD`; default: the repo's base
             branch from ~/.claude/scripts/resolve-base-ref.sh, preferring
             `origin/<name>` over the local `<name>`
  --exclude  extra fnmatch glob of paths to skip, repeatable; spec_*.md,
             plan_*.md and docs/designs/** are always skipped

stdout: one `<path>:<line>: <token> - <line text>` per flagged token
stderr: a diagnostic on a usage error, a bad base ref or a git failure
exit: 0 no leak; 1 at least one leak; 2 usage error, not a git repo,
      base ref unresolvable, or git diff failed
"""

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

RESOLVE_BASE_REF = Path.home() / ".claude" / "scripts" / "resolve-base-ref.sh"

AC_TOKEN = re.compile(r"\bAC-\d+\b")
TASK_TOKEN = re.compile(r"\bT\d+\b")

# `//` must follow whitespace or line start, so the `//` inside
# a URL such as `https://` never opens a comment.
COMMENT_START = re.compile(r"(?:^|\s)(?://|/\*|# )|^\s*\*")
MD_PATH = re.compile(r"[\w./-]+\.md\b")
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

ALWAYS_EXCLUDED_NAMES = ("spec_*.md", "plan_*.md")
ALWAYS_EXCLUDED_PREFIX = "docs/designs/"


class GitError(Exception):
    pass


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def is_commit(ref):
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
    )
    return result.returncode == 0


def find_default_base():
    """`origin/<base>` when fetched, else the local `<base>`; None when
    the repo names no base branch."""
    result = subprocess.run(["bash", str(RESOLVE_BASE_REF)], capture_output=True, text=True)
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        return None
    for candidate in (f"origin/{branch}", branch):
        if is_commit(candidate):
            return candidate
    return None


def is_excluded(path, extra_globs):
    name = PurePosixPath(path).name
    if any(fnmatch.fnmatch(name, glob) for glob in ALWAYS_EXCLUDED_NAMES):
        return True
    if path.startswith(ALWAYS_EXCLUDED_PREFIX):
        return True
    return any(fnmatch.fnmatch(path, glob) for glob in extra_globs)


def get_added_lines(diff_text):
    """(path, line number, text) for every added line of a
    `--unified=0` diff, skipping deleted and binary files."""
    path = None
    line_number = 0
    in_file_header = False
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            path = None
            in_file_header = True
            continue
        if in_file_header:
            if raw.startswith("+++ "):
                target = raw[len("+++ "):]
                path = target[len("b/"):] if target.startswith("b/") else None
                continue
            hunk = HUNK_HEADER.match(raw)
            if hunk:
                in_file_header = False
                line_number = int(hunk.group(1))
            continue
        hunk = HUNK_HEADER.match(raw)
        if hunk:
            line_number = int(hunk.group(1))
        elif raw.startswith("+"):
            if path is not None:
                yield path, line_number, raw[1:]
            line_number += 1
        elif raw.startswith(" "):
            line_number += 1


def cites_committed_doc(text, committed_paths):
    return any(match.group(0) in committed_paths for match in MD_PATH.finditer(text))


def find_leaked_tokens(text, committed_paths):
    ac_tokens = AC_TOKEN.findall(text)
    has_ac = bool(ac_tokens)
    if has_ac and cites_committed_doc(text, committed_paths):
        ac_tokens = []

    comment = COMMENT_START.search(text)
    task_scope = text if has_ac else (text[comment.start():] if comment else "")
    return ac_tokens + TASK_TOKEN.findall(task_scope)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="check-plan-id-leaks.py",
        description="Flag plan AC-<n>/T<n> IDs a branch adds to committed files.",
    )
    parser.add_argument("--base", help="ref to diff from as <ref>...HEAD")
    parser.add_argument("--exclude", action="append", default=[], help="extra path glob to skip")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    try:
        git("rev-parse", "--is-inside-work-tree")
    except GitError:
        print("check-plan-id-leaks.py: not a git repository", file=sys.stderr)
        return 2

    base = args.base or find_default_base()
    if base is None:
        print(
            "check-plan-id-leaks.py: no base branch resolvable "
            "(no origin/HEAD, main or master); pass --base <ref>",
            file=sys.stderr,
        )
        return 2
    if not is_commit(base):
        print(f"check-plan-id-leaks.py: base ref not found: {base}", file=sys.stderr)
        return 2

    try:
        diff_bytes = git(
            "-c", "core.quotePath=false",
            "diff", "--no-color", "--no-ext-diff", "-M",
            "--src-prefix=a/", "--dst-prefix=b/", "--unified=0",
            f"{base}...HEAD",
        )
        committed_paths = set(
            git("ls-tree", "-r", "--name-only", "HEAD").decode("utf-8", errors="replace").splitlines()
        )
    except GitError as error:
        print(f"check-plan-id-leaks.py: {error}", file=sys.stderr)
        return 2

    diff_text = diff_bytes.decode("utf-8", errors="replace")
    found = False
    for path, line_number, text in get_added_lines(diff_text):
        if is_excluded(path, args.exclude):
            continue
        for token in find_leaked_tokens(text, committed_paths):
            print(f"{path}:{line_number}: {token} - {text.strip()}")
            found = True

    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
