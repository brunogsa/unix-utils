#!/usr/bin/env python3
# run-committed-hook.py - run a hook as committed while
# its dir holds uncommitted edits.
#
# Usage:
#   run-committed-hook.py <hook.py>
#
# stdin: the Claude Code hook payload, passed on to the hook.
#
# stdout: the hook's own output, or a PreToolUse deny when
#   git cannot read or rule out its committed version.
#
# exit: the hook's own exit code; 1 when the committed
#   version cannot be read for a non-PreToolUse event;
#   2 on bad usage.

import io
import json
import os
import runpy
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

USAGE = "usage: run-committed-hook.py <hook.py>"
GIT_TIMEOUT_SECONDS = 10

# Optional locks off: a read here must never take index.lock
# from an agent committing in the same repo.
#
# LC_ALL=C keeps the "not a git repository" message in
# English, since it is the one git failure that means the
# hook has no committed version to run.
GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
NOT_A_REPO_MESSAGE = b"not a git repository"


class CommittedHookUnreadableError(Exception):
    pass


def run_git(hook_dir: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", str(hook_dir), *args],
            capture_output=True,
            check=False,
            env=GIT_ENV,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_git_stdout(result: subprocess.CompletedProcess | None, command: str) -> bytes:
    if result is None or result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() if result is not None else "git did not run"
        raise CommittedHookUnreadableError(f"git {command} failed: {detail}")
    return result.stdout


def read_git_output(hook_dir: Path, *args: str) -> bytes:
    return get_git_stdout(run_git(hook_dir, *args), args[0])


def is_in_git_repo(hook_dir: Path) -> bool:
    result = run_git(hook_dir, "rev-parse", "--is-inside-work-tree")
    if result is not None and NOT_A_REPO_MESSAGE in result.stderr:
        return False
    if get_git_stdout(result, "rev-parse").strip() != b"true":
        raise CommittedHookUnreadableError(f"{hook_dir} is inside a git dir, not a work tree")
    return True


def has_committed_hook(hook: Path) -> bool:
    # Outside any repo, or a hook HEAD never held: a fresh
    # install copy, which has only its working file to run.
    #
    # Any other git failure raises: running the working file
    # then would run the very edit this launcher fences off.
    if not is_in_git_repo(hook.parent):
        return False
    listed = read_git_output(hook.parent, "ls-tree", "--name-only", "HEAD", "--", hook.name)
    return bool(listed.strip())


def is_hook_dir_unedited(hook_dir: Path) -> bool:
    # The whole dir, not the hook alone: a hook loads its
    # siblings, and a half-edited sibling breaks it the same.
    result = run_git(hook_dir, "diff", "--quiet", "--no-ext-diff", "--no-textconv", "HEAD", "--", ".")
    return result is not None and result.returncode == 0


def extract_committed_hook_dir(hook_dir: Path, snapshot_dir: Path) -> None:
    lines = read_git_output(hook_dir, "rev-parse", "--show-toplevel", "--show-prefix").decode().splitlines()
    top_level, dir_prefix = (lines + [""])[:2]

    # Run from the top level: from a subdir, git archive also
    # filters the tree by that subdir's path and finds nothing.
    tar_bytes = read_git_output(Path(top_level), "archive", "--format=tar", f"HEAD:{dir_prefix}")
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
        archive.extractall(snapshot_dir, filter="data")


def get_hook_to_run(hook: Path, snapshot_dir: Path) -> Path:
    if not has_committed_hook(hook) or is_hook_dir_unedited(hook.parent):
        return hook
    extract_committed_hook_dir(hook.parent, snapshot_dir)
    committed_hook = snapshot_dir / hook.name
    if not committed_hook.is_file():
        raise CommittedHookUnreadableError(f"the HEAD snapshot of {hook.parent} holds no {hook.name}")
    return committed_hook


def get_event_name(payload_text: str) -> str | None:
    try:
        payload = json.loads(payload_text)
    except ValueError:
        return None
    return payload.get("hook_event_name") if isinstance(payload, dict) else None


def report_unreadable_hook(payload_text: str, hook: Path, error: Exception) -> int:
    problem = f"the committed version of {hook} could not be read ({error})"

    # A PreToolUse hook guards a call, so failing to run it must
    # deny; any other event keeps the crashed-hook outcome.
    if get_event_name(payload_text) != "PreToolUse":
        print(problem, file=sys.stderr)
        return 1
    decision = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"{problem}. Fix git or commit the hook's dir, then retry the call.",
    }
    print(json.dumps({"hookSpecificOutput": decision}))
    return 0


def run_hook(hook: Path, payload_text: str) -> None:
    # The hook runs as the script itself would: its own path in
    # __file__ and sys.path[0], so its siblings load from the
    # same snapshot it came from.
    sys.argv = [str(hook)]
    sys.path[0] = str(hook.parent)
    sys.stdin = io.StringIO(payload_text)
    runpy.run_path(str(hook), run_name="__main__")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        is_help = len(sys.argv) == 2
        print(USAGE, file=sys.stdout if is_help else sys.stderr)
        return 0 if is_help else 2

    hook = Path(sys.argv[1]).expanduser().resolve()
    payload_text = sys.stdin.read()
    with tempfile.TemporaryDirectory(prefix="committed-hook-") as snapshot_dir:
        try:
            hook_to_run = get_hook_to_run(hook, Path(snapshot_dir))
        except Exception as error:
            return report_unreadable_hook(payload_text, hook, error)
        run_hook(hook_to_run, payload_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
