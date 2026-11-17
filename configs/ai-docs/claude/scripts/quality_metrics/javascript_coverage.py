"""JavaScript and TypeScript coverage: c8 wraps `npm test` and
writes the lcov report."""

import json
import os
import tempfile
import time
from pathlib import Path

from quality_metrics.coverage_result import NO_COVERAGE_DATA, RED_BUILD, read_fresh_lcov
from quality_metrics.tools import run_command, ToolError

C8_LCOV_COMMAND = ["c8", "--reporter=lcov"]

# `npm init` writes this test script, which runs no tests.
NPM_INIT_TEST_STUB = 'echo "Error: no test specified"'

# Test files under these directories are not the repo's suites.
#
# Naming the files, rather than a bare `node --test`, measures
# exactly the repo's suites and skips node_modules.
NODE_TEST_SKIPPED_DIRS = {"node_modules", ".git", "coverage"}
NODE_TEST_FILE_SUFFIX = ".test.js"


def collect_javascript(repo_dir):
    if declares_npm_test(repo_dir):
        wrapped_command = ["npm", "test"]
    else:
        node_test_files = find_node_test_files(repo_dir)
        if not node_test_files:
            return NO_COVERAGE_DATA
        wrapped_command = ["node", "--test", *node_test_files]
    with tempfile.TemporaryDirectory() as reports_dir:
        test_command = [
            *C8_LCOV_COMMAND, f"--reports-dir={reports_dir}", *wrapped_command,
        ]
        run_started = time.time()
        test_run = run_command(test_command, cwd=repo_dir)
        if test_run.returncode != 0:
            return RED_BUILD
        return read_fresh_lcov(
            Path(reports_dir) / "lcov.info", repo_dir, run_started
        )


def find_node_test_files(repo_dir):
    """Repo-relative `*.test.js` paths, sorted, skipping
    dependency, VCS and report directories."""
    found = []
    for directory, subdirs, names in os.walk(repo_dir):
        subdirs[:] = [d for d in subdirs if d not in NODE_TEST_SKIPPED_DIRS]
        found.extend(
            os.path.relpath(os.path.join(directory, name), repo_dir)
            for name in names
            if name.endswith(NODE_TEST_FILE_SUFFIX)
        )
    return sorted(found)


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
