"""Chooses which tool measures a metric: the repo's own, or the global one.

A repo's own tool wins. With none, the global tool measures it
and the gap is a side-PR candidate.
"""

import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from quality_metrics.crap import parse_lcov
from quality_metrics.dependencies import DEPENDENCY_CRUISER, GO_ARCH_LINT, IMPORT_LINTER
from quality_metrics.failures import ToolTimedOutTwice
from quality_metrics.gate_inputs import write_base_ref_configs
from quality_metrics.repo_paths import repo_relative_hits
from quality_metrics.tool_map import LazyToolMap
from quality_metrics.tools import ToolError, run_command, run_tool

# How a repo tool exited, read from its output, in check order.
PASSED, UNCLASSIFIED = "passed", "unclassified"
FAILED_TESTS, REPO_THRESHOLD, CRASH = "failed_tests", "repo_threshold", "crash"

# The jest lines are jest's summary, its threshold message and a
# node stack frame. The pytest lines are pytest's summary,
# pytest-cov's threshold message (its plugin.py) and pytest's
# INTERNALERROR trace.
EXIT_CLASS_PATTERNS = (
    (FAILED_TESTS, re.compile(r"^Tests:.*\d+ failed", re.MULTILINE)),
    (FAILED_TESTS, re.compile(r"\b\d+ failed\b.* in \d+\.\d+s")),
    (REPO_THRESHOLD, re.compile(r"coverage threshold .* not met")),
    (REPO_THRESHOLD, re.compile(r"Required test coverage of .* not reached")),
    (CRASH, re.compile(r"^\s+at .+:\d+:\d+\)?$", re.MULTILINE)),
    (CRASH, re.compile(r"^INTERNALERROR>", re.MULTILINE)),
)

# Failures that are not exits of a finished run.
TIMEOUT, WROTE_NO_COVERAGE = "timeout", "no_coverage_data"

# pytest exits 5 when it collected no tests.
PYTEST_NO_TESTS_EXIT = 5
NO_TESTS = "no_tests"

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

JEST, PYTEST_COV = "jest", "pytest-cov"

# The repo's own pytest under pytest-cov, which uv adds with no
# install step. Flags are documented at
# pytest-cov.readthedocs.io/en/latest/config.html
PYTEST_COV_COMMAND = ["uv", "run", "--with", "pytest-cov", "--", "pytest", "--cov"]

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
    Returns None outside a git repo.
    Nothing is detected or written until a metric asks the map
    for its entry.
    """
    toplevel = run_command(["git", "-C", str(working_directory), "rev-parse", "--show-toplevel"])
    if toplevel.returncode != 0:
        return None
    repo = Path(toplevel.stdout.strip())
    base_sha = run_tool(["git", "-C", str(repo), "rev-parse", base_ref]).strip()
    return LazyToolMap(repo, base_sha, rules, session_id, map_dir)


@contextmanager
def _base_ref_config_flags(repo, base_ref):
    """jest's flags for the config as `base_ref` committed it.

    The copy lives in a subdirectory of the repo, so a preset it
    requires by package name resolves from the repo's node_modules.
    `--rootDir` keeps jest resolving paths against the repo. No flags,
    and no directory made, when no ref is given or the base ref holds
    no jest config.
    """
    if base_ref is None:
        yield []
        return
    with tempfile.TemporaryDirectory(dir=repo) as config_dir:
        copies = write_base_ref_configs(repo, base_ref, config_dir)
        yield ["--config", str(copies[0]), f"--rootDir={repo}"] if copies else []


def run_repo_jest(repo, timeout_seconds=None, base_ref=None):
    """One coverage run of the repo's jest: how it exited, and every file's line hits.

    With a `base_ref`, jest reads the config that ref committed,
    so a branch's own coverage excludes never shape the number.

    The hits read valid when jest passed or exited non-zero on the
    repo's own threshold: the harness judges the measured value against its
    own limit. Any other outcome raises RepoToolFailure naming its class.
    """
    with tempfile.TemporaryDirectory() as report_dir, _base_ref_config_flags(repo, base_ref) as config_flags:
        result = run_command(
            [
                "jest", "--coverage", "--coverageReporters=lcov", f"--coverageDirectory={report_dir}",
                *config_flags,
            ],
            cwd=repo, env=_repo_tool_env(repo), timeout=timeout_seconds,
        )
        exit_class = classify_exit(result)
        if exit_class not in MEASURING_EXIT_CLASSES:
            raise RepoToolFailure(exit_class, f"jest exited {result.returncode}: {result.stderr.strip()}")
        report = Path(report_dir) / "lcov.info"
        if not report.exists():
            raise RepoToolFailure(WROTE_NO_COVERAGE, "jest wrote no lcov report")
        return {"exit_class": exit_class, "hits_by_file": repo_relative_hits(repo, parse_lcov(report.read_text()))}


def run_repo_pytest_cov(repo, timeout_seconds=None, base_ref=None):
    """One coverage run of the repo's pytest: how it exited, and every file's line hits.

    With a `base_ref`, coverage reads the `.coveragerc` that ref
    committed, so a branch's own omits never shape the number.
    Without a copy it reads the repo's own file, as pytest-cov does.

    A run that collected no tests reads as no hits. Otherwise the
    hits read valid on the same exit classes as the repo jest's.
    """
    with tempfile.TemporaryDirectory() as work_dir:
        report = Path(work_dir) / "lcov.info"
        config_flags = [
            f"--cov-config={copy}"
            for copy in (write_base_ref_configs(repo, base_ref, work_dir, PYTEST_COV) if base_ref else [])
        ]
        result = run_command(
            [*PYTEST_COV_COMMAND, f"--cov-report=lcov:{report}", *config_flags],
            cwd=repo, timeout=timeout_seconds,
        )
        if result.returncode == PYTEST_NO_TESTS_EXIT:
            return {"exit_class": NO_TESTS, "hits_by_file": {}}
        exit_class = classify_exit(result)
        if exit_class not in MEASURING_EXIT_CLASSES:
            raise RepoToolFailure(exit_class, f"pytest exited {result.returncode}: {result.stderr.strip()}")
        if not report.exists():
            raise RepoToolFailure(WROTE_NO_COVERAGE, "pytest-cov wrote no lcov report")
        return {"exit_class": exit_class, "hits_by_file": repo_relative_hits(repo, parse_lcov(report.read_text()))}


# The coverage runner of each repo tool the harness can run.
REPO_COVERAGE_RUNNERS = {JEST: run_repo_jest, PYTEST_COV: run_repo_pytest_cov}


def run_repo_coverage_under_policy(tool, repo, policy, base_ref=None):
    """The repo `tool`'s coverage run, bounded by `policy`'s timeout.

    Raises RepoToolFailure naming how the tool failed: a timeout on
    both attempts is TIMEOUT, any other tool error is CRASH.
    """
    run_repo_coverage = REPO_COVERAGE_RUNNERS[tool]
    try:
        return policy.run(lambda timeout_seconds: run_repo_coverage(repo, timeout_seconds, base_ref))
    except ToolTimedOutTwice as error:
        raise RepoToolFailure(TIMEOUT, str(error)) from error
    except RepoToolFailure:
        raise
    except ToolError as error:
        raise RepoToolFailure(CRASH, str(error)) from error


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
