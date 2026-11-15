"""Runs a repo's tests under a coverage tool and reads the lcov report.

Every language writes `coverage/lcov.info` under the repo, as c8 does
by default. Each collector falls back to a global tool: uv with
coverage for Python, c8 for JavaScript and TypeScript, gcov2lcov for Go.

A run that reads as no coverage data (no tests, no report, or a
report older than the run) scores 0%. A run whose tests fail is a red
build: it scores 0% too, marked pessimistic.
"""

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from quality_metrics.crap import parse_lcov
from quality_metrics.tools import run_command, ToolError

LCOV_PATH = Path("coverage") / "lcov.info"

# pytest exits 5 when it collected no tests.
PYTEST_NO_TESTS_EXIT = 5

# pytest joins the ephemeral environment: `coverage run -m
# pytest` fails without it when the repo manages no environment.
PYTHON_TEST_COMMAND = [
    "uv", "run", "--with", "coverage", "--with", "pytest",
    "--", "coverage", "run", "-m", "pytest",
]
PYTHON_LCOV_COMMAND = [
    "uv", "run", "--with", "coverage", "--", "coverage", "lcov", "-o",
]
JAVASCRIPT_TEST_COMMAND = [
    "c8", "--reporter=lcov", "--reports-dir=coverage", "npm", "test",
]
GO_TEST_COMMAND = ["go", "test", "./..."]

# `npm init` writes this test script, which runs no tests.
NPM_INIT_TEST_STUB = 'echo "Error: no test specified"'


@dataclass(frozen=True)
class CoverageResult:
    """Line hits per repo-relative file; `tests_failed` marks a red build."""

    hits_by_file: dict
    tests_failed: bool


NO_COVERAGE_DATA = CoverageResult({}, False)
RED_BUILD = CoverageResult({}, True)


class CoverageRun:
    """Runs each language's tests at most once per measuring run."""

    def __init__(self, repo_dir):
        self.repo_dir = Path(repo_dir)
        self._results = {}

    def result_for(self, language):
        collector = COLLECTORS.get(language)
        if collector is None:
            return NO_COVERAGE_DATA
        if collector not in self._results:
            self._results[collector] = collector(self.repo_dir)
        return self._results[collector]


def collect_python(repo_dir):
    with tempfile.TemporaryDirectory() as data_dir:
        data_file_outside_repo = Path(data_dir) / ".coverage"
        env = {**os.environ, "COVERAGE_FILE": str(data_file_outside_repo)}
        run_started = time.time()
        test_run = run_command(PYTHON_TEST_COMMAND, cwd=repo_dir, env=env)
        if test_run.returncode == PYTEST_NO_TESTS_EXIT:
            return NO_COVERAGE_DATA
        if test_run.returncode != 0:
            return RED_BUILD
        report_file = Path(data_dir) / "lcov.info"
        report_run = run_command(
            [*PYTHON_LCOV_COMMAND, str(report_file)], cwd=repo_dir, env=env
        )

        # coverage deletes its output file when it fails, so the
        # report goes to the repo only on success. A failed run
        # leaves an older file in place for the freshness check.
        if report_run.returncode == 0:
            (repo_dir / LCOV_PATH).parent.mkdir(exist_ok=True)
            shutil.copyfile(report_file, repo_dir / LCOV_PATH)
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
        (repo_dir / LCOV_PATH).parent.mkdir(exist_ok=True)
        run_command(
            ["gcov2lcov", f"-infile={profile}", f"-outfile={repo_dir / LCOV_PATH}"],
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


def read_fresh_lcov(repo_dir, run_started):
    """Hits from the lcov file, or no data when it predates the run."""
    lcov_file = repo_dir / LCOV_PATH
    if not lcov_file.exists() or lcov_file.stat().st_mtime < run_started:
        return NO_COVERAGE_DATA
    hits_by_file = parse_lcov(lcov_file.read_text())
    return CoverageResult(
        {repo_relative(repo_dir, name): hits for name, hits in hits_by_file.items()},
        False,
    )


def repo_relative(repo_dir, name):
    """A repo-relative path, whether `name` is absolute or typed `./a`.

    gcov2lcov and c8 may name a file by absolute path, and a
    `--files` argument may be typed either way.
    """
    name = os.path.normpath(name)
    if not os.path.isabs(name):
        return name
    relative = os.path.relpath(name, repo_dir)
    return name if relative.startswith("..") else relative
