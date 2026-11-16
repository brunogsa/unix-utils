"""Measures each function's nesting, parameters and complexity.

lizard reads every language here except Bash, whose function syntax it
misreads (complexity 5 against a hand count of 8, and it misses
`function name {}`). shellmetrics reads Bash instead, with shfmt
supplying the end line shellmetrics lacks.
"""

import csv
import io
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Optional

from quality_metrics.tools import (
    SHELLMETRICS_COMPLEXITY,
    SHELLMETRICS_LLOC,
    SHELLMETRICS_NAME,
    SHELLMETRICS_PSEUDO_FUNCTIONS,
    SHELLMETRICS_START,
    ToolError,
    run_tool,
    shellmetrics_rows,
)

NESTING_LIMIT = 3
PARAMETER_LIMIT = 5

# Sonar's rule S3776 uses 15 as its default limit, and so does
# Biome's noExcessiveCognitiveComplexity.
COGNITIVE_COMPLEXITY_LIMIT = 15

DISPLAY_STEP = Decimal("0.01")

BASH = "bash"

# Columns of `lizard --csv -E nd -E cognitive`; an extension's
# column follows the order the -E flags name them in.
LIZARD_NLOC, LIZARD_COMPLEXITY, LIZARD_PARAMETERS = 0, 1, 3
LIZARD_NAME, LIZARD_START, LIZARD_END, LIZARD_NESTING = 7, 9, 10, 11
LIZARD_COGNITIVE = 12

# The node type shfmt `--to-json` gives a function definition.
SHFMT_FUNCTION_NODE = "FuncDecl"


@dataclass(frozen=True)
class FunctionMeasure:
    """One function's measures; a field the tool cannot read is None."""

    name: str
    start: int
    end: int
    nloc: int
    complexity: int
    nesting: Optional[int]
    parameters: Optional[int]
    cognitive_complexity: Optional[int] = None


class FunctionToolError(ToolError):
    """A global function tool is missing, crashed or timed out twice."""

    def __init__(self, tool, reason):
        super().__init__(reason)
        self.tool = tool


def _run_function_tool(policy, command, input_text=None):
    """The tool's stdout, run under `policy`'s timeout when given.

    Any ToolError, a timeout twice included, is re-raised as a
    FunctionToolError naming the tool, so a caller can ask about it.
    """
    try:
        if policy is None:
            return run_tool(command, input_text)
        return policy.run(lambda timeout: run_tool(command, input_text, timeout=timeout))
    except ToolError as error:
        raise FunctionToolError(command[0], str(error)) from error


def measure_functions(path, language, policy=None):
    if language == BASH:
        return _measure_bash_functions(path, policy)
    return _measure_functions_with_lizard(path, policy)


def touched_functions(target):
    functions = measure_functions(target.path, target.language, target.tool_policy)
    return [
        function for function in functions
        if target.touches(function.start, function.end)
    ]


def measure(target, metrics):
    """Measure nesting, parameters and cognitive complexity.

    Each touched function gets one record per requested metric.
    """
    limits = {
        "nesting": NESTING_LIMIT,
        "parameters": PARAMETER_LIMIT,
        "cognitive_complexity": COGNITIVE_COMPLEXITY_LIMIT,
    }
    results = []
    for function in touched_functions(target):
        for metric in metrics:
            value = getattr(function, metric)
            if value is None:
                raise ToolError(
                    f"{target.language} cannot measure {metric}; "
                    f"drop it from the {target.language} metrics in the declaration"
                )
            results.append(measurement(
                target, metric, value, limits[metric], function
            ))
    return results


def is_over_limit(item):
    """A record flags past its limit, at it when it says so (CRAP),
    or under it when it says so (coverage).

    The comparison reads the unrounded value; display_value is for
    showing it only. A record with no value, such as coverage
    not applicable, is neither passed nor flagged.
    """
    if item["value"] is None:
        return False
    if item.get("flagged_below_limit"):
        return item["value"] < item["limit"]
    if item.get("flagged_at_limit"):
        return item["value"] >= item["limit"]
    return item["value"] > item["limit"]


def display_value(item):
    """The record's value cut to 2 decimals, never rounded up.

    Rounding would show 7.996 as 8.00 beside a record that passed.
    Trailing zeros drop, so 4 shows as 4 and 8.90 as 8.9.
    """
    cut = Decimal(str(item["value"])).quantize(DISPLAY_STEP, ROUND_DOWN)
    return str(cut).rstrip("0").rstrip(".")


def measurement(target, metric, value, limit, function=None):
    """One report record; a record with no function is file-scoped."""
    return {
        "file": str(target.path),
        "function": function.name if function else None,
        "scope": "function" if function else "file",
        "metric": metric,
        "value": value,
        "limit": limit,
        "line": function.start if function else None,
    }


def _measure_functions_with_lizard(path, policy):
    output = _run_function_tool(policy, ["lizard", "--csv", "-E", "nd", "-E", "cognitive", str(path)]
    )
    return [
        FunctionMeasure(
            name=row[LIZARD_NAME],
            start=int(row[LIZARD_START]),
            end=int(row[LIZARD_END]),
            nloc=int(row[LIZARD_NLOC]),
            complexity=int(row[LIZARD_COMPLEXITY]),
            nesting=int(row[LIZARD_NESTING]),
            parameters=int(row[LIZARD_PARAMETERS]),
            cognitive_complexity=int(row[LIZARD_COGNITIVE]),
        )
        for row in csv.reader(io.StringIO(output))
    ]


def _measure_bash_functions(path, policy):
    end_lines = _bash_function_end_lines(path, policy)
    functions = []
    rows = shellmetrics_rows(path, run=lambda command: _run_function_tool(policy, command))
    for row in rows:
        name, start = row[SHELLMETRICS_NAME], int(row[SHELLMETRICS_START])
        if name in SHELLMETRICS_PSEUDO_FUNCTIONS:
            continue
        if (name, start) not in end_lines:
            raise ToolError(f"shfmt found no function {name} at line {start} of {path}")
        functions.append(FunctionMeasure(
            name=name,
            start=start,
            end=end_lines[(name, start)],
            nloc=int(row[SHELLMETRICS_LLOC]),
            complexity=int(row[SHELLMETRICS_COMPLEXITY]),
            nesting=None,
            parameters=None,
            cognitive_complexity=None,
        ))
    return functions


def _bash_function_end_lines(path, policy):
    """Map (name, start line) of each Bash function to its end line.

    shellmetrics gives no end line, so shfmt's syntax tree supplies it:
    a parser knows where a function ends when a heredoc or a quoted
    brace holds a `}`.
    """
    tree = json.loads(_run_function_tool(
        policy, ["shfmt", "--to-json", "-ln=bash"], Path(path).read_text()
    ))
    return {
        (node["Name"]["Value"], node["Pos"]["Line"]): node["End"]["Line"]
        for node in _function_declarations(tree)
    }


def _function_declarations(node):
    if isinstance(node, dict):
        if node.get("Type") == SHFMT_FUNCTION_NODE:
            yield node
        for child in node.values():
            yield from _function_declarations(child)
    elif isinstance(node, list):
        for child in node:
            yield from _function_declarations(child)
