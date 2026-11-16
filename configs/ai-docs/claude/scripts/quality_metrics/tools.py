"""Runs the external measuring tools and reads shellmetrics output."""

import csv
import io
import subprocess

# Columns of `shellmetrics --csv`; its pseudo-rows are not
# functions.
SHELLMETRICS_NAME, SHELLMETRICS_START = 1, 2
SHELLMETRICS_LLOC, SHELLMETRICS_COMPLEXITY = 3, 4
SHELLMETRICS_PSEUDO_FUNCTIONS = ("<begin>", "<main>", "<end>")


class ToolError(RuntimeError):
    """A measuring tool is missing or failed on a file."""


def run_command(command, input_text=None, cwd=None, env=None, timeout=None):
    """Run a command and return its result whatever its exit code.

    Raises subprocess.TimeoutExpired once `timeout` seconds pass.
    """
    try:
        return subprocess.run(
            command, capture_output=True, text=True,
            input=input_text, cwd=cwd, env=env, timeout=timeout,
        )
    except FileNotFoundError as error:
        raise ToolError(f"'{command[0]}' is not installed; run install.sh") from error


def run_tool(command, input_text=None, cwd=None, timeout=None):
    """Run a command and return its stdout; raises ToolError on a non-zero exit."""
    result = run_command(command, input_text, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        raise ToolError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout


def shellmetrics_rows(path, run=run_tool):
    """shellmetrics' rows for a file; `run(command)` returns a command's stdout."""
    output = run(["shellmetrics", "--csv", str(path)])
    return list(csv.reader(io.StringIO(output)))[1:]


def bash_file_lloc(path):
    """A Bash file's logical lines: its functions' plus the top-level script's."""
    return sum(int(row[SHELLMETRICS_LLOC]) for row in shellmetrics_rows(path))
