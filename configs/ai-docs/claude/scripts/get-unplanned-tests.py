#!/usr/bin/env python3
# get-unplanned-tests.py - list tests a branch adds that no plan
#   title names.
#
# Usage:
#   get-unplanned-tests.py <plan-path> --base <ref>
#
# stdin: none; run inside the repository under test.
# stdout: JSON array, one {path, line, title, gate} object per
#   unplanned test; [] when none.
# exit: 0 success, 2 bad ref, unreadable plan or no plan titles
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"

EXTRACT_DESIGN_TESTS = (
    SKILLS_DIR / "spec-driven-development/scripts/extract-design-tests.sh"
)

GATE_UNKNOWN = "gate unknown"

PYTHON_TEST = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w*)\s*\(")

GO_TEST = re.compile(r"^func\s+(Test\w*)\s*\(")

JS_TEST = re.compile(r"""\b(?:it|test)\s*\(\s*(["'`])(.*?)\1""")

HUNK_HEADER = re.compile(r"^@@ -\S+ \+(\d+)(?:,\d+)? @@")

CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def fail(message):
    print(f"get-unplanned-tests.py: {message}", file=sys.stderr)
    sys.exit(2)


def run_git(*args):
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        fail(f"`git {' '.join(args)}` failed: {completed.stderr.strip()}")
    return completed.stdout


def normalize_title(title):
    """Reduce a title to lowercase words so a Python name, a Go name
    and a JS sentence naming the same behavior compare equal."""
    if title.startswith("test_"):
        title = title[len("test_"):]
    elif re.match(r"Test[A-Z0-9]", title):
        title = CAMEL_BOUNDARY.sub(" ", title[len("Test"):])
    return " ".join(re.sub(r"[\W_]+", " ", title.lower()).split())


def read_planned_titles(plan_path):
    completed = subprocess.run(
        [str(EXTRACT_DESIGN_TESTS), "--pairs", plan_path],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        fail(
            f"no planned titles read from {plan_path} "
            f"(extract-design-tests exit {completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    bare_titles = (
        line.split("\t", 1)[0] for line in completed.stdout.splitlines()
    )
    return {normalize_title(title) for title in bare_titles}


def declared_title(source_line):
    """Return the test title a source line declares, else None."""
    for pattern in (PYTHON_TEST, GO_TEST):
        match = pattern.match(source_line)
        if match:
            return match.group(1)
    match = JS_TEST.search(source_line)
    return match.group(2) if match else None


def list_added_tests(base):
    """Return (path, line at HEAD, title) for every test declaration
    on a `+` line of the diff from base to HEAD."""
    diff = run_git("diff", "--no-color", "--no-renames", "-U0", f"{base}..HEAD")
    added = []
    path = None
    new_line = 0
    for diff_line in diff.splitlines():
        if diff_line.startswith("+++ "):
            path = None if diff_line == "+++ /dev/null" else diff_line[6:]
            continue
        hunk = HUNK_HEADER.match(diff_line)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if path is None or not diff_line.startswith("+"):
            continue
        title = declared_title(diff_line[1:])
        if title is not None:
            added.append((path, new_line, title))
        new_line += 1
    return added


def read_gate(path, line):
    """Return the Gate trailer of the commit that last wrote this
    line at HEAD, or GATE_UNKNOWN when that commit carries none."""
    blame = run_git(
        "blame", "-L", f"{line},{line}", "--porcelain", "HEAD", "--", path
    )
    adding_commit = blame.split(None, 1)[0]
    trailer = run_git(
        "log",
        "-1",
        "--format=%(trailers:key=Gate,valueonly,unfold)",
        adding_commit,
    ).strip()
    return trailer or GATE_UNKNOWN


def main():
    parser = argparse.ArgumentParser(
        description="List tests the branch adds that match no planned "
        "title in the plan's Test Design section."
    )
    parser.add_argument("plan", help="path to the plan markdown file")
    parser.add_argument(
        "--base", required=True, help="ref the branch diverged from"
    )
    args = parser.parse_args()

    planned_titles = read_planned_titles(args.plan)
    unplanned = [
        {
            "path": path,
            "line": line,
            "title": title,
            "gate": read_gate(path, line),
        }
        for path, line, title in list_added_tests(args.base)
        if normalize_title(title) not in planned_titles
    ]
    print(json.dumps(unplanned, indent=2))


if __name__ == "__main__":
    main()
