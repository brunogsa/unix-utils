#!/usr/bin/env python3
# get-push-route.py - say whether /implement's batch end may
# push the checked-out branch, or must leave it to the human.
#
# Usage:
#   get-push-route.py
#
# Reads the branch checked out in the git repo at the CWD.
#
# stdout: "push" or "by-hand", one line.
#
# exit: 0 with a route printed; 1 when no route can be
# decided, with a diagnostic on stderr; 2 on a usage error.

import json
import os
import subprocess
import sys
from pathlib import Path

# why: the guard owns which branches Claude may never push
# to, so asking it keeps that list in one place.
GIT_GUARD = Path(__file__).resolve().parents[3] / "hooks" / "claude-git-guard.sh"
BATCH_END_PUSH = "git push -u origin HEAD"
GUARD_ALLOWS = 0
GUARD_BLOCKS = 2


def get_guard_route(cwd):
    hook_input = json.dumps({"tool_input": {"command": BATCH_END_PUSH}, "cwd": cwd})
    result = subprocess.run(
        ["bash", str(GIT_GUARD)],
        input=hook_input,
        capture_output=True,
        text=True,
    )
    if result.returncode == GUARD_ALLOWS:
        return "push"
    if result.returncode == GUARD_BLOCKS:
        sys.stderr.write(result.stderr)
        return "by-hand"
    sys.stderr.write(result.stderr)
    sys.exit(f"error: {GIT_GUARD} exited {result.returncode} instead of allowing (0) or blocking (2) '{BATCH_END_PUSH}'")


def main(argv):
    if argv in (["-h"], ["--help"]):
        print("usage: get-push-route.py  (prints push or by-hand for the branch at the CWD)")
        return 0
    if argv:
        sys.stderr.write("usage: get-push-route.py\n")
        return 2
    print(get_guard_route(os.getcwd()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
