"""Runs a repo's tests under a coverage tool and reads the lcov
report.

Every language writes `coverage/lcov.info` under the repo, as c8
does by default. Each collector falls back to a global tool: uv
with coverage for Python, c8 for JavaScript and TypeScript,
gcov2lcov for Go.

A run that reads as no coverage data (no tests, no report, or a
report older than the run) scores 0%.
A run whose tests fail is a red build: it scores 0% too, marked
pessimistic.
"""

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from quality_metrics.crap import parse_lcov
from quality_metrics.dependencies import head_tree
from quality_metrics.failures import TimeoutPolicy, ask_or_defer
from quality_metrics.repo_paths import repo_relative_hits
from quality_metrics.sourcing import (
    FAILED_TESTS,
    FALL_THROUGH_REASONS,
    PYTEST_NO_TESTS_EXIT,
    REPO_COVERAGE_RUNNERS,
    RepoToolFailure,
    global_tool_for,
    run_repo_coverage_under_policy,
    source_for,
)
from quality_metrics.tool_map import LazyToolMap
from quality_metrics.tools import run_command, ToolError

LCOV_PATH = Path("coverage") / "lcov.info"

# pytest joins the ephemeral environment: `coverage run -m
# pytest` fails without it when the repo manages no environment.
#
# pyyaml joins it too: a repo's tests that import yaml fail
# collection without it. A fixed package is simpler than reading
# each repo's requirements and pyproject.
#
# pytest-xdist joins it so a repo whose pytest config passes
# `-n <N>` does not exit 4 with "unrecognized arguments: -n".
PYTHON_COVERAGE_WITH = [
    "uv", "run", "--with", "coverage", "--with", "pytest", "--with", "pyyaml",
    "--with", "pytest-xdist", "--",
    "coverage",
]
PYTHON_TEST_COMMAND = [*PYTHON_COVERAGE_WITH, "run", "-m", "pytest"]
PYTHON_COMBINE_COMMAND = [*PYTHON_COVERAGE_WITH, "combine"]
PYTHON_LCOV_COMMAND = [*PYTHON_COVERAGE_WITH, "lcov", "-o"]

# `patch = subprocess` measures Python subprocesses a test
# starts; `parallel` gives each process its own data file for
# `combine`. Documented at
# coverage.readthedocs.io/en/latest/subprocess.html
#
# coverage.py reads one config file and `COVERAGE_RCFILE`
# replaces the repo's own, with no flag or env var for `patch`
# (coverage.readthedocs.io/en/latest/config.html).
#
# So this config applies only to a repo with no coverage config.
# A repo with its own keeps it and loses subprocess measurement.
SUBPROCESS_COVERAGE_CONFIG = "[run]\nparallel = True\npatch = subprocess\n"

# Files that only ever configure coverage, and the section
# marker that shows a shared file configures it too.
DEDICATED_COVERAGE_CONFIGS = [".coveragerc", ".coveragerc.toml"]
SHARED_COVERAGE_CONFIG_MARKERS = {
    "setup.cfg": "[coverage:",
    "tox.ini": "[coverage:",
    "pyproject.toml": "[tool.coverage",
}

JAVASCRIPT_TEST_COMMAND = [
    "c8", "--reporter=lcov", "--reports-dir=coverage", "npm", "test",
]
GO_TEST_COMMAND = ["go", "test", "./..."]

# `npm init` writes this test script, which runs no tests.
NPM_INIT_TEST_STUB = 'echo "Error: no test specified"'


@dataclass(frozen=True)
class CoverageResult:
    """Line hits per repo-relative file.

    `has_failed_tests` marks a red build; `is_deferred` marks a
    global tool that could not run and was deferred.
    `failure_reason` says why a global test run failed.
    """

    hits_by_file: dict
    has_failed_tests: bool
    is_deferred: bool = False
    failure_reason: Optional[str] = None


FAILURE_REASON_MAX_CHARS = 200
USAGE_ERROR_MARKER = ": error: "

NO_COVERAGE_DATA = CoverageResult(hits_by_file={}, has_failed_tests=False)
RED_BUILD = CoverageResult(hits_by_file={}, has_failed_tests=True)
DEFERRED_COVERAGE = CoverageResult(hits_by_file={}, has_failed_tests=False, is_deferred=True)


class NoFreshCoverageError(ToolError):
    """A passing coverage run left no report newer than the
    run."""


@dataclass(frozen=True)
class _Measured:
    """A language's coverage and the tool that produced it."""

    result: CoverageResult
    exit_class: Optional[str]
    source: dict
    side_pr_candidate: Optional[str]


