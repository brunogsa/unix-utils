"""What a mutation tool that could not run leaves in the report.

The file scores pessimistically and the run gets one ask per
tool, so a crashed tool never loses the other metrics.
"""

import re

from quality_metrics.deferred import DEFERRED_LABEL

# Each mutation record counts one surviving or unchecked mutant
# against a limit of zero, so every such record is over it. It
# lives here, not in mutation.py, because mutation.py imports
# this module.
MUTATION_LIMIT = 0


def cannot_run_record(path, ranges, status):
    """One flagged pessimistic record for a file whose mutation
    tool failed."""
    return {
        "file": path, "line": ranges[0][0], "metric": "mutation", "value": 1,
        "limit": MUTATION_LIMIT, "scope": "file", "mutator": None, "replacement": None,
        "status": status, "pessimistic": True, "label": DEFERRED_LABEL,
    }


ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ERROR_LOG_LEVEL = re.compile(r"\bERROR\b")


def _quoted_line(message):
    """The line of `message` that names the error: the first
    Stryker ERROR-level log line, else the first non-empty line,
    with ANSI colour codes removed."""
    lines = [ANSI_ESCAPE.sub("", line).strip() for line in message.splitlines()]
    lines = [line for line in lines if line]
    error_lines = [line for line in lines if ERROR_LOG_LEVEL.search(line)]
    return (error_lines or lines or ["no output"])[0]


def cannot_run_ask(tool, paths, error):
    """The one ask a tool's failed files raise, quoting the line
    of the last failure that names the error."""
    return {
        "tool": tool, "metric": "mutation",
        "reason": f"{tool} could not run on {', '.join(paths)}: {_quoted_line(str(error))}",
        "choices": ["fix now", "defer"],
    }
