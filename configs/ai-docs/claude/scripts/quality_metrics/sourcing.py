"""Chooses which tool measures a metric: the repo's own, or the global one.

A repo's own tool wins. With none, the global tool measures it
and the gap is a side-PR candidate.
"""

import json
import os
import re
import tempfile
from pathlib import Path

from quality_metrics.coverage import coverage_measurement
from quality_metrics.crap import parse_lcov
from quality_metrics.failures import (
    TimeoutPolicy,
    ToolTimedOutTwice,
    ask_unless_deferred,
    deferred_coverage_measurement,
    session_can_ask,
)
from quality_metrics.functions import FunctionMeasure, measurement
from quality_metrics.size import FUNCTION_LINES_LIMIT
from quality_metrics.tool_map import LazyToolMap
from quality_metrics.tools import ToolError, run_command, run_tool

ESLINT_REPORT_EVERY_FUNCTION = "max-lines-per-function: [error, {max: 0}]"
ESLINT_LINE_COUNT = re.compile(r"^(?P<subject>.*?) has too many lines \((?P<lines>\d+)\)")

# How a repo tool exited, read from its output, in check order.
PASSED, UNCLASSIFIED = "passed", "unclassified"
FAILED_TESTS, CRASH = "failed_tests", "crash"
EXIT_CLASS_PATTERNS = (
    (FAILED_TESTS, re.compile(r"^Tests:.*\d+ failed", re.MULTILINE)),
    ("repo_threshold", re.compile(r"coverage threshold .* not met")),
    (CRASH, re.compile(r"^\s+at .+:\d+:\d+\)?$", re.MULTILINE)),
)

# Failures that are not exits of a finished run.
TIMEOUT, NO_COVERAGE_DATA = "timeout", "no_coverage_data"

# Exit classes whose measurements are valid.
MEASURING_EXIT_CLASSES = (PASSED, "repo_threshold")

# Why each failure sends the metric to the global tool, worded
# for the side-PR candidate.
FALL_THROUGH_REASONS = {
    CRASH: "crashed",
    TIMEOUT: "timed out twice",
    NO_COVERAGE_DATA: "wrote no coverage data",
    UNCLASSIFIED: "exited non-zero with no recognized cause",
}

REPO_COVERAGE_SOURCE = {"kind": "repo", "tool": "jest"}

# The global tool measuring each metric when the repo has none.
GLOBAL_TOOLS = {
    "coverage": "coverage.py",
    "code_duplication": "jscpd",
    "test_duplication": "jscpd",
}


class RepoToolFailure(ToolError):
    """A repo tool gave no measurement; `exit_class` says why."""

    def __init__(self, exit_class, detail):
        super().__init__(f"{exit_class}: {detail}")
        self.exit_class = exit_class


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


def measure_coverage(target, repo, measure_globally, policy=None):
    """Changed-line coverage, from the repo's jest or else the global tool.

    A repo tool that crashed, timed out twice or wrote no coverage data
    falls through to `measure_globally()`, and the repo gap is the side-PR
    candidate. Failing tests are a red build, never a tooling gap: nothing
    falls through. A failure of the global tool propagates as ToolError.
    `policy` is the TimeoutPolicy bounding each jest run.
    """
    try:
        outcome = _measure_coverage_under_timeout_policy(target, repo, policy or TimeoutPolicy())
    except RepoToolFailure as failure:
        if failure.exit_class == FAILED_TESTS:
            return {
                "source": REPO_COVERAGE_SOURCE, "exit_class": FAILED_TESTS, "red_build": True,
                "measurements": [], "side_pr_candidate": None,
            }
        return {
            "source": {"kind": "global", "tool": GLOBAL_TOOLS["coverage"]},
            "exit_class": failure.exit_class, "red_build": False,
            "measurements": measure_globally(),
            "side_pr_candidate": f"repo jest {FALL_THROUGH_REASONS[failure.exit_class]}",
        }
    return {**outcome, "source": REPO_COVERAGE_SOURCE, "red_build": False, "side_pr_candidate": None}


def measure_coverage_or_ask(target, repo, measure_globally, tool_map, policy=None, environ=None):
    """`measure_coverage` plus an `ask` for a global tool that cannot measure.

    A missing or crashing global tool, or a run that passes yet
    writes no coverage data, yields an ask and no measurements.
    Once the developer defers it (recorded in `tool_map`'s batch),
    the tool is not run again: coverage reads 0%, labelled
    pessimistic, and no second ask is emitted.
    When no session can ask (see `session_can_ask`, read from
    `environ`), a failure defers on the spot with no ask.
    """
    global_tool = GLOBAL_TOOLS["coverage"]
    global_failures = []

    def measure_globally_or_defer():
        if global_tool in tool_map.entry()["deferred"]:
            return [deferred_coverage_measurement(target)]
        try:
            measurements = measure_globally()
            failure = None if measurements else f"{global_tool} exited zero but wrote no coverage data"
        except ToolError as error:
            measurements, failure = [], str(error)
        if failure is None:
            return measurements
        if not session_can_ask(environ):
            return [deferred_coverage_measurement(target)]
        global_failures.append(failure)
        return []

    outcome = measure_coverage(target, repo, measure_globally_or_defer, policy)
    ask = None
    if global_failures:
        ask = ask_unless_deferred(tool_map, global_tool, "coverage", global_failures[0])
    return {**outcome, "ask": ask}


def _measure_coverage_under_timeout_policy(target, repo, policy):
    try:
        return policy.run(lambda timeout_seconds: measure_coverage_with_repo_tool(target, repo, timeout_seconds))
    except ToolTimedOutTwice as error:
        raise RepoToolFailure(TIMEOUT, str(error)) from error


def measure_coverage_with_repo_tool(target, repo, timeout_seconds=None):
    """Changed-line coverage from the repo's jest, with how jest exited.

    The coverage reads valid when jest passed or exited non-zero on the
    repo's own threshold: the harness judges the measured value against its
    own limit. Any other outcome raises RepoToolFailure naming its class.
    """
    with tempfile.TemporaryDirectory() as report_dir:
        result = run_command(
            ["jest", "--coverage", "--coverageReporters=lcov", f"--coverageDirectory={report_dir}"],
            cwd=repo, env=_repo_tool_env(repo), timeout=timeout_seconds,
        )
        exit_class = classify_exit(result)
        if exit_class not in MEASURING_EXIT_CLASSES:
            raise RepoToolFailure(exit_class, f"jest exited {result.returncode}: {result.stderr.strip()}")
        report = Path(report_dir) / "lcov.info"
        if not report.exists():
            raise RepoToolFailure(NO_COVERAGE_DATA, "jest wrote no lcov report")
        hits_by_file = parse_lcov(report.read_text())
    line_hits = hits_by_file.get(target.repo_path or str(Path(target.path).relative_to(repo)))
    return {"exit_class": exit_class, "measurements": [coverage_measurement(target, line_hits)]}


def classify_exit(result):
    """Name a repo tool's exit from its output; the exit code alone says too little.

    The first matching pattern wins, so failed tests rank above a
    threshold miss: a coverage figure from failing tests is not valid.
    """
    if result.returncode == 0:
        return PASSED
    output = result.stdout + result.stderr
    for exit_class, pattern in EXIT_CLASS_PATTERNS:
        if pattern.search(output):
            return exit_class
    return UNCLASSIFIED


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
