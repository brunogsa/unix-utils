"""Runs the external measuring tools and reads shellmetrics
output."""

import csv
import io
import os
import signal
import subprocess

# Columns of `shellmetrics --csv`; its pseudo-rows are not
# functions.
SHELLMETRICS_NAME, SHELLMETRICS_START = 1, 2
SHELLMETRICS_LLOC, SHELLMETRICS_COMPLEXITY = 3, 4
SHELLMETRICS_PSEUDO_FUNCTIONS = ("<begin>", "<main>", "<end>")


class ToolError(RuntimeError):
    """A measuring tool is missing or failed on a file."""


def run_command(command, input_text=None, cwd=None, env=None, timeout=None):
    """Run a command and return its result whatever its exit
    code.

    Raises subprocess.TimeoutExpired once `timeout` seconds
    pass, after killing the command's whole process group: a
    test runner's workers outlive a kill of the runner alone.

    A binary or Latin-1 file must not crash the run, so bytes
    that are not UTF-8 decode to a replacement character.
    """
    try:
        process = subprocess.Popen(
            command, stdin=None if input_text is None else subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env,
            start_new_session=True,
        )
    except FileNotFoundError as error:
        raise ToolError(f"'{command[0]}' is not installed; run install.sh") from error
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except BaseException:
        _kill_process_group(process)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _kill_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_tool(command, input_text=None, cwd=None, timeout=None):
    """Run a command and return its stdout; raises ToolError on
    a non-zero exit."""
    result = run_command(command, input_text, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        raise ToolError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout


def shellmetrics_rows(path, run=run_tool):
    """shellmetrics' rows for a file; `run(command)` returns a
    command's stdout."""
    output = run(["shellmetrics", "--csv", str(path)])
    return list(csv.reader(io.StringIO(output)))[1:]


def bash_file_lloc(path, run=run_tool):
    """A Bash file's logical lines: its functions' plus the
    top-level script's; `run(command)` returns a command's
    stdout."""
    return sum(int(row[SHELLMETRICS_LLOC]) for row in shellmetrics_rows(path, run=run))