@dataclass(eq=False)
class CoverageRun:
    """Measures each language's coverage at most once per
    measuring run.

    The repo's own jest or pytest-cov runs first, once, for
    every language it measures; any other language, or a repo
    tool that crashed, timed out or wrote no coverage data, runs
    the global collector.

    A failing global collector asks (or defers on the spot in a
    session that cannot ask) and reads as deferred coverage.
    Failing tests are a red build.

    `sources` gets one entry per language measured, naming the
    tool and the repo gap; `asks` gets one entry per ask raised.

    With a `head_ref`, tests run on an export of that ref, so an
    uncommitted file cannot change the coverage of the range.
    """

    repo_dir: Path
    tool_map: Optional[LazyToolMap] = None
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    policy: Optional[TimeoutPolicy] = None
    environ: Optional[dict] = None
    sources: list = field(default_factory=list, init=False)
    asks: list = field(default_factory=list, init=False)
    _measured: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.repo_dir = Path(self.repo_dir)
        self.policy = self.policy or TimeoutPolicy()

    def result_for(self, language):
        collector = COLLECTORS.get(language)
        if collector is None:
            return NO_COVERAGE_DATA
        if collector not in self._measured:
            self._measured[collector] = self._measure(language, collector)
        measured = self._measured[collector]
        if not self._has_source_entry(language):
            self.sources.append(_source_entry(language, measured))
        return measured.result

    def _has_source_entry(self, language):
        return language in {entry["language"] for entry in self.sources}

    def _measure(self, language, collector):
        choice = source_for("coverage", self.tool_map, language)
        with head_tree(self.repo_dir, self.head_ref) as tree:
            if choice["source"]["tool"] in REPO_COVERAGE_RUNNERS:
                return self._measure_with_repo_tool(language, choice["source"], tree)
            return self._measure_globally(language, choice["side_pr_candidate"], tree)

    def _measure_with_repo_tool(self, language, source, tree):
        tool = source["tool"]
        try:
            run = run_repo_coverage_under_policy(tool, tree, self.policy, self.base_ref)
        except RepoToolFailure as failure:
            if failure.exit_class == FAILED_TESTS:
                return _Measured(RED_BUILD, FAILED_TESTS, source, None)
            reason = FALL_THROUGH_REASONS[failure.exit_class]
            return self._measure_globally(language, f"repo {tool} {reason}", tree, failure.exit_class)
        result = CoverageResult(_normalized_hits(tree, run["hits_by_file"], ""), False)
        return _Measured(result, run["exit_class"], source, None)

    def _measure_globally(self, language, side_pr_candidate, tree, exit_class=None):
        tool = global_tool_for("coverage", language)
        source = {"kind": "global", "tool": tool}
        collector = COLLECTORS[language]
        result = self._collect_globally(collector, tool, tree)
        return _Measured(result, result.failure_reason or exit_class, source, side_pr_candidate)

    def _collect_globally(self, collector, tool, tree):
        if self.tool_map is not None and tool in self.tool_map.entry()["deferred"]:
            return DEFERRED_COVERAGE
        try:
            return collector(tree)
        except ToolError as error:
            return self._defer_after_failure(tool, error)

    def _defer_after_failure(self, tool, error):
        if self.tool_map is None and isinstance(error, NoFreshCoverageError):
            return NO_COVERAGE_DATA
        if self.tool_map is None:
            raise error
        ask = ask_or_defer(self.tool_map, tool, "coverage", str(error), self.environ)
        if ask is not None:
            self.asks.append(ask)
        return DEFERRED_COVERAGE


def _source_entry(language, measured):
    return {
        "metric": "coverage",
        "language": language,
        "source": measured.source,
        "exit_class": measured.exit_class,
        "side_pr_candidate": measured.side_pr_candidate,
    }


def repo_has_coverage_config(repo_dir):
    """True when the repo declares its own coverage settings.

    A file that cannot be read counts as declaring them, so the
    repo's config wins on doubt and the run reports no more
    coverage than the repo's own settings allow.
    """
    repo_dir = Path(repo_dir)
    if any((repo_dir / name).exists() for name in DEDICATED_COVERAGE_CONFIGS):
        return True
    for name, marker in SHARED_COVERAGE_CONFIG_MARKERS.items():
        path = repo_dir / name
        if not path.exists():
            continue
        try:
            if marker in path.read_text():
                return True
        except (OSError, UnicodeDecodeError):
            return True
    return False


def _red_build_naming_pytest_exit(test_run):
    """A red build that says which exit code and which output
    line made it red, so a pessimistic 0 explains itself.

    A pytest usage error carries an `error:` line, followed by
    context lines and coverage warnings; any other failure
    ends on its summary line."""
    lines = (test_run.stderr.strip() or test_run.stdout.strip()).splitlines()
    usage_errors = [line for line in lines if USAGE_ERROR_MARKER in line]
    candidates = usage_errors[:1] or lines[-1:] or [""]
    reason = f"pytest exited {test_run.returncode}: {candidates[0].strip()}"
    return CoverageResult(
        hits_by_file={}, has_failed_tests=True,
        failure_reason=reason[:FAILURE_REASON_MAX_CHARS],
    )


