"""Chooses which tool measures a metric: the repo's own, or the global one.

A repo's own tool wins. With none, the global tool measures it
and the gap is a side-PR candidate.
"""

import json
import os
import re
from pathlib import Path

from quality_metrics.functions import FunctionMeasure, measurement
from quality_metrics.size import FUNCTION_LINES_LIMIT
from quality_metrics.tool_map import TOOL_MAP_DIR, LazyToolMap
from quality_metrics.tools import ToolError, run_command, run_tool

ESLINT_REPORT_EVERY_FUNCTION = "max-lines-per-function: [error, {max: 0}]"
ESLINT_LINE_COUNT = re.compile(r"^(?P<subject>.*?) has too many lines \((?P<lines>\d+)\)")

# The global tool measuring each metric when the repo has none.
GLOBAL_TOOLS = {
    "coverage": "coverage.py",
    "code_duplication": "jscpd",
    "test_duplication": "jscpd",
}


def lazy_tool_map_for(working_directory, rules, session_id, map_dir, base_ref):
    """The lazy tool map of the repo around `working_directory`.

    `base_ref` is required: a default of the branch head would let
    a tool configured only on the branch into the map.
    Returns None outside a git repo. Nothing is detected or written until a metric asks the map for
    its entry.
    """
    toplevel = run_command(["git", "-C", str(working_directory), "rev-parse", "--show-toplevel"])
    if toplevel.returncode != 0:
        return None
    repo = Path(toplevel.stdout.strip())
    base_sha = run_tool(["git", "-C", str(repo), "rev-parse", base_ref]).strip()
    return LazyToolMap(repo, base_sha, rules, session_id, map_dir)


def measure_function_size_with_repo_tool(target, repo):
    """Each touched function's line count, as the repo's eslint counts it.

    eslint is asked to report every function (a zero line allowance), so the
    repo's own `max-lines-per-function` never hides one; the harness limit
    then judges the counts. eslint exits 1 on those reports by design, so its
    exit code is not read.
    """
    result = run_command(
        ["eslint", "--format", "json", "--rule", ESLINT_REPORT_EVERY_FUNCTION, str(target.path)],
        cwd=repo, env=_repo_tool_env(repo),
    )
    try:
        reports = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ToolError(f"eslint gave no JSON report for {target.path}: {result.stderr.strip()}") from error
    records = []
    for report in reports:
        for message in report["messages"]:
            function = _function_from_eslint_message(message)
            if function is not None and target.touches(function.start, function.end):
                records.append(measurement(target, "size", function.nloc, FUNCTION_LINES_LIMIT, function))
    return records


def _repo_tool_env(repo):
    """The environment with the repo's local tool binaries first on PATH."""
    local_bin = Path(repo) / "node_modules" / ".bin"
    return {**os.environ, "PATH": f"{local_bin}{os.pathsep}{os.environ['PATH']}"}


def _function_from_eslint_message(message):
    if message.get("ruleId") != "max-lines-per-function":
        return None
    counted = ESLINT_LINE_COUNT.search(message["message"])
    if counted is None:
        return None
    name = re.search(r"'([^']*)'", counted.group("subject"))
    return FunctionMeasure(
        name=name.group(1) if name else counted.group("subject"),
        start=message["line"], end=message["endLine"], nloc=int(counted.group("lines")),
        complexity=0, nesting=None, parameters=None,
    )


def source_for(metric, tool_map):
    """Which tool measures `metric`, and the side-PR candidate if the repo lacks one.

    `tool_map` is None outside a git repo, where no repo tool can
    be missing, so there is no candidate.
    """
    if tool_map is not None:
        repo_tool = next(
            (tool for tool in tool_map.entry()["tools"] if tool["metric"] == metric), None
        )
        if repo_tool is not None:
            return {
                "metric": metric,
                "source": {"kind": "repo", "tool": repo_tool["tool"]},
                "side_pr_candidate": None,
            }
    gap = None if tool_map is None else f"no repo {metric.replace('_', ' ')} tool"
    return {
        "metric": metric,
        "source": {"kind": "global", "tool": GLOBAL_TOOLS[metric]},
        "side_pr_candidate": gap,
    }
