"""Python coverage: uv runs pytest under coverage, then combines
the per-process data files into the lcov report."""

import os
import tempfile
import time
from pathlib import Path

from quality_metrics.coverage_result import (
    NO_COVERAGE_DATA,
    CoverageResult,
    read_fresh_lcov,
)
from quality_metrics.python_test_deps import declared_test_dependency_args
from quality_metrics.sourcing import PYTEST_NO_TESTS_EXIT
from quality_metrics.tools import run_command

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

# `-i` skips a source file the data names that no longer exists,
# such as a script a test ran from a temp dir it then deleted;
# without it one such file fails the whole report
# (coverage.readthedocs.io/en/latest/cmd.html#cmd-lcov).
PYTHON_LCOV_COMMAND = [*PYTHON_COVERAGE_WITH, "lcov", "-i", "-o"]

# `patch = subprocess` measures Python subprocesses a test
# starts; `parallel` gives each process its own data file for
# `combine`
# (coverage.readthedocs.io/en/latest/subprocess.html).
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

FAILURE_REASON_MAX_CHARS = 200
USAGE_ERROR_MARKER = ": error: "
NO_DATA_TO_COMBINE = "No data to combine"


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


def _failed_report_step(step, step_run):
    """A result naming the coverage step that exited non-zero
    and its last stderr line, so a failed report step reads as
    a failure with a reason, never as silent no-data."""
    stderr_lines = step_run.stderr.strip().splitlines()
    reason = f"coverage {step} exited {step_run.returncode}: {stderr_lines[-1].strip() if stderr_lines else ''}"
    return CoverageResult(
        hits_by_file={}, has_failed_tests=False,
        failure_reason=reason[:FAILURE_REASON_MAX_CHARS],
    )


def _with_declared_test_deps(command, repo_dir):
    """The command plus the repo's declared test dependencies,
    added ahead of uv's `--`; unchanged when it has none."""
    separator = command.index("--")
    extra = declared_test_dependency_args(repo_dir)
    return [*command[:separator], *extra, *command[separator:]]


def _lcov_report_of_measured_run(repo_dir, env, report_file, run_started):
    """Combine the run's data files and read the lcov report,
    or name the coverage step that exited non-zero."""
    combine_run = run_command(PYTHON_COMBINE_COMMAND, cwd=repo_dir, env=env)
    if combine_run.returncode != 0:
        if NO_DATA_TO_COMBINE in combine_run.stdout + combine_run.stderr:
            # Nothing was measured, e.g. all omitted.
            return read_fresh_lcov(report_file, repo_dir, run_started)
        return _failed_report_step("combine", combine_run)
    report_run = run_command(
        [*PYTHON_LCOV_COMMAND, str(report_file)], cwd=repo_dir, env=env
    )
    if report_run.returncode != 0:
        return _failed_report_step("lcov", report_run)
    return read_fresh_lcov(report_file, repo_dir, run_started)


def collect_python(repo_dir):
    with tempfile.TemporaryDirectory() as data_dir:
        data_file_outside_repo = Path(data_dir) / ".coverage"
        env = {**os.environ, "COVERAGE_FILE": str(data_file_outside_repo)}
        if repo_has_coverage_config(repo_dir):
            # An inherited rc file would override it.
            env.pop("COVERAGE_RCFILE", None)
        else:
            config_file = Path(data_dir) / "coveragerc"
            config_file.write_text(SUBPROCESS_COVERAGE_CONFIG)
            env["COVERAGE_RCFILE"] = str(config_file)
        run_started = time.time()
        test_run = run_command(
            _with_declared_test_deps(PYTHON_TEST_COMMAND, repo_dir),
            cwd=repo_dir, env=env,
        )
        if test_run.returncode == PYTEST_NO_TESTS_EXIT:
            return NO_COVERAGE_DATA
        if test_run.returncode != 0:
            return _red_build_naming_pytest_exit(test_run)
        return _lcov_report_of_measured_run(
            repo_dir, env, Path(data_dir) / "lcov.info", run_started
        )
