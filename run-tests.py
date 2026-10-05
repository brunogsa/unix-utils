#!/usr/bin/env python3
# run-tests.py - Run every test suite in this repo.
#
# Usage:
#   ./run-tests.py
#
# Exit codes:
#   0 - every suite passed
#   1 - at least one suite failed
#   2 - the headroom gate refused, or is missing; no run
#
# Three legs run here: the bash suites, the node:test
# suites, and the repo-root pytest.ini's python suites.
#
# They share one process because a separate pytest command
# is one nothing enforces, so this script's own exit code
# would silently lie about whether the repo is green.
#
# Why this exists:
#   Four separate bash test trees have no other
#   enumerator, so a suite would run only when someone
#   remembered it by name.
#
#   The hooks tree was the sharpest case: ten gate
#   suites, zero callers, so a regression in any Stop
#   hook would have shipped silently.
#
# Discovery is by glob, never by an enumerated list:
#   a runner that needs each new suite registered
#   reproduces the exact failure it exists to fix.
#
# Every suite runs even after one fails, because a
# runner that stops at the first failure hides the
# other 36.

import glob
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

BASH_SUITE_GLOBS = (
    "configs/ai-docs/claude/tests/test-*.sh",
    "configs/ai-docs/claude/scripts/tests/test-*.sh",
    "configs/ai-docs/claude/hooks/tests/test-*.sh",
    "configs/ai-docs/claude/skills/*/scripts/tests/test-*.sh",
)

# node:test suites run as one more leg, globbed over the
# same four trees as the bash suites, so a new node suite
# anywhere a bash suite can live needs no registration
# step either.
NODE_SUITE_GLOBS = (
    "configs/ai-docs/claude/tests/*.test.js",
    "configs/ai-docs/claude/scripts/tests/*.test.js",
    "configs/ai-docs/claude/hooks/tests/*.test.js",
    "configs/ai-docs/claude/skills/*/scripts/tests/*.test.js",
)

HEADROOM_GATE_RELATIVE_PATH = "configs/ai-docs/claude/scripts/check-machine-headroom.sh"

# The gate itself failed to run, not a verdict it reported.
GATE_UNAVAILABLE_STATUS = 2
GATE_NOT_EXECUTABLE_STATUS = 126


def write_stdout_bytes(data):
    # Flushing first keeps the bytes in order with the
    # text lines printed before them.
    sys.stdout.flush()
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def run_headroom_gate(headroom_gate):
    """Return (exit status, stdout bytes) of the gate; stderr passes through.

    stdin comes from /dev/null for the same reason every suite's does: the
    caller's stdin may never close, so a gate that reads it would hang the
    run before any suite starts.
    """
    if not os.access(headroom_gate, os.X_OK):
        return GATE_UNAVAILABLE_STATUS, b""
    try:
        completed = subprocess.run(
            [headroom_gate], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE
        )
    except OSError as error:
        print(f"run-tests.py: {headroom_gate}: {error.strerror}", file=sys.stderr, flush=True)
        return GATE_NOT_EXECUTABLE_STATUS, b""
    return completed.returncode, completed.stdout


def refuse_to_run(headroom_gate, gate_stdout):
    # Trailing newlines are stripped as shell command
    # substitution does, so the line reprints with one.
    gate_line = gate_stdout.rstrip(b"\n")
    if gate_line:
        write_stdout_bytes(gate_line + b"\n")
    print(
        f"run-tests.py: machine headroom check failed ({headroom_gate}) "
        "- the suites did NOT run",
        file=sys.stderr,
        flush=True,
    )
    return GATE_UNAVAILABLE_STATUS


@dataclass
class Tally:
    """Shared by every leg, so all report through the same counters, PASS/FAIL
    line, and failure-replay list rather than near-identical bookkeeping
    blocks drifting apart."""

    pass_count: int = 0
    failures: list = field(default_factory=list)

    def record(self, suite, log_file, passed):
        if passed:
            self.pass_count += 1
        else:
            self.failures.append((suite, log_file))
        print(f"{'PASS' if passed else 'FAIL'}  {suite}", flush=True)


