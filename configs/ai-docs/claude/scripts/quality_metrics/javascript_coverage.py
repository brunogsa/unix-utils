"""JavaScript and TypeScript coverage: c8 wraps `npm test` and
writes the lcov report."""

import json
import time

from quality_metrics.coverage_result import NO_COVERAGE_DATA, RED_BUILD, read_fresh_lcov
from quality_metrics.tools import run_command, ToolError

JAVASCRIPT_TEST_COMMAND = [
    "c8", "--reporter=lcov", "--reports-dir=coverage", "npm", "test",
]

# `npm init` writes this test script, which runs no tests.
NPM_INIT_TEST_STUB = 'echo "Error: no test specified"'


def collect_javascript(repo_dir):
    if not declares_npm_test(repo_dir):
        return NO_COVERAGE_DATA
    run_started = time.time()
    test_run = run_command(JAVASCRIPT_TEST_COMMAND, cwd=repo_dir)
    if test_run.returncode != 0:
        return RED_BUILD
    return read_fresh_lcov(repo_dir, run_started)


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
