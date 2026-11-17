"""The soft mutation metric for Python changed lines.

mutmut runs one file at a time under the same deadline as the
JS/TS half. Each mutant's verdict is saved as it finishes, so a
killed run keeps what it recorded and lists the rest as not run.
"""

import ast
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, NamedTuple

from quality_metrics.deadline import run_until
from quality_metrics.cannot_run import cannot_run_ask, cannot_run_record
from quality_metrics.mutation import NOT_RUN_LABEL
from quality_metrics.tools import ToolError, run_command

MUTMUT_VERSION = "3.8.1"
MUTMUT_COMMAND = [
    "uv", "run", "--with", f"mutmut=={MUTMUT_VERSION}", "--with", "pytest",
    "--with", "pyyaml", "--with", "pytest-xdist", "--", "mutmut",
]

CANNOT_RUN_STATUS = "mutmut could not run"

# mutmut names no mutator, so every record carries this one.
MUTATOR = "mutmut"

# mutmut's per-mutant statuses by what they mean for the metric.
SURVIVED_STATUSES = {"survived": "survived", "no tests": "no coverage"}
KILLED_STATUSES = ("killed", "timeout", "segfault", "caught by type check")
NOT_RUN_STATUSES = ("not checked", "check was interrupted by user")

RESULT_LINE = re.compile(r"^\s+(\S+): (.+?)\s*$")
HUNK_HEADER = re.compile(r"^@@ -(\d+)")

# A function's mutant is `x_name__mutmut_3`, a method's is
# `xǁClassǁname__mutmut_3`.
MUTANT_FUNCTION = re.compile(r"^x(?:_|ǁ[^ǁ]+ǁ)(.+)__mutmut_\d+$")


@dataclass(frozen=True)
class PythonBatchResult:
    """One file's mutants: killed count, surviving-mutant
    records, the changed ranges never run, and whether the
    deadline killed mutmut."""

    killed: int
    survivors: list
    not_run: list = field(default_factory=list)
    is_deadline_hit: bool = False


def _read_results(tree):
    result = run_command([*MUTMUT_COMMAND, "results", "--all", "True"], cwd=tree)
    if result.returncode != 0:
        raise ToolError(f"mutmut results failed: {result.stderr.strip()}")
    return result.stdout


def _show_mutant(tree, name):
    result = run_command([*MUTMUT_COMMAND, "show", name], cwd=tree)
    if result.returncode != 0:
        raise ToolError(f"mutmut show {name} failed: {result.stderr.strip()}")
    return result.stdout


class MutmutTools(NamedTuple):
    """The three outside calls a batch makes, which tests
    replace."""

    run: Callable = run_until
    results: Callable = _read_results
    show: Callable = _show_mutant


def module_name(path):
    """The dotted module mutmut names mutants after."""
    return path.removesuffix(".py").replace("/", ".")


def touched_functions(source, ranges):
    """`{function name: (first line, last line)}` for functions
    overlapping a changed range."""
    touched = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(start <= node.end_lineno and node.lineno <= end for start, end in ranges):
            touched[node.name] = (node.lineno, node.end_lineno)
    return touched


def _clipped_ranges(span, ranges):
    first, last = span
    return [
        (max(start, first), min(end, last))
        for start, end in ranges if start <= last and first <= end
    ]


def parse_results(text, module):
    """`[(function name, mutant name, status)]` for `module`'s
    mutants in `mutmut results --all True` output."""
    mutants = []
    for line in text.splitlines():
        match = RESULT_LINE.match(line)
        if not match or not match.group(1).startswith(f"{module}."):
            continue
        key = match.group(1).removeprefix(f"{module}.")
        function = MUTANT_FUNCTION.match(key)
        if function:
            mutants.append((function.group(1), match.group(1), match.group(2)))
    return mutants


def parse_show(text):
    """`(line, replacement)` of the one changed line in
    `mutmut show` output, or None when it has no diff."""
    old_line = None
    replacement = None
    changed_line = None
    for text_line in text.splitlines():
        header = HUNK_HEADER.match(text_line)
        if header:
            old_line = int(header.group(1)) - 1
        elif old_line is None:
            continue
        elif text_line.startswith("+"):
            replacement = text_line[1:].strip()
        elif text_line.startswith("-"):
            old_line += 1
            changed_line = old_line
        else:
            old_line += 1
    if replacement is None or changed_line is None:
        return None
    return changed_line, replacement


def _survivor_record(path, line, replacement, status):
    return {
        "file": path, "line": line, "metric": "mutation", "value": 1,
        "limit": 0, "scope": "file", "mutator": MUTATOR,
        "replacement": replacement, "status": status,
    }


