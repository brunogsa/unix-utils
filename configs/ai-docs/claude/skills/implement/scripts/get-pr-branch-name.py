#!/usr/bin/env python3
# get-pr-branch-name.py - print the branch name /implement
# creates for a PR-label run's PR.
#
# Usage:
#   get-pr-branch-name.py <PR-N>
#
# Reads the current branch of the git repo at the CWD.
#
# stdout: the PR's branch name, one line.
#
# exit: 0 on success; 2 on a usage error (missing or
# malformed PR-N label, detached HEAD), with a diagnostic
# on stderr.

import re
import subprocess
import sys

PR_LABEL = re.compile(r"PR-([0-9]+)")
LAYER_SUFFIX = re.compile(r"-t[0-9]+$")

# why: "-" never "/" - git refuses refs/heads/<feat>/pr<N>
# next to an existing refs/heads/<feat>, locally and on the
# remote, so the nested name dead-ends once the root PR
# pushed <feat>.
#
# "/" stays strippable for branches named before the switch.
PR_SUFFIX = re.compile(r"[-/]pr[0-9]+$")
PR_SEPARATOR = "-pr"
USAGE = "usage: get-pr-branch-name.py <PR-N>"


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def main():
    if sys.argv[1:] in (["-h"], ["--help"]):
        print(USAGE)
        sys.exit(0)

    if len(sys.argv) != 2:
        fail(USAGE)

    label_match = PR_LABEL.fullmatch(sys.argv[1])
    if label_match is None:
        fail(f"not a PR-N label: {sys.argv[1]}")

    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not current_branch:
        fail("HEAD is detached or not in a git repo; no feature branch to name after")

    feature_branch = PR_SUFFIX.sub("", LAYER_SUFFIX.sub("", current_branch))
    print(f"{feature_branch}{PR_SEPARATOR}{label_match.group(1)}")


if __name__ == "__main__":
    main()
