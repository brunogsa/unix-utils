"""Measures each function's nesting, parameters and complexity.

lizard reads every language here except Bash, whose function syntax it
misreads (complexity 5 against a hand count of 8, and it misses
`function name {}`). shellmetrics reads Bash instead.
"""

import csv
import io
import subprocess
from dataclasses import dataclass

NESTING_LIMIT = 3
PARAMETER_LIMIT = 5

BASH = "bash"

# Columns of `lizard --csv -E nd`.
LIZARD_NLOC, LIZARD_COMPLEXITY, LIZARD_PARAMETERS = 0, 1, 3
LIZARD_NAME, LIZARD_START, LIZARD_END, LIZARD_NESTING = 7, 9, 10, 11

# Columns of `shellmetrics --csv`; its pseudo-rows are not
# functions.
SHELLMETRICS_NAME, SHELLMETRICS_START = 1, 2
SHELLMETRICS_LLOC, SHELLMETRICS_COMPLEXITY = 3, 4
SHELLMETRICS_PSEUDO_FUNCTIONS = ("<begin>", "<main>", "<end>")


class ToolError(RuntimeError):
    """A measuring tool is missing or failed on a file."""


@dataclass(frozen=True)
class FunctionMeasure:
    """One function's measures; a field the tool cannot read is None."""

    name: str
    start: int
    end: object
    nloc: int
    complexity: int
    nesting: object
    parameters: object


def measure_functions(path, language):
    if language == BASH:
        return _measure_bash_functions(path)
    return _measure_functions_with_lizard(path)


def measure(target, metrics):
    """Measure the nesting and parameters of every touched function."""
    limits = {"nesting": NESTING_LIMIT, "parameters": PARAMETER_LIMIT}
    results = []
    for function in measure_functions(target.path, target.language):
        if not target.touches(function.start, function.end):
            continue
        for metric in metrics:
            results.append(function_measurement(
                target, function, metric, getattr(function, metric), limits[metric]
            ))
    return results


def function_measurement(target, function, metric, value, limit):
    return {
        "file": str(target.path),
        "function": function.name,
        "scope": "function",
        "metric": metric,
        "value": value,
        "limit": limit,
        "line": function.start,
    }


def run_tool(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise ToolError(f"'{command[0]}' is not installed; run install.sh") from error
    if result.returncode != 0:
        raise ToolError(f"{' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout


def _measure_functions_with_lizard(path):
    output = run_tool(["lizard", "--csv", "-E", "nd", str(path)])
    return [
        FunctionMeasure(
            name=row[LIZARD_NAME],
            start=int(row[LIZARD_START]),
            end=int(row[LIZARD_END]),
            nloc=int(row[LIZARD_NLOC]),
            complexity=int(row[LIZARD_COMPLEXITY]),
            nesting=int(row[LIZARD_NESTING]),
            parameters=int(row[LIZARD_PARAMETERS]),
        )
        for row in csv.reader(io.StringIO(output))
    ]


def _measure_bash_functions(path):
    output = run_tool(["shellmetrics", "--csv", str(path)])
    rows = list(csv.reader(io.StringIO(output)))[1:]
    return [
        FunctionMeasure(
            name=row[SHELLMETRICS_NAME],
            start=int(row[SHELLMETRICS_START]),
            end=None,
            nloc=int(row[SHELLMETRICS_LLOC]),
            complexity=int(row[SHELLMETRICS_COMPLEXITY]),
            nesting=None,
            parameters=None,
        )
        for row in rows
        if row[SHELLMETRICS_NAME] not in SHELLMETRICS_PSEUDO_FUNCTIONS
    ]
