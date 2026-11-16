"""Chooses which tool measures a metric: the repo's own, or the global one.

A repo's own tool wins. With none, the global tool measures it
and the gap is a side-PR candidate.
"""

import json
import os
import re
import tempfile
from pathlib import Path

from quality_metrics.coverage import coverage_measurement, coverage_record
from quality_metrics.crap import parse_lcov
from quality_metrics.dependencies import DEPENDENCY_CRUISER, GO_ARCH_LINT, IMPORT_LINTER
from quality_metrics.failures import (
    TimeoutPolicy,
    ToolTimedOutTwice,
    ask_or_defer,
    deferred_coverage_measurement,
)
from quality_metrics.functions import FunctionMeasure, measurement
from quality_metrics.gate_inputs import write_base_ref_configs
from quality_metrics.size import FUNCTION_LINES_LIMIT
from quality_metrics.tool_map import LazyToolMap
from quality_metrics.tools import ToolError, run_command, run_tool

# Blank and comment lines are skipped, so eslint counts as
# lizard's NLOC does. Rule options:
# https://eslint.org/docs/latest/rules/max-lines-per-function
ESLINT_REPORT_EVERY_FUNCTION = (
    "max-lines-per-function: "
    "[error, {max: 0, skipBlankLines: true, skipComments: true}]"
)
ESLINT_LINE_COUNT = re.compile(r"^(?P<subject>.*?) has too many lines \((?P<lines>\d+)\)")

# How a repo tool exited, read from its output, in check order.
PASSED, UNCLASSIFIED = "passed", "unclassified"
FAILED_TESTS, REPO_THRESHOLD, CRASH = "failed_tests", "repo_threshold", "crash"
EXIT_CLASS_PATTERNS = (
    (FAILED_TESTS, re.compile(r"^Tests:.*\d+ failed", re.MULTILINE)),
    (REPO_THRESHOLD, re.compile(r"coverage threshold .* not met")),
    (CRASH, re.compile(r"^\s+at .+:\d+:\d+\)?$", re.MULTILINE)),
)

# Failures that are not exits of a finished run.
TIMEOUT, WROTE_NO_COVERAGE = "timeout", "no_coverage_data"

# Exit classes whose measurements are valid.
MEASURING_EXIT_CLASSES = (PASSED, REPO_THRESHOLD)

# Why each failure sends the metric to the global tool, worded
# for the side-PR candidate.
FALL_THROUGH_REASONS = {
    CRASH: "crashed",
    TIMEOUT: "timed out twice",
    WROTE_NO_COVERAGE: "wrote no coverage data",
    UNCLASSIFIED: "exited non-zero with no recognized cause",
}

JEST = "jest"
REPO_COVERAGE_SOURCE = {"kind": "repo", "tool": JEST}

LIZARD, SHELLMETRICS, LINE_COUNT = "lizard", "shellmetrics", "line count"
COVERAGE_PY, C8, GCOV2LCOV = "coverage.py", "c8", "gcov2lcov"
JSCPD = "jscpd"
LIZARD_LANGUAGES = ("js", "ts", "python", "go")
ALL_LANGUAGES = (*LIZARD_LANGUAGES, "bash", "html", "css")

# The global tool each metric module runs per language, when the
# repo has none. A pair missing here has no global tool.
GLOBAL_TOOLS = {
    "size": {
        **dict.fromkeys(LIZARD_LANGUAGES, LIZARD),
        "bash": SHELLMETRICS,
        **dict.fromkeys(("html", "css"), LINE_COUNT),
    },
    "complexity": {**dict.fromkeys(LIZARD_LANGUAGES, LIZARD), "bash": SHELLMETRICS},
    "nesting": dict.fromkeys(LIZARD_LANGUAGES, LIZARD),
    "parameters": dict.fromkeys(LIZARD_LANGUAGES, LIZARD),
    "coverage": {"python": COVERAGE_PY, "js": C8, "ts": C8, "go": GCOV2LCOV},
    "code_duplication": dict.fromkeys(ALL_LANGUAGES, JSCPD),
    "test_duplication": dict.fromkeys(ALL_LANGUAGES, JSCPD),
    "dependency_direction": {
        "js": DEPENDENCY_CRUISER, "ts": DEPENDENCY_CRUISER,
        "python": IMPORT_LINTER, "go": GO_ARCH_LINT,
    },
}


