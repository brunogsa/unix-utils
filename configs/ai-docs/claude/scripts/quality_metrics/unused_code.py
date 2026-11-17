"""Counts the unused imports and variables in one file.

Each language's tool runs with the repo's own config and inline
disable comments bypassed, so a repo cannot hide unused code.
Go has no entry: its compiler already rejects unused code.
"""

import json
import re
from pathlib import Path

from quality_metrics.functions import measurement
from quality_metrics.tools import ToolError, run_command

METRIC = "unused_code"
NODE_TOOLS = Path(__file__).resolve().parent / "node_tools"
ESLINT = NODE_TOOLS / "node_modules" / ".bin" / "eslint"
TS_ESLINT_CONFIG = NODE_TOOLS / "eslint.config.mjs"
JS_ESLINT_CONFIG = NODE_TOOLS / "eslint.js.config.mjs"
RUFF = "ruff@0.17.5"
RUFF_RULES = ("F401", "F841")

# The first quoted word of a tool's message names the variable.
QUOTED_NAME = re.compile(r"[`'\"]([^`'\"]+)[`'\"]")
FIRST_WORD = re.compile(r"(\S+)")


def _name_in(message, pattern=QUOTED_NAME):
    found = pattern.search(message)
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
        "--select", ",".join(RUFF_RULES), "--output-format", "json", str(path),
    ]
    entries = _json_output(command)
    for entry in entries:
        # Only the selected rules are findings; a syntax error
        # comes back as another code, or none in older ruff.
        if entry["code"] not in RUFF_RULES:
            raise ToolError(f"ruff could not parse {path}: {entry['message']}")
    return [
        {"line": entry["location"]["row"], "rule": entry["code"],
         "name": _name_in(entry["message"])}
        for entry in entries
    ]


def _eslint_findings(command):
    """Run eslint from the filesystem root, so its default
    ignore of node_modules sees the file's whole path."""
    findings = []
    for file_result in _json_output(command, cwd="/"):
        for message in file_result["messages"]:
            if message["ruleId"] is None:
                raise ToolError(f"eslint could not lint the file: {message['message']}")
            findings.append({
                "line": message["line"], "rule": message["ruleId"],
                "name": _name_in(message["message"]),
            })
    return findings


def _javascript_findings(path):
    # Absolute, because eslint runs from / and a relative path
    # would resolve there instead of against the caller's cwd.
    return _eslint_findings([
        str(ESLINT), "-c", str(JS_ESLINT_CONFIG), "--no-inline-config",
        "-f", "json", str(Path(path).absolute()),
    ])


def _typescript_findings(path):
    return _eslint_findings([
        str(ESLINT), "-c", str(TS_ESLINT_CONFIG), "--no-inline-config",
        "-f", "json", str(Path(path).absolute()),
    ])


def _bash_findings(path):
    command = [
        "shellcheck", "--norc", "--include=SC2034", "-f", "json", str(path),
    ]
    return [
        {"line": entry["line"], "rule": f"SC{entry['code']}",
         "name": _name_in(entry["message"], FIRST_WORD)}
        for entry in _json_output(command)
    ]


FINDERS = {
    "python": _ruff_findings,
    "js": _javascript_findings,
    "ts": _typescript_findings,
    "bash": _bash_findings,
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