def collect_python(repo_dir):
    with tempfile.TemporaryDirectory() as data_dir:
        data_file_outside_repo = Path(data_dir) / ".coverage"
        env = {**os.environ, "COVERAGE_FILE": str(data_file_outside_repo)}
        if not repo_has_coverage_config(repo_dir):
            config_file = Path(data_dir) / "coveragerc"
            config_file.write_text(SUBPROCESS_COVERAGE_CONFIG)
            env["COVERAGE_RCFILE"] = str(config_file)
        run_started = time.time()
        test_run = run_command(PYTHON_TEST_COMMAND, cwd=repo_dir, env=env)
        if test_run.returncode == PYTEST_NO_TESTS_EXIT:
            return NO_COVERAGE_DATA
        if test_run.returncode != 0:
            return _red_build_naming_pytest_exit(test_run)
        run_command(PYTHON_COMBINE_COMMAND, cwd=repo_dir, env=env)
        report_file = Path(data_dir) / "lcov.info"
        report_run = run_command(
            [*PYTHON_LCOV_COMMAND, str(report_file)], cwd=repo_dir, env=env
        )

        # coverage deletes its output file when it fails, so the
        # report goes to the repo only on success. A failed run
        # leaves an older file in place for the freshness check.
        if report_run.returncode == 0:
            shutil.copyfile(report_file, _prepare_lcov_file(repo_dir))
        return read_fresh_lcov(repo_dir, run_started)


def collect_javascript(repo_dir):
    if not declares_npm_test(repo_dir):
        return NO_COVERAGE_DATA
    run_started = time.time()
    test_run = run_command(JAVASCRIPT_TEST_COMMAND, cwd=repo_dir)
    if test_run.returncode != 0:
        return RED_BUILD
    return read_fresh_lcov(repo_dir, run_started)


def collect_go(repo_dir):
    with tempfile.TemporaryDirectory() as data_dir:
        profile = Path(data_dir) / "cover.out"
        run_started = time.time()
        test_run = run_command(
            [*GO_TEST_COMMAND, f"-coverprofile={profile}"], cwd=repo_dir
        )
        if test_run.returncode != 0:
            return RED_BUILD
        lcov_file = _prepare_lcov_file(repo_dir)
        run_command(
            ["gcov2lcov", f"-infile={profile}", f"-outfile={lcov_file}"],
            cwd=repo_dir,
        )
        return read_fresh_lcov(repo_dir, run_started)


COLLECTORS = {
    "python": collect_python,
    "js": collect_javascript,
    "ts": collect_javascript,
    "go": collect_go,
}


def declares_npm_test(repo_dir):
    package_file = repo_dir / "package.json"
    if not package_file.exists():
        return False
    try:
        scripts = json.loads(package_file.read_text()).get("scripts") or {}
    except json.JSONDecodeError as error:
        raise ToolError(f"{package_file} is not valid JSON: {error}") from error
    test_script = scripts.get("test")
    if not isinstance(test_script, str) or not test_script:
        return False
    return not test_script.startswith(NPM_INIT_TEST_STUB)


def _prepare_lcov_file(repo_dir):
    """The repo's lcov path, with its directory created."""
    lcov_file = repo_dir / LCOV_PATH
    lcov_file.parent.mkdir(exist_ok=True)
    return lcov_file


def read_fresh_lcov(repo_dir, run_started):
    """Hits from the lcov file, or no data when it predates the
    run."""
    lcov_file = repo_dir / LCOV_PATH
    if not lcov_file.exists() or lcov_file.stat().st_mtime < run_started:
        raise NoFreshCoverageError(f"the passing coverage run wrote no coverage data under {repo_dir}")
    hits_by_file = parse_lcov(lcov_file.read_text())
    return CoverageResult(
        hits_by_file=_normalized_hits(repo_dir, hits_by_file, _go_module_prefix(repo_dir)),
        has_failed_tests=False,
    )


def _normalized_hits(repo_dir, hits_by_file, module_prefix):
    """Hits keyed by repo-relative name, with any go module
    prefix dropped."""
    return {
        _without_prefix(name, module_prefix): hits
        for name, hits in repo_relative_hits(repo_dir, hits_by_file).items()
    }


def _go_module_prefix(repo_dir):
    """`<module path>/` from go.mod, or "" when there is none.

    gcov2lcov writes each SF as `<module path>/<pkg>/a.go`.
    """
    go_mod = repo_dir / "go.mod"
    if not go_mod.exists():
        return ""
    for line in go_mod.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "module":
            return parts[1].strip('"') + "/"
    return ""


def _without_prefix(name, prefix):
    if prefix and name.startswith(prefix):
        return name[len(prefix):]
    return name
