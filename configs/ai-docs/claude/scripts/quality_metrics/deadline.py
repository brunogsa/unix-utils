"""Runs a command under a monotonic deadline, killing its whole
process group when the deadline passes.
"""

import os
import signal
import subprocess
import time
from dataclasses import dataclass

from quality_metrics.tools import ToolError


@dataclass(frozen=True)
class DeadlineResult:
    """How a command ended: killed at the deadline, or finished
    with an exit code and its output."""

    killed: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


def run_until(command, deadline, cwd, env):
    """Run a command until `deadline` (a `time.monotonic()`
    value) passes.

    The command leads its own process group, and the whole
    group is killed on timeout: Stryker and mutmut fork workers
    that `subprocess.run(timeout=...)` would leave running.
    """
    try:
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", start_new_session=True,
        )
    except FileNotFoundError as error:
        raise ToolError(f"'{command[0]}' is not installed; run install.sh") from error
    try:
        stdout, stderr = process.communicate(timeout=max(0.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        _kill_group(process)
        return DeadlineResult(killed=True)
    return DeadlineResult(killed=False, returncode=process.returncode, stdout=stdout, stderr=stderr)


def _kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.communicate()
