"""Temp-git-repo and measure-script helpers the quality-metrics suites share.

Named without a `.test.py` or `test_` marker, so pytest imports it
and never collects it.
"""

import importlib.machinery
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
MEASURE_SCRIPT = SCRIPTS_DIR / "measure-quality-metrics.py"
SHIPPED_DECLARATION = SCRIPTS_DIR / "quality-metrics.yaml"

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture.author@example.com",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture.author@example.com",
}


# A jest dying on an internal error: a stack trace, no report.
JEST_CRASH_STUB = """#!/bin/bash
echo "TypeError: Cannot read properties of undefined (reading 'config')" >&2
echo "    at Object.run (/repo/node_modules/jest-cli/build/run.js:31:18)" >&2
exit 1
"""


# 25 coverable lines, 23 run: 92% changed-line coverage.
CART_LCOV = "SF:src/cart.js\n" + "".join(
    f"DA:{line},{1 if line <= 23 else 0}\n" for line in range(1, 26)
) + "end_of_record\n"

# Writes an lcov report where it is told to, then fails the
# repo's own 95% threshold the way jest words it.
JEST_STUB = """#!/bin/bash
echo attempt >> "$ATTEMPT_LOG"
for argument in "$@"; do
  case "$argument" in
    --coverageDirectory=*) report_dir="${argument#--coverageDirectory=}";;
  esac
done
cp "$LCOV_FIXTURE" "$report_dir/lcov.info"
echo 'Jest: "global" coverage threshold for lines (95%) not met: 92%' >&2
exit 1
"""

# A c8 that passes yet writes no coverage report.
C8_NO_REPORT_STUB = """#!/bin/bash
exit 0
"""


def install_jest_reporting_cart_coverage(tmp_path, monkeypatch, lcov_text=CART_LCOV):
    lcov_fixture = tmp_path / "cart.lcov"
    lcov_fixture.write_text(lcov_text)
    monkeypatch.setenv("LCOV_FIXTURE", str(lcov_fixture))
    monkeypatch.setenv("ATTEMPT_LOG", str(tmp_path / "attempts.log"))
    install_stub_tool(tmp_path, monkeypatch, "jest", JEST_STUB)


def attempts_in(tmp_path):
    attempt_log = tmp_path / "attempts.log"
    return len(attempt_log.read_text().splitlines()) if attempt_log.exists() else 0


def stubbed_env():
    """The environment a script subprocess needs to see stub tools.

    GIT_ENV froze its PATH at import, so a stub installed by
    `install_stub_tool` is only on os.environ's PATH.
    """
    return {**os.environ, **GIT_ENV, "PATH": os.environ["PATH"],
            "CLAUDE_CODE_ENTRYPOINT": "cli"}


def install_stub_tool(tmp_path, monkeypatch, name, script):
    """Put an executable `name` first on PATH, standing in for a real tool."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / name
    stub.write_text(script)
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def load_script(script_path, module_name):
    """A hyphen-named script as a module, so a test can call its functions.

    SCRIPTS_DIR must already be on sys.path for the script's own imports.
    """
    loader = importlib.machinery.SourceFileLoader(module_name, str(script_path))
    module = types.ModuleType(loader.name)
    module.__file__ = str(script_path)
    loader.exec_module(module)
    return module


def load_measure_script():
    return load_script(MEASURE_SCRIPT, "measure_quality_metrics")


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True, capture_output=True)


def make_repo(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--quiet", "--initial-branch=main")
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "base")
    return repo


def commit_all(repo, message):
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", message)


def head_of(repo):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_measure(repo, declaration_path, *arguments, env=None):
    return subprocess.run(
        [sys.executable, str(MEASURE_SCRIPT), *arguments, "--declaration", str(declaration_path)],
        cwd=repo, env=env or GIT_ENV, capture_output=True, text=True,
    )


COVERAGE_DECLARATION_TEXT = """\
excluded_paths: []
ignored_extensions: [.md]
per_unit: []
languages:
  js:
    extensions: [.js]
    metrics: [coverage]
  ts:
    extensions: [.ts]
    metrics: [coverage]
  python:
    extensions: [.py]
    metrics: [coverage]
"""


def coverage_records_of(tmp_path, target, coverage_run):
    """The coverage records `crap_coverage.measure` gives one target.

    Imports sit inside the function because a suite puts
    SCRIPTS_DIR on sys.path only after importing this module.
    """
    from quality_metrics import crap_coverage
    from quality_metrics.declaration import load_declaration

    declaration_path = tmp_path / "coverage-declaration.yaml"
    declaration_path.write_text(COVERAGE_DECLARATION_TEXT)
    return crap_coverage.measure(
        target, ["coverage"], load_declaration(declaration_path), coverage_run
    )


def install_global_collector(monkeypatch, calls, hits_by_file=None, error=None):
    """Stand in for the global coverage collector of every language.

    Records each call in `calls`; raises `error` when given, else
    reports `hits_by_file`.
    """
    from quality_metrics import collection

    def collector(repo_dir):
        calls.append(repo_dir)
        if error is not None:
            raise error
        return collection.CoverageResult(hits_by_file or {}, False)

    for language in ("js", "ts", "python"):
        monkeypatch.setitem(collection.COLLECTORS, language, collector)


PACKAGE_WITH_TEST_SCRIPT = '{"scripts": {"test": "jest"}}\n'

CART_SOURCE = (
    "function applyDiscount(total, rate) {\n"
    "  if (rate > 0) {\n"
    "    return total - total * rate;\n"
    "  }\n"
    "  return total;\n"
    "}\n"
)


def measure_cart_where_global_c8_writes_no_data(
    tmp_path, monkeypatch, extra_files, declaration_text
):
    """The script's result for src/cart.js with a c8 that writes no report.

    With a session id the script can ask, so the failed global
    collector raises an ask. `extra_files` may add the repo's jest.
    """
    repo = make_repo(tmp_path, {
        "package.json": PACKAGE_WITH_TEST_SCRIPT, "src/cart.js": CART_SOURCE, **extra_files,
    })
    install_stub_tool(tmp_path, monkeypatch, "c8", C8_NO_REPORT_STUB)
    declaration_path = tmp_path / "declaration.yaml"
    declaration_path.write_text(declaration_text)
    return run_measure(
        repo, declaration_path, "--files", "src/cart.js",
        "--session-id", "session-b2c41d", "--map-dir", str(tmp_path),
        env=stubbed_env(),
    )


def verdict_section(verdict, title_prefix):
    """The text of the `## <title_prefix>...` section, up to the next `## `."""
    match = re.search(
        rf"^## {re.escape(title_prefix)}.*?$(.*?)(?=^## |\Z)", verdict, re.M | re.S
    )
    assert match, f"no section starting with {title_prefix!r} in:\n{verdict}"
    return match.group(0)


def verdict_entry_headings(text):
    return re.findall(r"^### \d+\. .*$", text, re.M)


def measure_report(repo, declaration_path, *arguments, env=None):
    """The measure script's parsed JSON report; fails loudly on no output."""
    result = run_measure(repo, declaration_path, *arguments, env=env)
    assert result.stdout, f"no output; stderr: {result.stderr}"
    return json.loads(result.stdout)