def run_into_log(command, log_file):
    """Run command with stdin from /dev/null, output to log_file; True on exit 0.

    The caller's stdin may never close (a Claude Bash tool socket), so any
    stray stdin read inside a suite would hang this run indefinitely.
    A missing executable fails loudly in the log instead of reading as a
    pass: skipping it would reopen the gap this fold-in closes.
    """
    with open(log_file, "wb") as log:
        if shutil.which(command[0]) is None:
            log.write(f"{command[0]}: command not found\n".encode())
            return False
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        except OSError as error:
            log.write(f"{command[0]}: {error.strerror}\n".encode())
            return False
    return completed.returncode == 0


def discover_suites(patterns):
    # sorted() because glob returns directory order where
    # a shell sorts. The isfile guard drops an unmatched
    # glob's literal text, so zero matches is an empty
    # leg, not a failure.
    for pattern in patterns:
        for match in sorted(glob.glob(pattern)):
            if os.path.isfile(match):
                yield match


def run_all_suites(log_dir):
    tally = Tally()
    entries = [(suite, ["bash", suite]) for suite in discover_suites(BASH_SUITE_GLOBS)]

    # One entry per node file, unlike the single pytest
    # entry below: pytest.ini is itself the discovery
    # mechanism, while here the glob is.
    #
    # So each FAIL line names a path a human re-runs
    # verbatim as `node --test <path>`.
    entries += [
        (suite, ["node", "--test", suite]) for suite in discover_suites(NODE_SUITE_GLOBS)
    ]

    # pytest.ini at the repo root collects every python
    # suite from one bare `pytest` invocation, so it runs
    # as one more suite and its failures replay like a
    # bash suite's.
    entries.append(("pytest", ["pytest"]))

    for index, (suite, command) in enumerate(entries, start=1):
        # Named by index, not by the suite path: two trees
        # can hold a suite of the same name, and
        # flattening the path would collide their logs.
        log_file = os.path.join(log_dir, f"{index}.log")
        tally.record(suite, log_file, run_into_log(command, log_file))
    return tally


def replay_failures(tally):
    # A bare FAIL line names the suite but not the
    # assertion, forcing a second run by hand to learn
    # what broke. Replaying each failing log closes that.
    for suite, log_file in tally.failures:
        print(f"\n===== {suite} =====", flush=True)
        with open(log_file, "rb") as log:
            write_stdout_bytes(log.read())

    print(f"\n{tally.pass_count} passed, {len(tally.failures)} failed", flush=True)


def main():
    # Anchored on this script's own directory, not the
    # caller's, so the globs resolve the same from any
    # subdirectory. Not resolved through symlinks.
    repo_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_root)

    # Pre-flight headroom gate, not a lock.
    #
    # Five sessions sharing this checkout once launched five
    # concurrent runs, the oldest 7m54s in, and starved each
    # other for CPU.
    #
    # A profile of one full run later showed it averages only
    # ~0.47 cores (48.6s user + 63.1s sys CPU over 237s
    # wall-clock on a 12-core machine) - light runs weren't
    # the cause, the sessions' own separate load was.
    #
    # A gate that refuses to start on an already-busy machine
    # addresses that without serializing every run behind a
    # lock two callers might not need at all.
    #
    # Known gap: check-machine-headroom.sh reads the 1-minute
    # load average, which lags a command that started seconds
    # ago. Two runs launched in the same instant can both read
    # the same stale load and both get GO.
    #
    # Only concurrency *correctness* - never letting two runs
    # execute their suites at the same time - would need a
    # lock back. This gate only protects a machine that is
    # already under load when a run starts.
    headroom_gate = os.path.join(repo_root, HEADROOM_GATE_RELATIVE_PATH)
    gate_status, gate_stdout = run_headroom_gate(headroom_gate)
    if gate_status != 0:
        return refuse_to_run(headroom_gate, gate_stdout)

    # The temp dir is removed on every exit path: SIGTERM
    # becomes a SystemExit and Ctrl-C a KeyboardInterrupt,
    # both unwinding through the context manager.
    with tempfile.TemporaryDirectory() as log_dir:
        signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
        try:
            tally = run_all_suites(log_dir)
            replay_failures(tally)
        except KeyboardInterrupt:
            return 130
    return 1 if tally.failures else 0


if __name__ == "__main__":
    sys.exit(main())