class RepoToolFailure(ToolError):
    """A repo tool gave no measurement; `exit_class` says why."""

    def __init__(self, exit_class, detail):
        super().__init__(f"{exit_class}: {detail}")
        self.exit_class = exit_class


class NoGlobalToolError(ToolError):
    """No global tool measures `metric` for `language`."""

    def __init__(self, metric, language):
        super().__init__(f"not measured: no global {metric} tool for {language}")


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


def measure_coverage(target, repo, measure_globally, tool_map, policy=None, base_ref=None):
    """Changed-line coverage, from the repo's own tool or else the global one.

    The repo tool comes from `tool_map`. Only jest has a runner here:
    another repo tool (pytest-cov) or none sends the measurement to
    `measure_globally()`. A repo with its own tool is no gap, so only
    a repo with none is a side-PR candidate.

    A jest that crashed, timed out twice or wrote no coverage data
    falls through to `measure_globally()`, and the repo gap is the side-PR
    candidate. Failing tests are a red build, never a tooling gap: nothing
    falls through. A failure of the global tool propagates as ToolError.
    `policy` is the TimeoutPolicy bounding each jest run.
    """
    choice = source_for("coverage", tool_map, target.language)
    if choice["source"].get("tool") != JEST:
        return {
            "source": {"kind": "global", "tool": global_tool_for("coverage", target.language)},
            "exit_class": None, "red_build": False,
            "measurements": measure_globally(),
            "side_pr_candidate": choice["side_pr_candidate"],
        }
    try:
        outcome = _measure_coverage_under_timeout_policy(target, repo, policy or TimeoutPolicy(), base_ref)
    except RepoToolFailure as failure:
        if failure.exit_class == FAILED_TESTS:
            return {
                "source": REPO_COVERAGE_SOURCE, "exit_class": FAILED_TESTS, "red_build": True,
                "measurements": [{**coverage_record(target, 0), "pessimistic": True}],
                "side_pr_candidate": None,
            }
        return {
            "source": {"kind": "global", "tool": global_tool_for("coverage", target.language)},
            "exit_class": failure.exit_class, "red_build": False,
            "measurements": measure_globally(),
            "side_pr_candidate": f"repo jest {FALL_THROUGH_REASONS[failure.exit_class]}",
        }
    return {**outcome, "source": REPO_COVERAGE_SOURCE, "red_build": False, "side_pr_candidate": None}


def measure_coverage_or_ask(
    target, repo, measure_globally, tool_map, policy=None, environ=None, base_ref=None
):
    """`measure_coverage` plus an `ask` for a global tool that cannot measure.

    A missing or crashing global tool, or a run that passes yet
    writes no coverage data, yields an ask and no measurements.
    Once the developer defers it (recorded in `tool_map`'s batch),
    the tool is not run again: coverage reads 0%, labelled
    pessimistic, and no second ask is emitted.
    When no session can ask (see `session_can_ask`, read from
    `environ`), a failure defers on the spot with no ask.
    """
    asks = []

    def measure_globally_or_defer():
        global_tool = global_tool_for("coverage", target.language)
        if global_tool in tool_map.entry()["deferred"]:
            return [deferred_coverage_measurement(target)]
        measurements, failure = _global_coverage_or_failure(measure_globally, global_tool)
        if failure is None:
            return measurements
        ask = ask_or_defer(tool_map, global_tool, "coverage", failure, environ)
        if ask is None:
            return [deferred_coverage_measurement(target)]
        asks.append(ask)
        return []

    outcome = measure_coverage(target, repo, measure_globally_or_defer, tool_map, policy, base_ref)
    return {**outcome, "ask": asks[0] if asks else None}


def _global_coverage_or_failure(measure_globally, global_tool):
    """The global tool's measurements and None, or no measurements and why."""
    try:
        measurements = measure_globally()
    except ToolError as error:
        return [], str(error)
    if not measurements:
        return [], f"{global_tool} exited zero but wrote no coverage data"
    return measurements, None


