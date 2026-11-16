#!/usr/bin/env python3
# get-test-sdd-dispatch-list.py - list test-sdd findings for
#   tdd-coder.
#
# Usage:
#   get-test-sdd-dispatch-list.py <test-sdd-verdict-path>
#
# stdin: none.
# stdout: heading line of each finding to dispatch, verbatim,
#   one per line in file order; empty when none qualify.
# exit: 0 success, 1 unreadable verdict file
import argparse
import re
import sys
from pathlib import Path

UNPLANNED_TESTS_FINDING_TITLE = "Unplanned tests added by the branch"

FINDING_HEADING = re.compile(
    r"^### \d+\. (?:\[Done\])?\[[A-Z]+\] (?P<title>.*?)\s*$"
)

FENCE_OPENER = re.compile(r"^\s*(?:```|~~~)")


def read_verdict(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(
            f"get-test-sdd-dispatch-list.py: cannot read {path}: {error}",
            file=sys.stderr,
        )
        sys.exit(1)


def list_dispatchable_headings(verdict_text):
    headings = []
    is_inside_fence = False
    for line in verdict_text.splitlines():
        if FENCE_OPENER.match(line):
            is_inside_fence = not is_inside_fence
            continue
        if is_inside_fence:
            continue
        heading = FINDING_HEADING.match(line)
        if heading and heading["title"] != UNPLANNED_TESTS_FINDING_TITLE:
            headings.append(line)
    return headings


def main():
    parser = argparse.ArgumentParser(
        description="Print the test-sdd finding headings that go to "
        "tdd-coder, leaving out the unplanned-tests finding."
    )
    parser.add_argument("verdict", help="path to a verdict_test-sdd_*.md")
    arguments = parser.parse_args()
    for heading in list_dispatchable_headings(read_verdict(arguments.verdict)):
        print(heading)


if __name__ == "__main__":
    main()
