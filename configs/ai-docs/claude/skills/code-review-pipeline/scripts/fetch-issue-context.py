#!/usr/bin/env python3
# fetch-issue-context.py - Fetch the review context of each
# Jira or Linear issue reference and print it as markdown.
#
# Usage:
#   fetch-issue-context.py [--timeout SECONDS]
#   extract-issue-refs.py < text | fetch-issue-context.py
#
# stdin: "<jira|linear|unknown> <KEY>" lines
# stdout: the fetched markdown, in input order
# stderr: one "issue-context: ..." outcome line per reference
# exit: 0 all fetched or no input, 1 any miss, 2 bad input/flag

import argparse
import os
import shutil
import signal
import subprocess
import sys

DEFAULT_TIMEOUT_SECONDS = 30
LOG_PREFIX = "issue-context:"

TRACKER_JIRA = "jira"
TRACKER_LINEAR = "linear"
TRACKER_UNKNOWN = "unknown"
TRACKERS = (TRACKER_JIRA, TRACKER_LINEAR, TRACKER_UNKNOWN)

# A bare key can belong to either tracker and both use the same
# ABC-123 shape, so only a lookup tells them apart: Jira first.
UNKNOWN_LOOKUP_ORDER = (TRACKER_JIRA, TRACKER_LINEAR)

SKIP_JIRA_UNSET = "JIRA_URL unset"
SKIP_LINEAR_MISSING = "linear CLI not installed"

# The helper is an existing bash function, so it is sourced
# rather than executed; the key arrives as $1, never spliced in.
JIRA_COMMAND = [
    "bash", "-c",
    'source "$HOME/.claude/skills/jira-cli/scripts/'
    'fetch-jira-review-context.sh" && '
    'fetch-jira-review-context "$1"',
    "_",
]
LINEAR_COMMAND = ["linear", "issue", "view"]
LINEAR_FLAGS = ["--no-comments", "--no-pager", "--no-download"]


def _positive_float(raw):
    value = float(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return value


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="fetch-issue-context.py",
        description="Fetch Jira/Linear issue context for each "
        "'<tracker> <KEY>' line on stdin and print it as markdown.",
    )
    parser.add_argument(
        "--timeout", type=_positive_float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="seconds each fetcher may run "
        f"(default {DEFAULT_TIMEOUT_SECONDS})",
    )
    return parser


def _parse_references(text):
    """Return [(tracker, key)] or raise ValueError on a bad line."""
    references = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] not in TRACKERS:
            raise ValueError(
                f"expected '<jira|linear|unknown> <KEY>', got: {line!r}"
            )
        references.append((parts[0], parts[1]))
    return references


def _run_fetcher(command, timeout_seconds):
    """Return (stdout, did_time_out). stdout is None on a miss.

    The fetcher gets its own process group so a timeout kills its
    children too; otherwise one would hold the pipe open.
    """
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return None, True
    if process.returncode != 0 or not stdout.strip():
        return None, False
    return stdout, False


def _skip_reason(tracker):
    """Return why a tracker cannot be queried, or None if it can."""
    if tracker == TRACKER_JIRA and not os.environ.get("JIRA_URL"):
        return SKIP_JIRA_UNSET
    if tracker == TRACKER_LINEAR and shutil.which("linear") is None:
        return SKIP_LINEAR_MISSING
    return None


def _fetch_from(tracker, key, timeout_seconds):
    if tracker == TRACKER_JIRA:
        return _run_fetcher([*JIRA_COMMAND, key], timeout_seconds)
    command = [*LINEAR_COMMAND, key, *LINEAR_FLAGS]
    return _run_fetcher(command, timeout_seconds)


def fetch_reference(tracker, key, timeout_seconds):
    """Return (snippet or None, one-line outcome for stderr)."""
    candidates = (
        UNKNOWN_LOOKUP_ORDER if tracker == TRACKER_UNKNOWN else (tracker,)
    )
    tried = []
    skipped = []
    for candidate in candidates:
        reason = _skip_reason(candidate)
        if reason is not None:
            skipped.append((candidate, reason))
            continue
        snippet, did_time_out = _fetch_from(candidate, key, timeout_seconds)
        if snippet is not None:
            return snippet, f"{LOG_PREFIX} fetched {candidate} {key}"
        note = f" (timed out after {timeout_seconds:g}s)"
        tried.append(candidate + (note if did_time_out else ""))
    return None, _describe_miss(tracker, key, tried, skipped)


def _describe_miss(tracker, key, tried, skipped):
    if not tried:
        reasons = "; ".join(reason for _, reason in skipped)
        return f"{LOG_PREFIX} {tracker} skipped for {key} ({reasons})"
    line = f"{LOG_PREFIX} {key} not found (tried {', '.join(tried)})"
    for skipped_tracker, reason in skipped:
        line += f"; {skipped_tracker} skipped: {reason}"
    return line


def main():
    args = _build_parser().parse_args()
    try:
        references = _parse_references(sys.stdin.read())
    except ValueError as error:
        print(f"fetch-issue-context.py: {error}", file=sys.stderr)
        sys.exit(2)

    snippets = []
    has_miss = False
    for tracker, key in references:
        snippet, outcome = fetch_reference(tracker, key, args.timeout)
        print(outcome, file=sys.stderr)
        if snippet is None:
            has_miss = True
        else:
            snippets.append(snippet.rstrip("\n"))

    if snippets:
        print("\n\n".join(snippets))
    sys.exit(1 if has_miss else 0)


if __name__ == "__main__":
    main()
