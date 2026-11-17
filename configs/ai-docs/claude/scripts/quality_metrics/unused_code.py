"""Counts the unused imports and variables in one file.

Each language's tool runs with the repo's own config and inline
disable comments bypassed, so a repo cannot hide unused code.
Go has no entry: its compiler already rejects unused code.
"""

import json
import re

from quality_metrics.functions import measurement
from quality_metrics.tools import ToolError, run_command

METRIC = "unused_code"
RUFF = "ruff@0.17.5"

# The first quoted word of a tool's message names the variable.
QUOTED_NAME = re.compile(r"[`'\"]([^`'\"]+)[`'\"]")


def _name_in(message):
    found = QUOTED_NAME.search(message)
    return found.group(1) if found else message


def _json_output(command, cwd=None):
    """Parse a linter's JSON; a linter exits 1 when it finds
    something, so only unparsable output is a failure."""
    result = run_command(command, cwd=cwd)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ToolError(f"{' '.join(command)} gave no JSON: {detail}") from error


def _ruff_findings(path):
    command = [
        "uvx", RUFF, "check", "--isolated", "--ignore-noqa",
        "--select", "F401,F841", "--output-format", "json", str(path),
    ]
    return [
        {"line": entry["location"]["row"], "rule": entry["code"],
         "name": _name_in(entry["message"])}
        for entry in _json_output(command)
    ]


FINDERS = {
    "python": _ruff_findings,
}


def measure_unused_code(target):
    """The file's `unused_code` record, with each finding's
    line, rule and name; a language with no finder gives none.

    Raises ToolError when the tool is missing, crashes or skips
    the file.
    """
    finder = FINDERS.get(target.language)
    if finder is None:
        return []
    findings = finder(target.path)
    record = measurement(target, METRIC, len(findings), 0)
    record["findings"] = findings
    return [record]