def _is_on_changed_line(line, ranges):
    return any(start <= line <= end for start, end in ranges)


def _mutmut_patterns(module, functions):
    return [f"{module}.x*{name}__mutmut_*" for name in functions]


def _undecided_functions(functions, mutants, is_killed):
    """Functions whose mutants were not all decided.

    After a kill, a function with no listed mutant is undecided.
    """
    listed = {function for function, _name, _status in mutants}
    undecided = {function for function, _name, status in mutants if status in NOT_RUN_STATUSES}
    if is_killed:
        undecided |= set(functions) - listed
    return undecided


def _verdicts(path, ranges, mutants, tools, tree):
    """`(killed count, survivors)` of the decided mutants on the
    changed lines."""
    killed, survivors = 0, []
    for _function, name, status in mutants:
        if status not in KILLED_STATUSES and status not in SURVIVED_STATUSES:
            continue
        shown = parse_show(tools.show(tree, name))
        if shown is None or not _is_on_changed_line(shown[0], ranges):
            continue
        if status in KILLED_STATUSES:
            killed += 1
        else:
            survivors.append(_survivor_record(path, shown[0], shown[1], SURVIVED_STATUSES[status]))
    return killed, survivors


def _results_after_run(tools, tree, is_killed):
    try:
        return tools.results(tree)
    except ToolError:
        if is_killed:
            return ""
        raise


def run_mutmut_batch(tree, path, ranges, deadline, tools=MutmutTools()):
    """Mutate the functions touching one file's changed ranges.

    A run the deadline killed still returns what mutmut saved,
    with the undecided functions' changed ranges as not run.
    Raises a ToolError when mutmut failed, quoting its output
    when it printed any.
    """
    functions = touched_functions((Path(tree) / path).read_text(), ranges)
    if not functions:
        return PythonBatchResult(killed=0, survivors=[])
    module = module_name(path)
    command = [*MUTMUT_COMMAND, "run", *_mutmut_patterns(module, functions)]
    outcome = tools.run(command, deadline, tree, None)
    if not outcome.killed and outcome.returncode != 0:
        output = (outcome.stdout + outcome.stderr).strip()
        if not output:
            raise ToolError(f"mutmut crashed with no output on {path}")
        raise ToolError(output)
    mutants = [
        mutant for mutant in parse_results(_results_after_run(tools, tree, outcome.killed), module)
        if mutant[0] in functions
    ]
    killed, survivors = _verdicts(path, ranges, mutants, tools, tree)
    undecided = _undecided_functions(functions, mutants, outcome.killed)
    not_run = [r for name in sorted(undecided) for r in _clipped_ranges(functions[name], ranges)]
    return PythonBatchResult(killed, survivors, not_run, outcome.killed)


def _not_run_records(path, ranges):
    return [
        {"file": path, "lines": f"{start}-{end}", "label": NOT_RUN_LABEL}
        for start, end in ranges
    ]


def measure_python_mutation(tree, changed, deadline, tools=MutmutTools()):
    """Surviving mutants, not-run ranges, a summary and any asks
    for the changed Python files; `changed` maps a path to its
    changed line ranges.

    The first batch the deadline killed, and every file after
    it, lists its ranges as not run. A file mutmut cannot run on
    gets one flagged pessimistic record, and the run gets one
    ask.
    """
    survivors, not_run, killed = [], [], 0
    failed_paths, last_error = [], None
    paths = sorted(changed)
    for position, path in enumerate(paths):
        if time.monotonic() >= deadline:
            not_run.extend(_not_run_after(paths[position:], changed))
            break
        try:
            batch = run_mutmut_batch(tree, path, changed[path], deadline, tools)
        except ToolError as error:
            survivors.append(cannot_run_record(path, changed[path], CANNOT_RUN_STATUS))
            failed_paths.append(path)
            last_error = error
            continue
        killed += batch.killed
        survivors.extend(batch.survivors)
        not_run.extend(_not_run_records(path, batch.not_run))
        if batch.is_deadline_hit:
            not_run.extend(_not_run_after(paths[position + 1:], changed))
            break
    asks = [cannot_run_ask("mutmut", failed_paths, last_error)] if failed_paths else []
    summary = {"killed": killed, "survived": len(survivors), "not_run_ranges": len(not_run)}
    return {
        "surviving_mutants": survivors, "mutants_not_run": not_run,
        "mutation_summary": summary, "asks": asks,
    }


def _not_run_after(paths, changed):
    return [record for path in paths for record in _not_run_records(path, changed[path])]
