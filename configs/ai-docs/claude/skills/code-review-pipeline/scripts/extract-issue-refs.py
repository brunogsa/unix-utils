#!/usr/bin/env python3
# extract-issue-refs.py - List the Jira and Linear issue
# references found in free text (a PR title, then its body).
#
# Usage:
#   extract-issue-refs.py [--max N]
#   printf '%s\n%s\n' "$title" "$body" | extract-issue-refs.py
#
# stdin: free text
# stdout: "<jira|linear|unknown> <KEY>", one per distinct issue
# stderr: a usage message on a bad flag
# exit: 0 on valid input (even with no keys), 2 on a bad flag

import argparse
import re
import sys

DEFAULT_MAX_REFS = 5

# 2-10 characters of project prefix, then 1-7 issue digits.
KEY_BODY = r"[A-Z][A-Z0-9]{1,9}-[0-9]{1,7}"

# Bare keys are uppercase only and must not touch a neighbouring
# letter or digit.
#
# "abcPROJ-123" and "PROJ-12345678" are rejected, while
# "feat/PROJ-123-fix" and "(PROJ-123)" are accepted.
BARE_KEY = re.compile(rf"(?<![A-Za-z0-9])({KEY_BODY})(?![0-9])")

# Keys inside URLs are matched case-insensitively.
LINEAR_URL_KEY = re.compile(
    rf"https?://linear\.app/[^/\s]+/issue/({KEY_BODY})(?![0-9])",
    re.IGNORECASE,
)

# Jira Cloud and self-hosted both serve issues at /browse/<KEY>.
JIRA_URL_KEY = re.compile(
    rf"https?://[^\s)\]>]*?/browse/({KEY_BODY})(?![0-9])",
    re.IGNORECASE,
)

TRACKER_JIRA = "jira"
TRACKER_LINEAR = "linear"
TRACKER_UNKNOWN = "unknown"


def _non_negative_int(raw):
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return value


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="extract-issue-refs.py",
        description="List Jira and Linear issue references in stdin text.",
    )
    parser.add_argument(
        "--max", type=_non_negative_int, default=DEFAULT_MAX_REFS,
        dest="max_refs",
        help=f"keep the first N distinct references (default {DEFAULT_MAX_REFS})",
    )
    return parser


def _find_matches(text):
    """Return (position, key, tracker) for every key mention."""
    matches = []
    for pattern, tracker in (
        (LINEAR_URL_KEY, TRACKER_LINEAR),
        (JIRA_URL_KEY, TRACKER_JIRA),
        (BARE_KEY, TRACKER_UNKNOWN),
    ):
        for match in pattern.finditer(text):
            matches.append((match.start(1), match.group(1).upper(), tracker))
    return sorted(matches)


def extract_refs(text):
    """Return [(tracker, key)] in first-appearance order, one per
    key, with a URL's tracker winning over a bare mention."""
    trackers_by_key = {}
    for _position, key, tracker in _find_matches(text):
        known = trackers_by_key.get(key)
        is_upgrade = known == TRACKER_UNKNOWN and tracker != TRACKER_UNKNOWN
        if known is None or is_upgrade:
            trackers_by_key[key] = tracker
    return [(tracker, key) for key, tracker in trackers_by_key.items()]


def main():
    args = _build_parser().parse_args()
    refs = extract_refs(sys.stdin.read())
    for tracker, key in refs[: args.max_refs]:
        print(f"{tracker} {key}")


if __name__ == "__main__":
    main()
