"""Reclaims leaked test-runner processes when machine headroom
reads NO-GO before the repo test run.

A test runner killed mid-run, or a crashed one, can leave its
workers alive, orphaned to launchd, holding gigabytes of RAM.
Those keep headroom NO-GO, so the repo test run would never
start. Only a process that is surely such a leak is killed:
one of the current user, orphaned (parent PID 1), running a
test worker, and older than 5 minutes, so no run that is still
ending loses its workers.
"""

import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from quality_metrics.tools import ToolError, run_command

ORPHAN_PARENT_PID = 1
MIN_AGE_SECONDS = 300
COMMAND_SHOWN_CHARS = 120
BUSIEST_SHOWN = 5
GRACE_POLLS, GRACE_POLL_SECONDS = 10, 0.5
LOOKUP_TIMEOUT_SECONDS = 10
PS_COMMAND = [
    "ps", "-A", "-o", "pid=,ppid=,uid=,etime=,rss=,%cpu=,command=",
]
PS_FIELDS = 7

# jest, its workers, vitest's workers, and the execnet
# bootstrap pytest-xdist starts each worker with.
TEST_WORKER_PATTERN = re.compile(
    r"node_modules/(\.bin/(jest|vitest)\b|jest(-worker|-cli)?/|vitest/)"
    r"|python[\d.]* -c import sys;exec\(eval\(sys\.stdin\.readline\(\)\)\)"
)


@dataclass(frozen=True)
class ProcessInfo:
    """One `ps` row."""

    pid: int
    ppid: int
    uid: int
    age_seconds: int
    rss_kb: int
    cpu_percent: float
    command: str


def parse_ps_output(text):
    """The ProcessInfo of each `PS_COMMAND` line; a line ps
    could not fill is skipped."""
    processes = []
    for line in text.splitlines():
        fields = line.split(None, PS_FIELDS - 1)
        if len(fields) != PS_FIELDS:
            continue
        pid, ppid, uid, elapsed, rss, cpu, command = fields
        try:
            processes.append(ProcessInfo(
                pid=int(pid), ppid=int(ppid), uid=int(uid),
                age_seconds=_elapsed_seconds(elapsed), rss_kb=int(rss),
                cpu_percent=float(cpu), command=command,
            ))
        except ValueError:
            continue
    return processes


def _elapsed_seconds(elapsed):
    """Seconds in a ps elapsed time, `[[dd-]hh:]mm:ss`."""
    days, _, clock = elapsed.rpartition("-")
    seconds = 0
    for part in clock.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds + int(days or 0) * 86400


def is_safe_to_kill(process, uid):
    """True only for an orphaned test worker of `uid` old enough
    that no run is still ending."""
    return (
        process.uid == uid
        and process.ppid == ORPHAN_PARENT_PID
        and process.age_seconds >= MIN_AGE_SECONDS
        and TEST_WORKER_PATTERN.search(process.command) is not None
    )


def reclaim_leaked_processes(repo_dir, machine=None):
    """Kill every process safe to kill and return
    `{killed, busiest_by_cpu, busiest_by_rss}`.

    Each killed entry names the repo it ran in, read from its
    working directory or else its command, and whether that is
    the measured `repo_dir`: a leak there is the repo's own
    scout. The busiest lists name what still holds the machine.
    """
    machine = machine or MachineProcesses()
    processes = machine.list_processes()
    leaked = [process for process in processes if is_safe_to_kill(process, machine.uid)]
    for process in leaked:
        machine.kill(process.pid)
    alive = [process for process in processes if process not in leaked]
    return {
        "killed": [_killed_entry(process, machine, repo_dir) for process in leaked],
        "busiest_by_cpu": _busiest(alive, lambda process: process.cpu_percent),
        "busiest_by_rss": _busiest(alive, lambda process: process.rss_kb),
    }


def _killed_entry(process, machine, repo_dir):
    repo = machine.repo_of(machine.read_cwd(process.pid) or process.command)
    return {
        "pid": process.pid,
        "command": process.command[:COMMAND_SHOWN_CHARS],
        "rss_kb": process.rss_kb,
        "age_seconds": process.age_seconds,
        "repo": repo,
        "is_repo_scout_candidate": repo is not None and Path(repo) == Path(repo_dir),
    }


def _busiest(processes, load):
    ranked = sorted(processes, key=load, reverse=True)[:BUSIEST_SHOWN]
    return [
        {
            "pid": process.pid,
            "command": process.command[:COMMAND_SHOWN_CHARS],
            "cpu_percent": process.cpu_percent,
            "rss_kb": process.rss_kb,
        }
        for process in ranked
    ]


def terminate_then_kill(pid, send_signal=os.kill, is_alive=None, sleep=time.sleep):
    """SIGTERM `pid`, then SIGKILL it if it outlives the grace
    period; a process already gone is no error."""
    is_alive = is_alive or _is_alive
    try:
        send_signal(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(GRACE_POLLS):
        if not is_alive(pid):
            return
        sleep(GRACE_POLL_SECONDS)
    try:
        send_signal(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _list_processes():
    try:
        result = run_command(PS_COMMAND, timeout=LOOKUP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise ToolError(f"ps timed out: {error}") from error
    if result.returncode != 0:
        raise ToolError(f"ps failed: {result.stderr.strip()}")
    return parse_ps_output(result.stdout)


def _read_cwd(pid):
    """The working directory of `pid`, or None when lsof cannot
    read it."""
    command = ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"]
    try:
        result = run_command(command, timeout=LOOKUP_TIMEOUT_SECONDS)
    except (ToolError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def _repo_of(location):
    """The git toplevel holding the first existing directory
    `location` names, or None.

    A command names its script by a path that may sit under
    node_modules, so the part before node_modules is tried.
    """
    for word in location.split():
        directory = word.split("/node_modules/")[0]
        if not os.path.isdir(directory):
            continue
        try:
            result = run_command(
                ["git", "-C", directory, "rev-parse", "--show-toplevel"],
                timeout=LOOKUP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            continue
        if result.returncode == 0:
            return result.stdout.strip()
    return None


@dataclass(frozen=True)
class MachineProcesses:
    """This machine's processes as the reclaim sees them, as
    the current user; injected so no test touches a real one."""

    list_processes: Callable[[], list] = _list_processes
    kill: Callable[[int], None] = terminate_then_kill
    read_cwd: Callable[[int], Optional[str]] = _read_cwd
    repo_of: Callable[[str], Optional[str]] = _repo_of
    uid: int = field(default_factory=os.getuid)