def _measure_coverage_under_timeout_policy(target, repo, policy, base_ref=None):
    try:
        return policy.run(
            lambda timeout_seconds: measure_coverage_with_repo_tool(target, repo, timeout_seconds, base_ref)
        )
    except ToolTimedOutTwice as error:
        raise RepoToolFailure(TIMEOUT, str(error)) from error
    except RepoToolFailure:
        raise
    except ToolError as error:
        raise RepoToolFailure(CRASH, str(error)) from error


def _base_ref_config_flags(repo, base_ref, config_dir):
    """jest's flags for the config as `base_ref` committed it.

    The copy lives in a subdirectory of the repo, so a preset it
    requires by package name resolves from the repo's node_modules.
    `--rootDir` keeps jest resolving paths against the repo. No flags
    when no ref is given or the base ref holds no jest config.
    """
    if base_ref is None:
        return []
    copies = write_base_ref_configs(repo, base_ref, config_dir)
    if not copies:
        return []
    return ["--config", str(copies[0]), f"--rootDir={repo}"]


def measure_coverage_with_repo_tool(target, repo, timeout_seconds=None, base_ref=None):
    """Changed-line coverage from the repo's jest, with how jest exited.

    With a `base_ref`, jest reads the config that ref committed,
    so a branch's own coverage excludes never shape the number.

    The coverage reads valid when jest passed or exited non-zero on the
    repo's own threshold: the harness judges the measured value against its
    own limit. Any other outcome raises RepoToolFailure naming its class.
    """
    with tempfile.TemporaryDirectory() as report_dir, tempfile.TemporaryDirectory(dir=repo) as config_dir:
        result = run_command(
            [
                "jest", "--coverage", "--coverageReporters=lcov", f"--coverageDirectory={report_dir}",
                *_base_ref_config_flags(repo, base_ref, config_dir),
            ],
            cwd=repo, env=_repo_tool_env(repo), timeout=timeout_seconds,
        )
        exit_class = classify_exit(result)
        if exit_class not in MEASURING_EXIT_CLASSES:
            raise RepoToolFailure(exit_class, f"jest exited {result.returncode}: {result.stderr.strip()}")
        report = Path(report_dir) / "lcov.info"
        if not report.exists():
            raise RepoToolFailure(WROTE_NO_COVERAGE, "jest wrote no lcov report")
        hits_by_file = parse_lcov(report.read_text())
    target_path = Path(repo) / target.path
    line_hits = hits_by_file.get(target.repo_path or str(target_path.relative_to(repo)))
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


def global_tool_for(metric, language):
    """The global tool measuring `metric` for `language`, or NoGlobalToolError."""
    tool = GLOBAL_TOOLS.get(metric, {}).get(language)
    if tool is None:
        raise NoGlobalToolError(metric, language)
    return tool


def _repo_tool_for(metric, tool_map, language):
    """The tool-map entry measuring `metric` for `language`, or None.

    An entry stored before entries carried `languages` has none,
    so it matches no language and the global tool measures.
    """
    if tool_map is None:
        return None
    return next(
        (
            tool for tool in tool_map.entry()["tools"]
            if tool["metric"] == metric and language in tool.get("languages", ())
        ),
        None,
    )


def source_for(metric, tool_map, language):
    """Which tool measures `metric`, and the side-PR candidate if the repo lacks one.

    `tool_map` is None outside a git repo, where no repo tool can
    be missing, so there is no candidate. With no repo tool, the
    global one for `language` measures; none for that pair raises
    NoGlobalToolError.
    """
    repo_tool = _repo_tool_for(metric, tool_map, language)
    if repo_tool is not None:
        return {
            "metric": metric,
            "source": {"kind": "repo", "tool": repo_tool["tool"]},
            "side_pr_candidate": None,
        }
    gap = None if tool_map is None else f"no repo {metric.replace('_', ' ')} tool for {language}"
    return {
        "metric": metric,
        "source": {"kind": "global", "tool": global_tool_for(metric, language)},
        "side_pr_candidate": gap,
    }
